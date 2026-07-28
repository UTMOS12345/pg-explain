from __future__ import annotations

from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from pg_explain.collectors.bloat import BloatStat
from pg_explain.collectors.index_usage import IndexStat
from pg_explain.collectors.slow_queries import SlowQuery
from pg_explain.render.colors import SEVERITY_COLORS, CUSTOM_THEME


def render_slow_queries(queries: list[SlowQuery], title: str = "Top Slow Queries") -> Panel:
    table = Table(title=title, box=box.ROUNDED, border_style="yellow")
    table.add_column("Query", style="white")
    table.add_column("Total", style="red")
    table.add_column("Calls", style="cyan")
    table.add_column("Avg", style="magenta")

    for q in queries:
        table.add_row(
            q.query[:80],
            f"{q.total_time_ms / 1000:.1f}s",
            str(q.calls),
            f"{q.mean_time_ms:.1f}ms",
        )

    return Panel(table, border_style="yellow", box=box.ROUNDED)


def render_index_stats(stats: list[IndexStat], unused: list[str]) -> Panel:
    table = Table(title="Index Usage", box=box.ROUNDED, border_style="cyan")
    table.add_column("Table.Index", style="white")
    table.add_column("Scans", style="green")
    table.add_column("Tup Read", style="cyan")
    table.add_column("Size", style="blue")

    for s in stats[:15]:
        style = "dim" if s.idx_scan == 0 else "white"
        table.add_row(
            f"{s.tablename}.{s.indexname}",
            str(s.idx_scan),
            str(s.idx_tup_read),
            f"{s.size_kb:,}kB",
            style=style,
        )

    if unused:
        table.add_section()
        table.add_row(
            Text(f"Unused indexes ({len(unused)}):", style="yellow"),
            "", "", "",
        )
        for idx in unused[:5]:
            table.add_row(f"  {idx}", "0", "0", "?", style="dim")

    return Panel(table, border_style="cyan", box=box.ROUNDED)


def render_bloat_report(stats: list[BloatStat]) -> Panel:
    table = Table(title="Bloat Report", box=box.ROUNDED, border_style="magenta")
    table.add_column("Table", style="white")
    table.add_column("Size", style="blue")
    table.add_column("Bloat %", style="red")
    table.add_column("Waste", style="yellow")

    for s in stats:
        table.add_row(
            s.tablename,
            s.size_display,
            f"{s.bloat_pct:.1f}%",
            s.waste_display,
        )

    return Panel(table, border_style="magenta", box=box.ROUNDED)


def render_db_dashboard(
    db_label: str,
    slow_queries: list[SlowQuery] | None = None,
    index_stats: list[IndexStat] | None = None,
    unused: list[str] | None = None,
    bloat: list[BloatStat] | None = None,
) -> list[Panel]:
    panels: list[Panel] = []

    panels.append(
        Panel(
            Text(f"Database Diagnostics — {db_label}", style="bold cyan"),
            border_style="cyan",
            box=box.ROUNDED,
        )
    )

    if slow_queries:
        panels.append(render_slow_queries(slow_queries))

    if index_stats is not None:
        panels.append(render_index_stats(index_stats, unused or []))

    if bloat:
        panels.append(render_bloat_report(bloat))

    return panels