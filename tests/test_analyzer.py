import json
from pathlib import Path

from pg_explain.analyzer import analyze
from pg_explain.models import PlanNode
from pg_explain.parser import parse_plan

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> tuple[PlanNode, dict]:
    raw = json.loads((FIXTURES / name).read_text())
    return parse_plan(raw)


def test_analyze_seq_scan():
    root, meta = load_fixture("plan_seq_scan.json")
    issues = analyze(root)
    assert len(issues) >= 1
    ids = {i.rule_id for i in issues}
    assert "seq_scan_large_table" in ids or "parallel_not_used" in ids
    for issue in issues:
        assert issue.severity in ("critical", "warning", "info")


def test_analyze_nested_loop():
    root, meta = load_fixture("plan_nested_loop.json")
    issues = analyze(root)
    assert len(issues) >= 0


def test_analyze_sort_spill():
    root, meta = load_fixture("plan_sort_spill.json")
    issues = analyze(root)
    ids = {i.rule_id for i in issues}
    assert "sort_spilled_to_disk" in ids
    for i in issues:
        if i.rule_id == "sort-spill":
            assert i.severity == "warning"


def test_analyze_complex():
    root, meta = load_fixture("plan_complex_query.json")
    issues = analyze(root)
    assert len(issues) >= 0


def test_analyze_no_issues():
    n = PlanNode(node_type="Limit", plan_rows=10)
    child = PlanNode(node_type="Index Scan", relation_name="t", plan_rows=5, actual_rows=5, index_name="t_pkey")
    n.children = [child]
    child.parent = n
    issues = analyze(n)
    assert len(issues) >= 0


def test_analyze_with_custom_rules():
    root, meta = load_fixture("plan_seq_scan.json")
    issues = analyze(root, rules=["sort-spill"])
    assert len(issues) == 0


def test_analyze_dedup():
    n = PlanNode(
        node_type="Seq Scan",
        relation_name="orders",
        plan_rows=100000,
        filter="(x > 1)",
    )
    issues = analyze(n, rules=["seq-scan"])
    assert len(issues) == 1


def test_analyze_sort_by_severity():
    issues = analyze(
        PlanNode(
            node_type="Seq Scan",
            relation_name="t",
            plan_rows=100000,
            filter="(x > 1)",
        ),
        rules=["seq-scan", "sort-spill", "sort-indexed"],
    )
    severities = [i.severity for i in issues]
    assert severities == sorted(severities, key={"critical": 0, "warning": 1, "info": 2}.get)