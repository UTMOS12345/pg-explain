from __future__ import annotations

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.text import Text

from pg_explain.models import Issue
from pg_explain.render.colors import SEVERITY_COLORS


def render_diagnostics(issues: list[Issue]) -> list[Panel]:
    if not issues:
        return [
            Panel(
                Text("Plan looks healthy — no issues detected", style="green"),
                title="Diagnostics",
                border_style="green",
                box=box.ROUNDED,
            )
        ]

    panels: list[Panel] = []
    for issue in issues:
        color = SEVERITY_COLORS.get(issue.severity, "white")
        icon = {"critical": "\uD83D\uDD34", "warning": "\u26A0\uFE0F", "info": "\u2139\uFE0F"}.get(issue.severity, "")

        content = Text()
        content.append(f"{issue.description}\n\n", "white")
        content.append("RECOMMENDED:\n", "bold")
        content.append(f"  {issue.recommendation}\n\n", "cyan")
        content.append(f"Estimated impact: {issue.estimated_impact}", "dim")

        panels.append(
            Panel(
                content,
                title=f"{icon} {issue.severity.upper()}: {issue.title}",
                border_style=color,
                box=box.ROUNDED,
            )
        )

    return panels