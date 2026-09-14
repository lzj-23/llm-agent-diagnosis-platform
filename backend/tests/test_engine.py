import asyncio
import json

from diagnosis_agent.agents.engine import Engine


class FakeModel:
    def __init__(self, bad=False):
        self.calls = 0
        self.bad = bad
        self.usage = []

    async def chat(self, messages, tools=None):
        self.calls += 1
        if tools and not any(m.get("role") == "tool" for m in messages):
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": str(i),
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps({"case_id": "oom-0"})},
                    }
                    for i, name in enumerate(["query_logs", "query_metrics", "compare_runs"])
                ],
            }
        if tools:
            return {"role": "assistant", "content": "Enough evidence"}
        return {
            "role": "assistant",
            "content": json.dumps(
                {
                    "category": "oom",
                    "conclusion": "候选显存不足",
                    "evidence_ids": ["fabricated" if self.bad else "oom-0:logs"],
                    "recommendations": ["检查并发"],
                    "verification": ["控制变量复测"],
                    "uncertainty": "待验证",
                }
            ),
        }


def test_engine_rejects_fabricated_citation():
    result = asyncio.run(
        Engine(FakeModel(True)).run("排查显存", "oom-0", mode="single", semantic_review=False)
    )
    assert result["status"] == "needs_attention"
    assert result["error"] == "unsupported_citation"
    assert result["evidence"]


def test_engine_persists_tool_events_callback():
    events = []
    result = asyncio.run(
        Engine(FakeModel()).run(
            "排查显存", "oom-0", mode="single", on_event=events.append, semantic_review=False
        )
    )
    assert result["status"] == "completed"
    assert [e["tool"] for e in events if e["action"] == "tool"] == [
        "query_logs",
        "query_metrics",
        "compare_runs",
    ]
    assert events[-1]["action"] == "completed"
    assert any(e.get("tool") == "generate_report" for e in events)


def test_engine_retains_flagged_report_for_human_review():
    class UnsafeReportModel(FakeModel):
        async def chat(self, messages, tools=None):
            reply = await super().chat(messages, tools)
            if not tools:
                report = json.loads(reply["content"])
                report["conclusion"] = "已排除OOM风险"
                reply["content"] = json.dumps(report)
            return reply

    result = asyncio.run(
        Engine(UnsafeReportModel()).run("检查显存", "oom-0", mode="single", semantic_review=False)
    )
    assert result["status"] == "needs_attention"
    assert result["diagnosis"]
    assert result["quality_issues"][0]["code"] == "unsupported_exclusion"
    assert result["report"]


def test_missing_model_tools_use_bounded_scoped_fallback():
    class NoToolsModel(FakeModel):
        async def chat(self, messages, tools=None):
            if tools:
                return {"role": "assistant", "content": "没有调用工具"}
            return await super().chat(messages, tools)

    result = asyncio.run(
        Engine(NoToolsModel()).run("检查显存", "oom-0", mode="single", semantic_review=False)
    )
    assert result["status"] == "completed"
    fallback = [e for e in result["events"] if e.get("source") == "mandatory_evidence_fallback"]
    assert len(fallback) == 3
    assert all(e["arguments"] == {"case_id": "oom-0"} for e in fallback)


def test_engine_revision_is_reaudited_and_can_be_disabled():
    class RevisingModel(FakeModel):
        async def chat(self, messages, tools=None):
            reply = await super().chat(messages, tools)
            if not tools:
                report = json.loads(reply["content"])
                is_revision = "这是一次质量修订" in messages[0]["content"]
                report["conclusion"] = (
                    "证据不足，无法排除OOM风险" if is_revision else "已排除OOM风险"
                )
                reply["content"] = json.dumps(report)
            return reply

    for enabled in (True, False):
        result = asyncio.run(
            Engine(RevisingModel()).run(
                "检查显存", "oom-0", mode="single", quality_repair=enabled, semantic_review=False
            )
        )
        assert result["status"] == ("completed" if enabled else "needs_attention")
        revisions = [e for e in result["events"] if e["action"] == "revision"]
        assert len(revisions) == int(enabled)
        assert any(
            e["action"] == "draft" and "已排除" in e["output"]["conclusion"]
            for e in result["events"]
        )


def test_default_grounding_gate_is_enforced_after_revision():
    class GroundedModel(FakeModel):
        def __init__(self, unsupported):
            super().__init__()
            self.unsupported = unsupported

        async def chat(self, messages, tools=None):
            if "你是证据核对器" in messages[0]["content"]:
                payload = json.loads(messages[1]["content"])
                return {
                    "content": json.dumps(
                        {
                            "judgments": [
                                {
                                    "id": row["id"],
                                    "verdict": "unsupported" if self.unsupported else "hypothesis",
                                    "evidence_ids": [],
                                    "reason": "test audit",
                                }
                                for row in payload["fragments"]
                            ]
                        }
                    )
                }
            return await super().chat(messages, tools)

    for unsupported in (True, False):
        result = asyncio.run(
            Engine(GroundedModel(unsupported)).run("检查显存", "oom-0", mode="single")
        )
        assert result["status"] == ("needs_attention" if unsupported else "completed")
        audits = [event for event in result["events"] if event["action"] == "grounding_audit"]
        assert len(audits) == (2 if unsupported else 1)
        assert result["diagnosis"] and result["report"]
