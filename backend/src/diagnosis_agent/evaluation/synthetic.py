"""Deterministic causal fixtures. They are synthetic, not reconstructed incidents."""

import hashlib
import random
from dataclasses import dataclass

from diagnosis_agent.tools.contracts import Case, Log, Run

SCENARIOS = (
    "queue_saturation",
    "context_limit",
    "kv_cache_pressure",
    "external_memory_contention",
    "telemetry_missing",
    "conflicting_evidence",
    "mixed_queue_oom",
    "normal_control",
)
SPLIT_COUNTS = {"development": 48, "validation": 24, "frozen": 24}
SPLIT_SEEDS = {"development": 23017, "validation": 71429, "frozen": 99173}


@dataclass(frozen=True)
class Generated:
    case: Case
    label: dict


def _run(rng, run_id="baseline", *, device="synthetic-16GB"):
    ttft = round(rng.uniform(0.25, 0.55), 3)
    e2e = round(rng.uniform(1.5, 3.0), 3)
    throughput = round(rng.uniform(3.5, 7.5), 3)
    memory = round(rng.uniform(6500, 9500), 1)
    concurrency = rng.choice((4, 8))
    return Run(
        id=run_id,
        model="synthetic-model",
        device=device,
        context_size=rng.choice((2048, 4096)),
        concurrency=concurrency,
        prompt_profile="synthetic-fixed",
        max_tokens=128,
        metrics={
            "ttft_p95_seconds": ttft,
            "e2e_p95_seconds": e2e,
            "request_throughput_per_second": throughput,
            "success_rate": 1.0,
            "gpu_memory_peak_mib": memory,
            "waiting_requests_peak": 0.0,
            "preemptions": 0.0,
        },
        config={"max_num_seqs": 16, "gpu_memory_utilization": 0.8},
    )


def _timestamp(index):
    return f"2026-02-01T00:{index % 60:02d}:00Z"


def make_generated(split, scenario, index):
    if split not in SPLIT_COUNTS or scenario not in SCENARIOS:
        raise KeyError("unknown_split_or_scenario")
    seed_text = f"synthetic-v2:{SPLIT_SEEDS[split]}:{scenario}:{index}"
    rng = random.Random(int(hashlib.sha256(seed_text.encode()).hexdigest()[:16], 16))
    baseline = _run(rng)
    current = baseline.model_copy(deep=True)
    current.id = "current"
    logs, expected, cause = [], "unknown", "insufficient_evidence"
    required = ["query_logs", "query_metrics", "compare_runs"]
    supported, forbidden = [], ["故障已修复", "已完成生产变更"]
    ambiguity = []

    if scenario == "queue_saturation":
        expected, cause = "latency", "scheduler_queue_saturation"
        current.concurrency = rng.randint(24, 64)
        current.metrics["ttft_p95_seconds"] = round(
            baseline.metrics["ttft_p95_seconds"] * rng.uniform(5, 9), 3
        )
        current.metrics["e2e_p95_seconds"] = round(
            baseline.metrics["e2e_p95_seconds"] * rng.uniform(2, 4), 3
        )
        current.metrics["request_throughput_per_second"] = round(
            baseline.metrics["request_throughput_per_second"] * rng.uniform(1.01, 1.10), 3
        )
        current.metrics["waiting_requests_peak"] = float(rng.randint(18, 55))
        logs = [
            Log(
                timestamp=_timestamp(index),
                level="WARNING",
                message=f"scheduler queue waiting requests={int(current.metrics['waiting_requests_peak'])}",
            )
        ]
        supported = ["等待队列增加", "TTFT P95上升", "吞吐接近平台期"]
        forbidden += ["GPU算力不足已确认", "max_num_seqs是唯一根因"]
        ambiguity = ["max_num_seqs是否为主要约束需控制变量复测"]
    elif scenario == "context_limit":
        expected, cause = "config", "input_exceeds_model_limit"
        limit = rng.choice((2048, 4096, 8192))
        observed = limit * rng.choice((2, 4, 8))
        current.config.update(max_model_len=limit, observed_input_tokens=observed)
        current.metrics["success_rate"] = round(rng.uniform(0.2, 0.7), 2)
        logs = [
            Log(
                timestamp=_timestamp(index),
                level="ERROR",
                message=f"input length {observed} exceeds max_model_len {limit}",
            )
        ]
        supported = ["输入长度超过配置上限", "请求成功率下降"]
        forbidden += ["增加上下文后显存一定安全", "已排除共存资源风险"]
        ambiguity = ["调整上限后的显存与延迟尚未复测"]
    elif scenario == "kv_cache_pressure":
        expected, cause = "oom", "kv_cache_pressure_candidate"
        current.concurrency = rng.randint(20, 48)
        current.context_size = rng.choice((8192, 16384))
        current.metrics["gpu_memory_peak_mib"] = round(rng.uniform(14500, 15900), 1)
        current.metrics["preemptions"] = float(rng.randint(5, 30))
        current.metrics["ttft_p95_seconds"] = round(
            baseline.metrics["ttft_p95_seconds"] * rng.uniform(2, 5), 3
        )
        logs = [
            Log(
                timestamp=_timestamp(index),
                level="WARNING",
                message=f"KV cache pressure; preemptions={int(current.metrics['preemptions'])}",
            )
        ]
        supported = ["KV Cache压力与抢占被观测", "显存峰值接近容量"]
        forbidden += ["内存泄漏已确认", "降低gpu_memory_utilization一定改善"]
        ambiguity = ["输入长度、并发及缓存配置共同变化，单一根因未隔离"]
    elif scenario == "external_memory_contention":
        expected, cause = "oom", "external_gpu_process_candidate"
        current.metrics["gpu_memory_peak_mib"] = round(rng.uniform(15000, 16200), 1)
        current.metrics["success_rate"] = round(rng.uniform(0.45, 0.8), 2)
        other = rng.randint(2200, 4800)
        logs = [
            Log(
                timestamp=_timestamp(index),
                level="WARNING",
                message=f"external GPU process observed memory_mib={other}",
            ),
            Log(
                timestamp=_timestamp(index + 1),
                level="ERROR",
                message="CUDA out of memory: allocation failed",
            ),
        ]
        supported = ["出现CUDA OOM", "观察到外部GPU进程占用"]
        forbidden += ["服务自身内存泄漏已确认"]
        ambiguity = ["外部占用与OOM存在关联，隔离复测前不确认因果"]
    elif scenario == "telemetry_missing":
        expected, cause = "unknown", "telemetry_incomplete"
        current.metrics["gpu_memory_peak_mib"] = None
        current.metrics["ttft_p95_seconds"] = None
        current.metrics["success_rate"] = round(rng.uniform(0.7, 0.95), 2)
        logs = [
            Log(
                timestamp=_timestamp(index),
                level="WARNING",
                message="metrics exporter timeout; partial sample",
            )
        ]
        supported = ["遥测不完整", "成功率低于基线"]
        forbidden += ["OOM已排除", "延迟正常", "根因已经确定"]
        ambiguity = ["缺少TTFT与显存数据，无法确定原因类别"]
    elif scenario == "conflicting_evidence":
        expected, cause = "oom", "oom_symptom_root_unknown"
        current.metrics["gpu_memory_peak_mib"] = round(rng.uniform(3000, 6000), 1)
        current.metrics["success_rate"] = round(rng.uniform(0.5, 0.8), 2)
        logs = [
            Log(
                timestamp=_timestamp(index),
                level="ERROR",
                message="CUDA out of memory: transient allocation failure",
            )
        ]
        supported = ["日志记录CUDA OOM", "聚合显存峰值与日志冲突"]
        forbidden += ["低聚合显存排除了OOM", "采样误差已确认"]
        ambiguity = ["可能存在采样遗漏、进程重启或瞬时峰值，尚未区分"]
    elif scenario == "mixed_queue_oom":
        expected, cause = "unknown", "multiple_simultaneous_faults"
        current.concurrency = rng.randint(24, 48)
        current.metrics.update(
            ttft_p95_seconds=round(baseline.metrics["ttft_p95_seconds"] * 6, 3),
            e2e_p95_seconds=round(baseline.metrics["e2e_p95_seconds"] * 3, 3),
            gpu_memory_peak_mib=round(rng.uniform(15500, 16300), 1),
            success_rate=round(rng.uniform(0.4, 0.75), 2),
            waiting_requests_peak=float(rng.randint(12, 40)),
        )
        waiting = int(current.metrics["waiting_requests_peak"])
        logs = [
            Log(
                timestamp=_timestamp(index),
                level="WARNING",
                message=f"scheduler queue waiting requests={waiting}",
            ),
            Log(
                timestamp=_timestamp(index + 1),
                level="ERROR",
                message="CUDA out of memory: allocation failed",
            ),
        ]
        supported = ["排队与OOM同时出现", "无法用单一原因解释全部现象"]
        forbidden += ["唯一根因是排队", "唯一根因是显存不足"]
        ambiguity = ["需分别隔离并发和显存预算变量"]
    else:
        expected, cause = "normal", "no_observed_regression"
        for key in (
            "ttft_p95_seconds",
            "e2e_p95_seconds",
            "request_throughput_per_second",
            "gpu_memory_peak_mib",
        ):
            current.metrics[key] = round(baseline.metrics[key] * rng.uniform(0.98, 1.02), 3)
        supported = ["已记录指标未出现明显退化"]
        forbidden += ["系统绝对无风险", "没有日志即可排除故障"]
        ambiguity = ["合成短窗口不能代表长期生产稳定性"]

    case_id = f"syn-{split[:3]}-{scenario.replace('_', '-')}-{index:02d}"
    descriptions = {
        "queue_saturation": "并发升高后首Token延迟明显上升，请判断是否存在排队。",
        "context_limit": "部分长请求被拒绝，请检查上下文与服务配置。",
        "kv_cache_pressure": "显存接近上限并出现抢占，请分析候选原因。",
        "external_memory_contention": "服务出现OOM，同时观测到其他GPU进程，请分析。",
        "telemetry_missing": "成功率下降但部分遥测缺失，请避免猜测根因。",
        "conflicting_evidence": "OOM日志与聚合显存指标矛盾，请解释证据边界。",
        "mixed_queue_oom": "排队和OOM同时出现，请避免强行给出唯一根因。",
        "normal_control": "检查本次记录是否存在异常，证据不足时说明限制。",
    }
    # The agent-facing case deliberately keeps ``expected`` unknown. Ground truth lives only
    # in labels.json and is joined by the evaluator after the run.
    case = Case(
        id=case_id,
        description=descriptions[scenario],
        synthetic=True,
        baseline=baseline,
        current=current,
        logs=logs,
        expected="unknown",
    )
    label = {
        "case_id": case_id,
        "split": split,
        "scenario": scenario,
        "expected_category": expected,
        "root_cause_rubric": cause,
        "required_tools": required,
        "supported_claims": supported,
        "forbidden_claims": forbidden,
        "ambiguities": ambiguity,
        "agent_visible": False,
    }
    return Generated(case, label)


def generate_split(split):
    count = SPLIT_COUNTS[split]
    per_scenario = count // len(SCENARIOS)
    return [
        make_generated(split, scenario, index)
        for scenario in SCENARIOS
        for index in range(per_scenario)
    ]


def validate_generated(rows):
    issues, ids = [], set()
    for row in rows:
        case, label = row.case, row.label
        if case.id in ids:
            issues.append({"case_id": case.id, "reason": "duplicate_id"})
        ids.add(case.id)
        if not case.synthetic or label["agent_visible"]:
            issues.append({"case_id": case.id, "reason": "visibility_or_provenance"})
        if label["case_id"] != case.id or case.expected != "unknown":
            issues.append({"case_id": case.id, "reason": "label_mismatch"})
        serialized = case.model_dump_json()
        hidden_values = (
            label["root_cause_rubric"],
            *label["supported_claims"],
            *label["forbidden_claims"],
        )
        if any(value in serialized for value in hidden_values):
            issues.append({"case_id": case.id, "reason": "hidden_label_leak"})
        if label["scenario"] == "normal_control" and case.logs:
            issues.append({"case_id": case.id, "reason": "normal_has_logs"})
        if (
            label["scenario"] == "context_limit"
            and case.current.config["observed_input_tokens"] <= case.current.config["max_model_len"]
        ):
            issues.append({"case_id": case.id, "reason": "invalid_context_relation"})
        if label["scenario"] == "queue_saturation" and (
            case.current.metrics["waiting_requests_peak"] <= 0
            or case.current.concurrency <= case.baseline.concurrency
        ):
            issues.append({"case_id": case.id, "reason": "invalid_queue_relation"})
        if label["scenario"] == "mixed_queue_oom":
            waiting = int(case.current.metrics["waiting_requests_peak"])
            if f"waiting requests={waiting}" not in " ".join(log.message for log in case.logs):
                issues.append({"case_id": case.id, "reason": "queue_log_metric_mismatch"})
    return issues
