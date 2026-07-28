from __future__ import annotations

from rich.style import Style
from rich.theme import Theme


SEVERITY_COLORS = {
    "critical": "bold red",
    "warning": "bold yellow",
    "info": "cyan",
    "success": "green",
}

NODE_COLORS = {
    "Seq Scan": "red",
    "Index Scan": "green",
    "Index Only Scan": "green",
    "Bitmap Heap Scan": "yellow",
    "Bitmap Index Scan": "yellow",
    "Nested Loop": "cyan",
    "Hash Join": "blue",
    "Merge Join": "magenta",
    "Sort": "yellow",
    "Limit": "white",
    "Aggregate": "cyan",
    "Hash": "blue",
    "Materialize": "magenta",
    "Memoize": "magenta",
    "Gather": "blue",
    "CTE Scan": "cyan",
    "Subquery Scan": "cyan",
}

def node_style(node_type: str) -> str:
    return NODE_COLORS.get(node_type, "white")

CUSTOM_THEME = Theme({
    "critical": "red",
    "warning": "yellow",
    "info": "cyan",
    "success": "green",
    "dim": "dim white",
    "cost": "blue",
    "time": "magenta",
    "rows": "cyan",
    "buffers": "dim cyan",
})