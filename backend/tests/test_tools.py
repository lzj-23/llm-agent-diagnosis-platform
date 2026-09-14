import pytest

from diagnosis_agent.tools.service import ToolService


@pytest.fixture
def svc():
    return ToolService()


@pytest.mark.parametrize("kind", ["latency", "oom", "config", "normal"])
def test_replay_observations(svc, kind):
    result = svc.call("replay_case", {"case_id": kind + "-0"})
    assert result.ok
    assert result.data["observations"] == ([] if kind == "normal" else [kind])


def test_comparison_conditions(svc):
    r = svc.call("compare_runs", {"case_id": "latency-0"})
    assert r.data["changed_conditions"]["concurrency"]["after"] == 32
    assert r.data["deltas"]["ttft_p95_seconds"] == 2.6


def test_tools_validate_and_deny(svc):
    assert svc.call("shell", {"cmd": "anything"}).error == "tool_not_allowed"
    assert svc.call("query_logs", {"case_id": "../secret"}).error == "invalid_arguments"
    assert svc.call("query_logs", {"case_id": "missing"}).error == "case_not_found"
    assert svc.call("query_metrics", {"case_id": "oom-0", "other": 1}).error == "invalid_arguments"


def test_search_and_report(svc):
    docs = svc.call("search_docs", {"query": "CUDA out of memory"})
    assert docs.data["hits"][0]["id"] == "doc-memory"
    bad = svc.call(
        "generate_report",
        {"case_id": "oom-0", "conclusion": "test", "evidence_ids": ["fabricated"]},
    )
    assert bad.error == "unknown_evidence"
    good = svc.call(
        "generate_report",
        {"case_id": "oom-0", "conclusion": "候选", "evidence_ids": ["oom-0:logs"]},
    )
    assert good.ok
