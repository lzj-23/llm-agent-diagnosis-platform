import json
from collections import Counter
from pathlib import Path

from pydantic import ValidationError

from diagnosis_agent.rag.knowledge import DOCS, search
from diagnosis_agent.security.guards import redact, sanitize
from diagnosis_agent.tools.contracts import CaseArgs, ReportArgs, Run, SearchArgs, ToolResult
from diagnosis_agent.tools.fixtures import cases

CATALOG = {
    "query_logs": (CaseArgs, "读取案例日志，统计错误、OOM、排队和上下文错误。"),
    "query_metrics": (CaseArgs, "读取案例基线与当前延迟、吞吐、成功率和显存数据。"),
    "compare_runs": (CaseArgs, "比较实验指标并报告配置差异与可比性限制。"),
    "replay_case": (CaseArgs, "离线重放注册案例规则检查；不执行 shell、不压测生产服务。"),
    "search_docs": (SearchArgs, "检索排障知识，返回文档来源和引用ID。"),
    "generate_report": (ReportArgs, "校验引用ID并生成结构化诊断报告。"),
}


def benchmark_adapter(path: Path, allowed_root: Path) -> Run:
    resolved = path.resolve()
    if not resolved.is_relative_to(allowed_root.resolve()):
        raise ValueError("path_outside_allowed_root")
    if resolved.stat().st_size > 10_000_000:
        raise ValueError("file_too_large")
    raw = json.loads(resolved.read_text(encoding="utf-8"))
    case = raw["case"]
    summary = raw["summary"]
    metrics = {
        k: summary.get(k)
        for k in (
            "ttft_p95_seconds",
            "e2e_p95_seconds",
            "request_throughput_per_second",
            "success_rate",
        )
    }
    metrics["gpu_memory_peak_mib"] = raw.get("resources", {}).get("gpu_memory_peak_mib")
    return Run(
        id=case["case_id"],
        model=case["model_key"],
        device=case["device"],
        context_size=case["context_size"],
        concurrency=case["concurrency"],
        prompt_profile=case["prompt_profile"],
        max_tokens=raw["protocol"]["max_tokens"],
        metrics=metrics,
        config=raw["protocol"],
    )


class ToolService:
    def __init__(self, dataset=None, settings=None):
        from diagnosis_agent.config import get_settings

        self.settings = settings or get_settings()
        self.dataset = cases() if dataset is None else dataset
        self.retriever = None
        if dataset is None:
            from diagnosis_agent.tools.contracts import Case

            folder = Path(self.settings.runtime_dir) / "cases"
            for path in folder.glob("*.json"):
                self.dataset[path.stem] = Case.model_validate_json(path.read_text(encoding="utf-8"))

    def schemas(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": desc,
                    "parameters": model.model_json_schema(),
                },
            }
            for name, (model, desc) in CATALOG.items()
        ]

    def call(self, name: str, arguments: dict) -> ToolResult:
        if name not in CATALOG:
            return ToolResult(ok=False, error="tool_not_allowed")
        try:
            args = CATALOG[name][0].model_validate(arguments)
            if name == "search_docs":
                settings = self.settings
                if settings.rag_backend == "neural":
                    from diagnosis_agent.rag.vector_store import NeuralRetriever

                    if self.retriever is None:
                        self.retriever = NeuralRetriever(
                            settings.embedding_model,
                            settings.reranker_model,
                            Path(settings.runtime_dir) / "knowledge.sqlite",
                        )
                        self.retriever.build(DOCS)
                    result = self.retriever.search(args.query, args.top_k)
                    return ToolResult(data=result)
                return ToolResult(data=search(args.query, args.top_k))
            case = self.dataset[args.case_id]
            if name == "query_logs":
                rows = [{**x.model_dump(), "message": redact(x.message)} for x in case.logs]
                return ToolResult(
                    data={
                        "evidence_id": f"{case.id}:logs",
                        "logs": rows,
                        "counts": dict(Counter(x.level for x in case.logs)),
                    }
                )
            if name == "query_metrics":
                return ToolResult(
                    data={
                        "evidence_id": f"{case.id}:metrics",
                        "synthetic": case.synthetic,
                        "baseline": sanitize(case.baseline.model_dump()),
                        "current": sanitize(case.current.model_dump()),
                    }
                )
            if name == "compare_runs":
                before, after = case.baseline, case.current
                diffs = {
                    key: {"before": getattr(before, key), "after": getattr(after, key)}
                    for key in (
                        "model",
                        "device",
                        "context_size",
                        "concurrency",
                        "prompt_profile",
                        "max_tokens",
                        "config",
                    )
                    if getattr(before, key) != getattr(after, key)
                }
                deltas = {
                    k: after.metrics[k] - v
                    for k, v in before.metrics.items()
                    if v is not None and after.metrics.get(k) is not None
                }
                return ToolResult(
                    data={
                        "evidence_id": f"{case.id}:comparison",
                        "changed_conditions": sanitize(diffs),
                        "deltas": deltas,
                        "comparable": not any(
                            k in diffs for k in ("model", "device", "prompt_profile", "max_tokens")
                        ),
                        "caution": "配置变化只是相关性，必须通过控制变量复测确认因果。",
                    }
                )
            if name == "replay_case":
                text = " ".join(x.message.lower() for x in case.logs)
                observations = []
                if "out of memory" in text:
                    observations.append("oom")
                if "exceeds max_model_len" in text:
                    observations.append("config")
                a = case.current.metrics.get("ttft_p95_seconds")
                b = case.baseline.metrics.get("ttft_p95_seconds")
                if a is not None and b and a > b * 2:
                    observations.append("latency")
                return ToolResult(
                    data={
                        "evidence_id": f"{case.id}:replay",
                        "mode": "offline_rule_replay",
                        "observations": observations,
                        "note": "没有启动推理服务，也没有生成新的硬件测量数据。",
                    }
                )
            valid = {f"{case.id}:{k}" for k in ("logs", "metrics", "comparison", "replay")}
            valid |= {x["id"] for x in DOCS}
            if set(args.evidence_ids) - valid:
                return ToolResult(ok=False, error="unknown_evidence")
            return ToolResult(
                data={
                    "case_id": case.id,
                    "conclusion": args.conclusion,
                    "evidence_ids": args.evidence_ids,
                    "recommendations": args.recommendations,
                    "synthetic": case.synthetic,
                    "status": "candidate_diagnosis",
                }
            )
        except ValidationError:
            return ToolResult(ok=False, error="invalid_arguments")
        except KeyError:
            return ToolResult(ok=False, error="case_not_found")
