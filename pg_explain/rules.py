from __future__ import annotations

from pg_explain.models import Issue, PlanNode


def seq_scan_large_table(node: PlanNode, root: PlanNode) -> list[Issue]:
    if node.node_type != "Seq Scan" or node.plan_rows < 1000:
        return []
    if not node.filter:
        return []

    rel = node.relation_name or "(unknown)"
    return [
        Issue(
            severity="critical",
            title=f"Seq Scan on {rel} ({node.plan_rows:,} rows)",
            description=(
                f"The planner chose a sequential scan on \"{rel}\" "
                f"because there is no suitable index for the filter: "
                f"{node.filter}. All {node.plan_rows:,} rows were scanned."
            ),
            recommendation=(
                f"CREATE INDEX CONCURRENTLY idx_{rel}_filter ON {rel} "
                f"(<filter_column>);"
            ),
            estimated_impact=f"~{node.total_cost:.0f} cost units -> ~1-10 units",
            rule_id="seq_scan_large_table",
            node=node,
        )
    ]


def sort_spilled_to_disk(node: PlanNode, root: PlanNode) -> list[Issue]:
    if not node.is_sort:
        return []
    if not node.spilled_to_disk:
        return []

    disk_kb = node.temp_written or 0
    return [
        Issue(
            severity="warning",
            title=f"Sort spilled to disk ({disk_kb}kB)",
            description=(
                "The sort operation exceeded work_mem and used a temp file "
                "on disk. Disk-based sort is 10-100x slower than in-memory."
            ),
            recommendation="SET work_mem = '16MB'; (per-session) or increase the server default.",
            estimated_impact=f"~{disk_kb // 10}ms -> ~1ms",
            rule_id="sort_spilled_to_disk",
            node=node,
        )
    ]


def row_estimate_mismatch(node: PlanNode, root: PlanNode) -> list[Issue]:
    if node.actual_rows is None or node.plan_rows == 0:
        return []
    actual = int(node.actual_rows)
    estimated = node.plan_rows
    if actual < 1000:
        return []
    factor = max(actual, estimated) / max(min(actual, estimated), 1)
    if factor < 10:
        return []

    rel = node.relation_name or "(subquery)"
    return [
        Issue(
            severity="warning",
            title=f"Row estimate off by {factor:.0f}x on {rel}",
            description=(
                f"Estimated: {estimated:,} rows | Actual: {actual:,} rows. "
                "The planner may choose a suboptimal plan due to this misestimate."
            ),
            recommendation=f"ANALYZE {rel}; (or increase default_statistics_target)",
            estimated_impact="Varies — may cause nested loop vs hash join mispick",
            rule_id="row_estimate_mismatch",
            node=node,
        )
    ]


def nested_loop_no_index(node: PlanNode, root: PlanNode) -> list[Issue]:
    if not node.is_join or node.node_type != "Nested Loop":
        return []
    if len(node.children) < 2:
        return []

    inner = node.children[-1]
    if not inner.is_scan or inner.node_type != "Seq Scan":
        return []
    if inner.plan_rows < 100:
        return []

    rel = inner.relation_name or "(unknown)"
    return [
        Issue(
            severity="critical",
            title=f"Nested Loop inner is Seq Scan on {rel} ({inner.plan_rows:,} rows)",
            description=(
                f"The inner child of the Nested Loop is a Seq Scan on "
                f"\"{rel}\" with {inner.plan_rows:,} rows. "
                "Each outer row triggers a full scan of the inner table."
            ),
            recommendation=(
                f"CREATE INDEX ON {rel} (<join_column>); "
                "to enable Index Scan as the inner child."
            ),
            estimated_impact=f"~{node.plan_rows * inner.plan_rows:.0f} -> ~{node.plan_rows * 2:.0f} cost units",
            rule_id="nested_loop_no_index",
            node=node,
        )
    ]


def bitmap_scan_few_rows(node: PlanNode, root: PlanNode) -> list[Issue]:
    if node.node_type != "Bitmap Heap Scan":
        return []
    if node.actual_rows is not None and int(node.actual_rows) >= 10:
        return []
    if node.plan_rows >= 10:
        return []

    return [
        Issue(
            severity="info",
            title="Bitmap Scan returning < 10 rows",
            description=(
                "A Bitmap Heap Scan was used but very few rows were returned. "
                "An Index Scan would likely be more efficient for few rows."
            ),
            recommendation="Consider if an Index Scan would be cheaper for selective predicates.",
            estimated_impact="Minor — usually < 1ms difference",
            rule_id="bitmap_scan_few_rows",
            node=node,
        )
    ]


def cte_materialized(node: PlanNode, root: PlanNode) -> list[Issue]:
    if node.node_type != "CTE Scan":
        return []
    rel = node.cte_name or node.relation_name or "(unknown)"
    return [
        Issue(
            severity="info",
            title=f"CTE \"{rel}\" is materialized",
            description=(
                "PostgreSQL materializes CTEs by default, preventing "
                "predicate push-down into the CTE. The CTE is fully "
                "executed regardless of outer filters."
            ),
            recommendation=(
                f"WITH {rel} AS NOT MATERIALIZED ( ... ) SELECT ... "
                "to allow predicate push-down."
            ),
            estimated_impact="Varies — can reduce rows processed from 100% to filtered set",
            rule_id="cte_materialized",
            node=node,
        )
    ]


def parallel_not_used(node: PlanNode, root: PlanNode) -> list[Issue]:
    if node.plan_rows < 100_000:
        return []
    if node.parallel_aware:
        return []
    if node.workers_planned is not None and node.workers_planned > 0:
        return []

    rel = node.relation_name or "(table)"
    return [
        Issue(
            severity="warning",
            title=f"No parallel scan on large table {rel} ({node.plan_rows:,} rows)",
            description=(
                f"\"{rel}\" has {node.plan_rows:,} rows but is not using "
                "a parallel scan. Sequential processing on a single worker."
            ),
            recommendation=(
                "SET max_parallel_workers_per_gather = 2; "
                "or ensure the table is large enough for the planner to consider parallelism."
            ),
            estimated_impact="2-4x speedup with parallel query",
            rule_id="parallel_not_used",
            node=node,
        )
    ]


def filter_not_pushed(node: PlanNode, root: PlanNode) -> list[Issue]:
    if node.node_type not in ("Index Scan", "Index Only Scan"):
        return []
    if not node.filter:
        return []

    rel = node.relation_name or "(unknown)"
    return [
        Issue(
            severity="info",
            title=f"Filter on {rel} not pushed to index condition",
            description=(
                f"An index scan on \"{rel}\" has a filter: {node.filter}. "
                "This filter is evaluated on every row retrieved from the index. "
                "Consider a composite index that includes the filter column."
            ),
            recommendation=(
                f"CREATE INDEX ON {rel} (<current_index_col>, <filter_column>);"
            ),
            estimated_impact="Reduces rows retrieved from index",
            rule_id="filter_not_pushed",
            node=node,
        )
    ]


def no_index_only_scan(node: PlanNode, root: PlanNode) -> list[Issue]:
    if node.node_type != "Index Scan":
        return []
    if node.actual_rows is not None and node.actual_rows < 100:
        return []

    rel = node.relation_name or "(unknown)"
    return [
        Issue(
            severity="info",
            title=f"Index Only Scan possible on {rel}",
            description=(
                f"An Index Scan on \"{rel}\" could potentially be an "
                "Index Only Scan if the visibility map is up to date. "
                "Index Only Scans avoid heap lookups."
            ),
            recommendation=(
                f"VACUUM {rel}; (to update visibility map for Index Only Scan eligibility)"
            ),
            estimated_impact="~20-30% fewer blocks read",
            rule_id="no_index_only_scan",
            node=node,
        )
    ]


def sort_on_indexed_column(node: PlanNode, root: PlanNode) -> list[Issue]:
    if not node.is_sort:
        return []
    if not node.sort_key:
        return []

    keys = ", ".join(node.sort_key)
    return [
        Issue(
            severity="info",
            title="Sort could use an index",
            description=(
                f"Sort key: ({keys}). "
                "An index on the sort column eliminates the sort step entirely."
            ),
            recommendation=(
                f"CREATE INDEX ON <table> ({keys}); "
                "to provide sorted data directly."
            ),
            estimated_impact="Eliminates the sort operation (~100% reduction)",
            rule_id="sort_on_indexed_column",
            node=node,
        )
    ]


ALL_RULES = {
    "seq-scan": seq_scan_large_table,
    "sort-spill": sort_spilled_to_disk,
    "row-estimate": row_estimate_mismatch,
    "nested-loop-no-index": nested_loop_no_index,
    "bitmap-few-rows": bitmap_scan_few_rows,
    "cte-materialized": cte_materialized,
    "parallel-not-used": parallel_not_used,
    "filter-not-pushed": filter_not_pushed,
    "no-index-only": no_index_only_scan,
    "sort-indexed": sort_on_indexed_column,
}

RULE_NAMES: dict[str, str] = {
    "seq-scan": "Seq Scan on Large Table",
    "sort-spill": "Sort Spilled to Disk",
    "row-estimate": "Row Estimate Mismatch",
    "nested-loop-no-index": "Nested Loop Without Index",
    "bitmap-few-rows": "Bitmap Scan Returning Few Rows",
    "cte-materialized": "CTE Materialized",
    "parallel-not-used": "Parallel Query Not Used",
    "filter-not-pushed": "Filter Not Pushed to Index",
    "no-index-only": "Index Only Scan Possible",
    "sort-indexed": "Sort Could Use Index",
}

DEFAULT_RULES = list(ALL_RULES.keys())