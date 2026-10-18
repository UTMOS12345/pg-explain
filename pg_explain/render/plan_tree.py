from __future__ import annotations

from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from pg_explain.models import PlanNode
from pg_explain.render.colors import node_style


def render_plan_tree(root: PlanNode, title: str | None = None) -> Panel:
    tree = Tree(_node_label(root), guide_style="dim")
    _build_tree(root, tree)
    return Panel(
        tree,
        title=title or "Query Plan Tree",
        border_style="blue",
        box=box.ROUNDED,
    )


def _build_tree(parent_node: PlanNode, parent_tree: Tree) -> None:
    for child in parent_node.children:
        branch = parent_tree.add(_node_label(child))
        _build_tree(child, branch)


def _node_label(node: PlanNode) -> Text:
    style = node_style(node.node_type)
    t = Text()
    t.append(node.pretty_type, style=style)

    parts = []
    if node.relation_name:
        alias_part = f" as {node.alias}" if node.alias and node.alias != node.relation_name else ""
        parts.append(f"on {node.relation_name}{alias_part}")
    # if node.index_name:
    #     parts.append(f"({node.index_name})")
    # if t.plain:
    #     t.append("  ", "dim")
    if node.index_name:
        parts.append(f"({node.index_name})")
    if parts:
        t.append(" " + " ".join(parts), "bold")
    if t.plain:
        t.append("", "dim")



    info = Text()
    if node.has_actuals:
        info.append(f"time={node.actual_total_time:.3f}ms ", "magenta")
        info.append(f"rows={int(node.actual_rows or 0)} ", "cyan")
        if node.actual_loops and node.actual_loops > 1:
            info.append(f"loops={node.actual_loops} ", "dim")
    else:
        info.append(f"cost={node.startup_cost:.2f}..{node.total_cost:.2f} ", "blue")
        info.append(f"rows={node.plan_rows} ", "cyan")

    if node.filter:
        info.append(f"\n  filter: {node.filter}", "dim")

    if node.sort_key:
        keys = ", ".join(node.sort_key)
        info.append(f"\n  sort: {keys}", "dim")
        if node.sort_method:
            info.append(f" ({node.sort_method})", "dim")

    hits = node.shared_hit or 0
    reads = node.shared_read or 0
    if hits or reads:
        info.append(f"\n  buffers: hit={hits} read={reads}", "dim")

    t.append(info)
    return t
