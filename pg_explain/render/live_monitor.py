from __future__ import annotations

from rich import box
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from pg_explain.collectors.locks import ActiveQuery
from pg_explain.render.colors import SEVERITY_COLORS


def render_active_queries(queries: list[ActiveQuery], interval: int) -> Panel:
    if not queries:
        return Panel(
            Text("No active queries", style="green dim"),
            title=f"Live Monitor (refresh: {interval}s)",
            border_style="green",
            box=box.ROUNDED,
        )

    table = Table(box=box.SIMPLE)
    table.add_column("PID", style="bold")
    table.add_column("Duration", style="magenta")
    table.add_column("State", style="cyan")
    table.add_column("Wait", style="yellow")
    table.add_column("Query", style="white")

    for q in queries:
        table.add_row(
            str(q.pid),
            f"{q.duration_ms:.0f}ms",
            q.state,
            q.wait_event or "-",
            q.query[:80],
        )

    return Panel(
        table,
        title=f"Live Monitor — {len(queries)} active (refresh: {interval}s)",
        border_style="yellow",
        box=box.ROUNDED,
    )


def format_duration(ms: float) -> str:
    if ms >= 60_000:
        return f"{ms / 60_000:.1f}m"
    if ms >= 1000:
        return f"{ms / 1000:.1f}s"
    return f"{ms:.0f}ms"