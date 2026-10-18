from pg_explain.models import PlanNode
from pg_explain.rules import (
    seq_scan_large_table,
    sort_spilled_to_disk,
    row_estimate_mismatch,
    nested_loop_no_index,
    bitmap_scan_few_rows,
    cte_materialized,
    parallel_not_used,
    filter_not_pushed,
    no_index_only_scan,
    sort_on_indexed_column,
    ALL_RULES,
    RULE_NAMES,
)


def test_seq_scan_fires():
    n = PlanNode(node_type="Seq Scan", relation_name="t", plan_rows=100000, filter="(x > 1)")
    assert len(seq_scan_large_table(n, n)) == 1


def test_seq_scan_skip_small():
    n = PlanNode(node_type="Seq Scan", relation_name="t", plan_rows=500, filter="(x > 1)")
    assert len(seq_scan_large_table(n, n)) == 0


def test_seq_scan_skip_no_filter():
    n = PlanNode(node_type="Seq Scan", relation_name="t", plan_rows=100000)
    assert len(seq_scan_large_table(n, n)) == 0


def test_sort_spill_fires():
    n = PlanNode(node_type="Sort", sort_method="external merge", temp_written=512)
    assert len(sort_spilled_to_disk(n, n)) == 1


def test_sort_spill_skip_in_memory():
    n = PlanNode(node_type="Sort", sort_method="quicksort")
    assert len(sort_spilled_to_disk(n, n)) == 0


def test_sort_spill_skip_non_sort():
    n = PlanNode(node_type="Seq Scan")
    assert len(sort_spilled_to_disk(n, n)) == 0


def test_row_estimate_fires():
    n = PlanNode(node_type="Index Scan", plan_rows=1500, actual_rows=31240)
    assert len(row_estimate_mismatch(n, n)) == 1


def test_row_estimate_skip_small_actual():
    n = PlanNode(node_type="Index Scan", plan_rows=10, actual_rows=50)
    assert len(row_estimate_mismatch(n, n)) == 0


def test_row_estimate_skip_no_actuals():
    n = PlanNode(node_type="Index Scan", plan_rows=1000)
    assert len(row_estimate_mismatch(n, n)) == 0


def test_nested_loop_fires():
    inner = PlanNode(node_type="Seq Scan", relation_name="t", plan_rows=5000)
    nl = PlanNode(node_type="Nested Loop", join_type="Inner", children=[PlanNode(node_type="Index Scan"), inner])
    inner.parent = nl
    assert len(nested_loop_no_index(nl, nl)) == 1


def test_nested_loop_skip_indexed_inner():
    inner = PlanNode(node_type="Index Scan", relation_name="t", plan_rows=5000)
    nl = PlanNode(node_type="Nested Loop", children=[PlanNode(node_type="Index Scan"), inner])
    inner.parent = nl
    assert len(nested_loop_no_index(nl, nl)) == 0


def test_nested_loop_skip_small_inner():
    inner = PlanNode(node_type="Seq Scan", relation_name="t", plan_rows=50)
    nl = PlanNode(node_type="Nested Loop", children=[PlanNode(node_type="Index Scan"), inner])
    inner.parent = nl
    assert len(nested_loop_no_index(nl, nl)) == 0


def test_bitmap_few_rows_fires():
    n = PlanNode(node_type="Bitmap Heap Scan", plan_rows=3, actual_rows=3)
    assert len(bitmap_scan_few_rows(n, n)) == 1


def test_bitmap_few_rows_skip_many():
    n = PlanNode(node_type="Bitmap Heap Scan", plan_rows=100, actual_rows=100)
    assert len(bitmap_scan_few_rows(n, n)) == 0


def test_cte_materialized_fires():
    n = PlanNode(node_type="CTE Scan", cte_name="my_cte")
    assert len(cte_materialized(n, n)) == 1


def test_parallel_not_used_fires():
    n = PlanNode(node_type="Seq Scan", relation_name="t", plan_rows=200000, parallel_aware=False)
    assert len(parallel_not_used(n, n)) == 1


def test_parallel_not_used_skip_small():
    n = PlanNode(node_type="Seq Scan", plan_rows=50000)
    assert len(parallel_not_used(n, n)) == 0


def test_parallel_not_used_skip_parallel():
    n = PlanNode(node_type="Seq Scan", plan_rows=200000, parallel_aware=True)
    assert len(parallel_not_used(n, n)) == 0


def test_filter_not_pushed_fires():
    n = PlanNode(node_type="Index Scan", relation_name="t", filter="(total > 100)")
    assert len(filter_not_pushed(n, n)) == 1


def test_filter_not_pushed_skip_no_filter():
    n = PlanNode(node_type="Index Scan", relation_name="t")
    assert len(filter_not_pushed(n, n)) == 0


def test_no_index_only_scan_fires():
    n = PlanNode(node_type="Index Scan", relation_name="t", actual_rows=500)
    assert len(no_index_only_scan(n, n)) == 1


def test_no_index_only_skip_few_rows():
    n = PlanNode(node_type="Index Scan", relation_name="t", actual_rows=10)
    assert len(no_index_only_scan(n, n)) == 0


def test_no_index_only_skip_non_index_scan():
    n = PlanNode(node_type="Seq Scan", relation_name="t")
    assert len(no_index_only_scan(n, n)) == 0


def test_sort_indexed_fires():
    n = PlanNode(node_type="Sort", sort_key=["created_at DESC"])
    assert len(sort_on_indexed_column(n, n)) == 1


def test_sort_indexed_skip_no_keys():
    n = PlanNode(node_type="Sort")
    assert len(sort_on_indexed_column(n, n)) == 0


def test_all_rules_registered():
    assert len(ALL_RULES) >= 10
    assert "seq-scan" in ALL_RULES
    assert "sort-spill" in ALL_RULES
    assert "row-estimate" in ALL_RULES
    assert "parallel-not-used" in ALL_RULES
    assert "filter-not-pushed" in ALL_RULES


def test_rule_names_registered():
    assert len(RULE_NAMES) >= 10
    for rule_id in ALL_RULES:
        assert rule_id in RULE_NAMES


def test_row_estimate_title_shows_factor():
    n = PlanNode(node_type="Index Scan", relation_name="orders", plan_rows = 100, actual_rows = 10_000)
    issues = row_estimate_mismatch(n,n)
    assert '100x' in issues[0].title
