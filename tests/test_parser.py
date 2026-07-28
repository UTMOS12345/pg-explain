import json
from pathlib import Path

from pg_explain.models import PlanNode
from pg_explain.parser import parse_plan, plan_from_explain_text

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_parse_seq_scan():
    data = load_fixture("plan_seq_scan.json")
    root, meta = parse_plan(data)
    assert root.node_type == "Seq Scan"
    assert root.relation_name == "orders"
    assert root.plan_rows > 0
    assert root.has_actuals
    assert root.is_scan
    assert not root.is_join
    assert len(root.children) == 0
    assert meta["Execution Time"] is not None


def test_parse_nested_loop():
    data = load_fixture("plan_nested_loop.json")
    root, meta = parse_plan(data)
    assert root.node_type == "Limit"
    assert len(root.children) == 1
    nl = root.children[0]
    assert nl.node_type == "Nested Loop"
    assert nl.join_type == "Inner"
    assert nl.is_join
    assert len(nl.children) >= 2
    inner_group = nl.children[-1]
    assert inner_group.node_type in ("Index Scan", "Memoize", "Materialize")
    assert inner_group.parent is nl
    assert root.parent is None


def test_parse_sort_spill():
    data = load_fixture("plan_sort_spill.json")
    root, meta = parse_plan(data)
    assert root.node_type == "Sort"
    assert root.sort_method == "external merge"
    assert root.spilled_to_disk
    assert root.is_sort
    assert len(root.children) == 1
    assert root.children[0].node_type == "Seq Scan"


def test_parse_complex():
    data = load_fixture("plan_complex_query.json")
    root, meta = parse_plan(data)
    assert root.node_type == "Limit"
    assert meta["Execution Time"] is not None


def test_parse_json_string():
    raw = (FIXTURES / "plan_seq_scan.json").read_text()
    root, meta = parse_plan(raw)
    assert root.node_type == "Seq Scan"


def test_parse_from_text():
    raw = (FIXTURES / "plan_seq_scan.json").read_text()
    text = f"QUERY PLAN\n----------\n {raw} \n(1 row)\n"
    root, meta = plan_from_explain_text(text)
    assert root.node_type == "Seq Scan"


def test_plan_node_from_dict():
    raw = {
        "Node Type": "Sort",
        "Startup Cost": 100.0,
        "Total Cost": 500.0,
        "Plan Rows": 1000,
        "Plan Width": 32,
        "Sort Method": "quicksort",
        "Sort Space Used": 64,
        "Sort Space Type": "Memory",
        "Plans": [
            {
                "Node Type": "Seq Scan",
                "Relation Name": "orders",
                "Alias": "o",
                "Startup Cost": 0.0,
                "Total Cost": 100.0,
                "Plan Rows": 1000,
                "Plan Width": 32,
            }
        ],
    }
    root = PlanNode.from_dict(raw)
    assert root.node_type == "Sort"
    assert root.sort_method == "quicksort"
    assert root.sort_space_used == 64
    assert len(root.children) == 1
    assert root.children[0].node_type == "Seq Scan"
    assert root.children[0].relation_name == "orders"
    assert root.children[0].alias == "o"
    assert root.children[0].parent is root


def test_plan_node_properties():
    scan = PlanNode(node_type="Index Scan")
    assert scan.is_scan
    assert not scan.is_join
    assert not scan.is_sort

    join = PlanNode(node_type="Hash Join")
    assert join.is_join
    assert not join.is_scan

    sort = PlanNode(node_type="Sort", sort_method="external merge", temp_written=512)
    assert sort.is_sort
    assert sort.spilled_to_disk

    sort2 = PlanNode(node_type="Sort", sort_method="quicksort")
    assert not sort2.spilled_to_disk

    agg = PlanNode(node_type="Aggregate")
    assert agg.is_aggregate

    no_actuals = PlanNode(node_type="Seq Scan")
    assert not no_actuals.has_actuals
    with_actuals = PlanNode(node_type="Seq Scan", actual_total_time=1.5)
    assert with_actuals.has_actuals


def test_total_buffer_hits():
    n = PlanNode(node_type="Seq Scan", shared_hit=100, local_hit=50)
    assert n.total_buffer_hits == 150
    n2 = PlanNode(node_type="Seq Scan")
    assert n2.total_buffer_hits == 0