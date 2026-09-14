import asyncio
import json

import pytest

from diagnosis_agent.agents.grounding import arithmetic_issues, check_grounding, fragments


def report(conclusion="观察到错误。根因未知"):
    return {
        "conclusion": conclusion,
        "evidence_ids": ["logs"],
        "recommendations": ["检查日志"],
        "verification": [],
        "uncertainty": "待验证",
    }


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "missing",
        "duplicate",
        "fabricated",
        "no_support",
        "malformed",
        "timeout",
        "unsupported",
        "extra",
        "string_id",
    ],
)
def test_coverage_and_reference_validation(failure):
    calls, events = [], []

    async def invoke(role, messages):
        payload = json.loads(messages[1]["content"])
        assert list(payload["evidence"]) == ["logs"]  # uncited evidence is excluded
        calls.append(role)
        if failure == "timeout":
            raise asyncio.TimeoutError()
        if failure == "malformed":
            return {"content": "not json"}
        rows = [
            {"id": row["id"], "verdict": "supported", "evidence_ids": ["logs"], "reason": "test"}
            for row in payload["fragments"]
        ]
        if failure == "missing":
            rows.pop()
        elif failure == "duplicate":
            rows[1]["id"] = rows[0]["id"]
        elif failure == "fabricated":
            rows[0]["evidence_ids"] = ["private"]
        elif failure == "no_support":
            rows[0]["evidence_ids"] = []
        elif failure == "unsupported":
            rows[0]["verdict"] = "unsupported"
        elif failure == "extra":
            rows[0]["id"] = 999
        elif failure == "string_id":
            rows[0]["id"] = "0"
        return {"content": json.dumps({"judgments": rows})}

    issues = asyncio.run(
        check_grounding(
            report(), {"logs": {}, "private": {}}, invoke, lambda *a, **k: events.append(k)
        )
    )
    assert bool(issues) == bool(failure)
    assert len(calls) == 1
    assert len(events[0]["fragments"]) == 4


def test_report_limit_does_not_silently_skip_fragments():
    async def forbidden(*args):
        raise AssertionError("must not call model")

    issues = asyncio.run(
        check_grounding(report("句子。" * 25), {}, forbidden, lambda *a, **k: None)
    )
    assert issues[0]["code"] == "grounding_size_limit"


def test_provider_bare_judgment_list_is_normalized_before_validation():
    events = []

    async def invoke(role, messages):
        payload = json.loads(messages[1]["content"])
        rows = [
            {"id": row["id"], "verdict": "supported", "evidence_ids": ["logs"], "reason": "test"}
            for row in payload["fragments"]
        ]
        return {"content": json.dumps(rows)}

    issues = asyncio.run(
        check_grounding(
            report(), {"logs": {}}, invoke, lambda *a, **k: events.append(k)
        )
    )

    assert issues == []
    assert len(events[0]["judgments"]) == 4


def test_all_fields_are_included():
    assert {
        row["field"]
        for row in fragments(
            {
                "conclusion": "A",
                "recommendations": ["B"],
                "verification": ["C"],
                "uncertainty": "D",
            }
        )
    } == {"conclusion", "recommendations", "verification", "uncertainty"}


def test_grounding_cancellation_is_not_swallowed():
    async def cancelled(*args):
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(check_grounding(report(), {}, cancelled, lambda *a, **k: None))


@pytest.mark.parametrize(
    "claim,wrong",
    [
        ("从2秒升到5秒，增加了2秒", True),
        ("从2秒升到5秒，增加了3秒", False),
        ("从2秒升至3秒，增加了1000毫秒", False),
        ("从10ms降至8ms，减少2ms", False),
        ("从10ms降至8ms，减少3ms", True),
        ("从0.4秒升至3秒，增加2.6秒", False),
        ("P95为5秒，并发2，增加2台机器", False),
        ("从2秒升到5秒，增加约3秒", False),
    ],
)
def test_explicit_time_delta_calculation(claim, wrong):
    assert bool(arithmetic_issues([{"id": 0, "text": claim}])) == wrong
