from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


_SCAN_TYPES = frozenset({
    "Seq Scan", "Index Scan", "Index Only Scan",
    "Bitmap Heap Scan", "Bitmap Index Scan",
    "CTE Scan", "Subquery Scan", "Function Scan",
    "Values Scan", "Tid Scan", "Sample Scan",
})

_JOIN_TYPES = frozenset({
    "Nested Loop", "Hash Join", "Merge Join",
})

_NODE_TYPE_TO_WORD = {
    "Seq Scan": "Seq Scan",
    "Index Scan": "Index Scan",
    "Index Only Scan": "Index Only Scan",
    "Bitmap Heap Scan": "Bitmap Scan",
    "Bitmap Index Scan": "Bitmap Index Scan",
    "Nested Loop": "Nested Loop",
    "Hash Join": "Hash Join",
    "Merge Join": "Merge Join",
    "Sort": "Sort",
    "Limit": "Limit",
    "Aggregate": "Aggregate",
    "GroupAggregate": "Group Aggregate",
    "SortAggregate": "Sort Aggregate",
    "Hash": "Hash",
    "Materialize": "Materialize",
    "Memoize": "Memoize",
    "Append": "Append",
    "Gather": "Gather",
    "Gather Merge": "Gather Merge",
    "CTE Scan": "CTE Scan",
    "Subquery Scan": "Subquery Scan",
    "Function Scan": "Function Scan",
    "Unique": "Unique",
}


_SNAKE = {
    "Node Type": "node_type",
    "Strategy": "strategy",
    "Join Type": "join_type",
    "Relation Name": "relation_name",
    "Alias": "alias",
    "Startup Cost": "startup_cost",
    "Total Cost": "total_cost",
    "Plan Rows": "plan_rows",
    "Plan Width": "plan_width",
    "Actual Startup Time": "actual_startup_time",
    "Actual Total Time": "actual_total_time",
    "Actual Rows": "actual_rows",
    "Actual Loops": "actual_loops",
    "Filter": "filter",
    "Index Name": "index_name",
    "Index Cond": "index_cond",
    "Sort Key": "sort_key",
    "Sort Method": "sort_method",
    "Sort Space Used": "sort_space_used",
    "Sort Space Type": "sort_space_type",
    "Merge Cond": "merge_cond",
    "Hash Cond": "hash_cond",
    "Shared Hit Blocks": "shared_hit",
    "Shared Read Blocks": "shared_read",
    "Shared Dirtied Blocks": "shared_dirtied",
    "Shared Written Blocks": "shared_written",
    "Local Hit Blocks": "local_hit",
    "Local Read Blocks": "local_read",
    "Local Dirtied Blocks": "local_dirtied",
    "Local Written Blocks": "local_written",
    "Temp Read Blocks": "temp_read",
    "Temp Written Blocks": "temp_written",
    "Rows Removed by Filter": "rows_removed_filter",
    "Rows Removed by Index Recheck": "rows_removed_idx_recheck",
    "Parallel Aware": "parallel_aware",
    "Workers Planned": "workers_planned",
    "Workers Launched": "workers_launched",
    "CTE Name": "cte_name",
    "Subplan Name": "subplan_name",
    "Parent Relationship": "parent_relationship",
    "Disabled": "disabled",
    "Inner Unique": "inner_unique",
    "Scan Direction": "scan_direction",
    "Index Searches": "index_searches",
    "Cache Key": "cache_key",
    "Cache Mode": "cache_mode",
    "Cache Hits": "cache_hits",
    "Cache Misses": "cache_misses",
    "Cache Evictions": "cache_evictions",
    "Cache Overflows": "cache_overflows",
    "Peak Memory Usage": "peak_memory",
}


@dataclass(slots=True)
class PlanNode:
    node_type: str
    strategy: str | None = None
    join_type: str | None = None
    relation_name: str | None = None
    alias: str | None = None
    startup_cost: float = 0.0
    total_cost: float = 0.0
    plan_rows: int = 0
    plan_width: int = 0
    actual_startup_time: float | None = None
    actual_total_time: float | None = None
    actual_rows: float | None = None
    actual_loops: int | None = None
    filter: str | None = None
    index_name: str | None = None
    index_cond: str | None = None
    sort_key: list[str] | None = None
    sort_method: str | None = None
    sort_space_used: int | None = None
    sort_space_type: str | None = None
    merge_cond: str | None = None
    hash_cond: str | None = None
    shared_hit: int | None = None
    shared_read: int | None = None
    shared_dirtied: int | None = None
    shared_written: int | None = None
    local_hit: int | None = None
    local_read: int | None = None
    local_dirtied: int | None = None
    local_written: int | None = None
    temp_read: int | None = None
    temp_written: int | None = None
    rows_removed_filter: int | None = None
    rows_removed_idx_recheck: int | None = None
    parallel_aware: bool = False
    workers_planned: int | None = None
    workers_launched: int | None = None
    cte_name: str | None = None
    subplan_name: str | None = None
    parent_relationship: str | None = None
    disabled: bool | None = None
    inner_unique: bool | None = None
    scan_direction: str | None = None
    index_searches: int | None = None
    cache_key: str | None = None
    cache_mode: str | None = None
    cache_hits: int | None = None
    cache_misses: int | None = None
    cache_evictions: int | None = None
    cache_overflows: int | None = None
    peak_memory: int | None = None

    children: list[PlanNode] = field(default_factory=list)
    parent: PlanNode | None = field(default=None, repr=False)

    # ── computed properties ──────────────────────────────────

    @property
    def is_scan(self) -> bool:
        return self.node_type in _SCAN_TYPES

    @property
    def is_join(self) -> bool:
        return self.node_type in _JOIN_TYPES

    @property
    def is_sort(self) -> bool:
        return self.node_type == "Sort"

    @property
    def is_aggregate(self) -> bool:
        return self.node_type in ("Aggregate", "GroupAggregate", "SortAggregate")

    @property
    def has_actuals(self) -> bool:
        return self.actual_total_time is not None

    @property
    def total_buffer_hits(self) -> int:
        return (self.shared_hit or 0) + (self.local_hit or 0)

    @property
    def total_buffer_reads(self) -> int:
        return (self.shared_read or 0) + (self.local_read or 0)

    @property
    def spilled_to_disk(self) -> bool:
        return (self.sort_method == "external merge") or ((self.temp_written or 0) > 0)

    @property
    def pretty_type(self) -> str:
        return _NODE_TYPE_TO_WORD.get(self.node_type, self.node_type)

    # ── JSON parsing ─────────────────────────────────────────

    @classmethod
    def from_dict(cls, d: dict) -> PlanNode:
        kwargs: dict = {}
        for json_key, field_name in _SNAKE.items():
            if json_key in d:
                kwargs[field_name] = d[json_key]

        children_data = d.get("Plans")
        children: list[PlanNode] = []
        if isinstance(children_data, list):
            for child in children_data:
                node = cls.from_dict(child)
                children.append(node)

        kwargs["children"] = children
        node = cls(**kwargs)
        for child in children:
            child.parent = node
        return node

    def __str__(self) -> str:
        return f"{self.pretty_type} (cost={self.startup_cost}..{self.total_cost})"


@dataclass
class Issue:
    severity: Literal["critical", "warning", "info"]
    title: str
    description: str
    recommendation: str
    estimated_impact: str
    rule_id: str
    node: PlanNode | None = None
