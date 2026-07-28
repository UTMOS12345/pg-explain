from __future__ import annotations

import json
import pathlib
import sys
import time

import click
from rich.console import Console

from pg_explain.analyzer import analyze
from pg_explain.config import DbConfig, load_config, merge_config
from pg_explain.executor import (
    execute_explain,
    execute_explain_estimate,
    read_plan_from_file,
    read_plan_from_stdin,
    test_connection,
)
from pg_explain.parser import parse_plan
from pg_explain.render.colors import CUSTOM_THEME
from pg_explain.render.dashboard import render_db_dashboard
from pg_explain.render.diagnostics import render_diagnostics
from pg_explain.render.live_monitor import render_active_queries
from pg_explain.render.plan_tree import render_plan_tree
from pg_explain.rules import DEFAULT_RULES, RULE_NAMES

console = Console(theme=CUSTOM_THEME)


@click.group()
@click.version_option(version="0.1.0", prog_name="pg-explain")
def main():
    pass


@main.command()
@click.option("--db", "-d", help="Connection string (postgresql://...)")
@click.option("--query", "-q", help="SQL query to analyze")
@click.option("--file", "-f", "file_path", type=click.Path(exists=True), help="Read query from file")
@click.option("--stdin", "read_stdin", is_flag=True, help="Read query from stdin")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--save", type=click.Path(), help="Save rendered output to file")
@click.option("--verbose", "-v", is_flag=True, help="Show all plan nodes")
@click.option("--rules", help="Comma-separated rule IDs")
@click.option("--threshold", type=float, default=100.0, help="Cost threshold for warnings")
@click.option("--no-analyze", is_flag=True, help="Skip ANALYZE (estimates only)")
def query(db, query, file_path, read_stdin, as_json, save, verbose, rules, threshold, no_analyze):
    cfg = _resolve_config(db)

    sql = query
    if file_path:
        sql = pathlib.Path(file_path).read_text().strip()
    elif read_stdin or not sql:
        sql = sys.stdin.read().strip()

    if not sql:
        console.print("[red]No query provided. Use --query, --file, or --stdin.[/red]")
        sys.exit(1)

    rule_ids = _parse_rules(rules)

    with console.status("[bold cyan]Running EXPLAIN ...[/bold cyan]"):
        try:
            if no_analyze:
                json_str = execute_explain_estimate(cfg, sql)
            else:
                json_str = execute_explain(cfg, sql)
        except Exception as e:
            console.print(f"[red]Error executing query: {e}[/red]")
            sys.exit(1)

    root, meta = parse_plan(json_str)
    issues = analyze(root, rule_ids) if not as_json else []

    if as_json:
        output = _to_json(root, meta, issues)
        if save:
            pathlib.Path(save).write_text(output)
        else:
            console.print(output)
        return

    panels = []
    exec_time = meta.get("Execution Time")
    title_parts = ["Query Analysis"]
    if exec_time:
        title_parts.append(f"{exec_time:.3f}ms total")
    title = " \u00b7 ".join(title_parts)

    panels.append(render_plan_tree(root, title=title))
    panels.extend(render_diagnostics(issues))

    if save:
        _save_html(save, panels)

    for panel in panels:
        console.print(panel)


@main.command()
@click.option("--db", "-d", help="Connection string (postgresql://...)")
@click.option("--file", "-f", "file_path", type=click.Path(exists=True), required=True, help="EXPLAIN output file")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--rules", help="Comma-separated rule IDs")
def file_cmd(db, file_path, as_json, rules):
    rule_ids = _parse_rules(rules)

    try:
        json_str = read_plan_from_file(file_path)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    root, meta = parse_plan(json_str)
    issues = analyze(root, rule_ids) if not as_json else []

    if as_json:
        console.print(_to_json(root, meta, issues))
        return

    panels = [render_plan_tree(root)]
    panels.extend(render_diagnostics(issues))
    for panel in panels:
        console.print(panel)


@main.command()
@click.option("--db", "-d", required=True, help="Connection string")
@click.option("--save", type=click.Path(), help="Save report to file")
def diagnose(db, save):
    cfg = _resolve_config(db)

    with console.status("[bold cyan]Collecting diagnostics ...[/bold cyan]"):
        try:
            version = test_connection(cfg)
        except Exception as e:
            console.print(f"[red]Connection failed: {e}[/red]")
            sys.exit(1)

        slow_queries = None
        try:
            from pg_explain.collectors.slow_queries import get_slow_queries
            slow_queries = get_slow_queries(cfg.conn_string)
        except Exception:
            pass

        index_stats = None
        unused = None
        try:
            from pg_explain.collectors.index_usage import get_index_stats
            index_stats, unused = get_index_stats(cfg.conn_string)
        except Exception:
            pass

        bloat = None
        try:
            from pg_explain.collectors.bloat import estimate_bloat
            bloat = estimate_bloat(cfg.conn_string)
        except Exception:
            pass

    db_label = cfg.display_name()
    panels = render_db_dashboard(db_label, slow_queries, index_stats, unused, bloat)
    for panel in panels:
        console.print(panel)


@main.command()
@click.option("--db", "-d", required=True, help="Connection string")
@click.option("--interval", type=int, default=5, help="Refresh interval (seconds)")
def watch(db, interval):
    cfg = _resolve_config(db)

    try:
        from pg_explain.collectors.locks import get_active_queries
    except ImportError:
        console.print("[red]Could not import lock collector[/red]")
        sys.exit(1)

    try:
        while True:
            queries = get_active_queries(cfg.conn_string)
            console.clear()
            panel = render_active_queries(queries, interval)
            console.print(panel)
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[yellow]Exited.[/yellow]")


@main.command()
@click.option("--host", default="localhost", help="Database host")
@click.option("--port", type=int, default=5432, help="Database port")
@click.option("--dbname", help="Database name")
@click.option("--user", help="Database user")
def config(host, port, dbname, user):
    config_path = pathlib.Path.home() / ".pg-explain.toml"
    existing = load_config()

    cfg = DbConfig(
        host=host or existing.host,
        port=port or existing.port,
        dbname=dbname or existing.dbname,
        user=user or existing.user,
    )

    toml_content = f"""[connection]
host = "{cfg.host}"
port = {cfg.port}
dbname = "{cfg.dbname}"
user = "{cfg.user}"
"""
    config_path.write_text(toml_content)
    console.print(f"[green]Config saved to {config_path}[/green]")


def _resolve_config(cli_db: str | None) -> DbConfig:
    file_cfg = load_config()
    return merge_config(cli_db, file_cfg)


def _parse_rules(rules_str: str | None) -> list[str]:
    if not rules_str:
        return DEFAULT_RULES
    ids = [r.strip() for r in rules_str.split(",")]
    valid = [r for r in ids if r in RULE_NAMES]
    if not valid:
        console.print(f"[yellow]Warning: no valid rules specified, using defaults[/yellow]")
        return DEFAULT_RULES
    return valid


def _to_json(root, meta, issues) -> str:
    def node_dict(n):
        return {
            "node_type": n.node_type,
            "relation_name": n.relation_name,
            "startup_cost": n.startup_cost,
            "total_cost": n.total_cost,
            "plan_rows": n.plan_rows,
            "actual_rows": n.actual_rows,
            "actual_total_time": n.actual_total_time,
            "filter": n.filter,
            "children": [node_dict(c) for c in n.children],
        }

    output = {
        "metadata": {
            "planning_time": meta.get("Planning Time"),
            "execution_time": meta.get("Execution Time"),
        },
        "plan": node_dict(root),
        "issues": [
            {
                "severity": i.severity,
                "title": i.title,
                "description": i.description,
                "recommendation": i.recommendation,
                "rule_id": i.rule_id,
            }
            for i in issues
        ],
    }
    return json.dumps(output, indent=2)


def _save_html(path: str, panels) -> None:
    from rich.console import Console as RichConsole

    c = RichConsole(record=True)
    for panel in panels:
        c.print(panel)
    html = c.export_html()
    pathlib.Path(path).write_text(html)
    console.print(f"[green]Report saved to {path}[/green]")


if __name__ == "__main__":
    main()