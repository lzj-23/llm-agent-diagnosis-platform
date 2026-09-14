import asyncio
import json

import pytest

from diagnosis_agent.agents.engine import Diagnosis, Engine
from diagnosis_agent.agents.model import ModelError
from diagnosis_agent.agents.quality import audit_report


def report(text="无OOM日志，已排除显存不足", ids=None):
    return Diagnosis(
        category="config",
        conclusion=text,
        evidence_ids=["case:logs"] if ids is None else ids,
        recommendations=["采集显存指标"],
        verification=["控制变量复测"],
        uncertainty="缺少运行时显存测量",
    )


@pytest.mark.parametrize(
    "kind", ["valid", "unsafe", "fabricated", "empty", "malformed", "timeout", "budget"]
)
def test_bounded_revision_preserves_evidence_and_original(kind):
    original = report()
    evidence = {"case:logs": {"lines": []}}
    findings = audit_report(original.model_dump())
    events, calls = [], []

    async def invoke(role, messages):
        calls.append(role)
        payload = json.loads(messages[1]["content"])
        assert payload["evidence"] == evidence
        assert payload["findings"] == findings
        if kind == "timeout":
            raise asyncio.TimeoutError()
        if kind == "budget":
            raise ModelError("budget_exceeded")
        if kind == "malformed":
            return {"content": "not json"}
        candidate = report("未观测到OOM日志，但无法排除显存不足，需补充测量")
        if kind == "unsafe":
            candidate = original
        if kind == "fabricated":
            candidate.evidence_ids = ["not-observed"]
        if kind == "empty":
            candidate.evidence_ids = []
        return {"content": candidate.model_dump_json()}

    def event(role, action, **data):
        events.append({"role": role, "action": action, **data})

    revised, remaining = asyncio.run(
        Engine.repair_report(original, evidence, findings, invoke, event)
    )
    assert calls == ["quality_repair"]
    assert events
    if kind == "valid":
        assert not remaining
        assert revised.conclusion != original.conclusion
    else:
        assert revised is original
        assert remaining == findings


def test_cancellation_propagates():
    async def invoke(*args):
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(Engine.repair_report(report(), {}, [], invoke, lambda *a, **k: None))
