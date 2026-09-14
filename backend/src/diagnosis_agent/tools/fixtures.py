"""Deterministic synthetic fixtures; no real GPU experiment is claimed."""

from diagnosis_agent.tools.contracts import Case, Log, Run


def make_case(kind: str, variant: int = 0) -> Case:
    metrics = {
        "ttft_p95_seconds": 0.4,
        "e2e_p95_seconds": 2.0,
        "request_throughput_per_second": 4.0,
        "success_rate": 1.0,
        "gpu_memory_peak_mib": 9000.0,
    }
    base = Run(
        id="baseline",
        model="demo-model",
        device="demo-16GB",
        context_size=2048,
        concurrency=4,
        metrics=metrics,
        config={"max_num_seqs": 16, "gpu_memory_utilization": 0.8},
    )
    current = base.model_copy(deep=True)
    current.id = "current"
    logs = []
    descriptions = {
        "latency": "并发升高后 P95 延迟上升，请排查排队与吞吐变化。",
        "oom": "服务出现 CUDA out of memory 和请求失败，请排查显存。",
        "config": "提高上下文长度后请求失败，请检查推理配置。",
        "normal": "检查本次推理实验是否有异常，证据不足时不要猜测。",
    }
    if kind == "latency":
        current.concurrency = 32 + variant
        current.metrics.update(
            ttft_p95_seconds=3.0 + variant / 10,
            e2e_p95_seconds=7.0,
            request_throughput_per_second=4.2,
        )
        logs = [
            Log(
                timestamp="2026-01-01T00:00:01Z",
                level="WARNING",
                message="scheduler queue waiting requests=28",
            )
        ]
    elif kind == "oom":
        current.metrics.update(success_rate=0.65, gpu_memory_peak_mib=15800.0 + variant)
        logs = [
            Log(
                timestamp="2026-01-01T00:00:01Z",
                level="ERROR",
                message="CUDA out of memory: allocation failed",
            )
        ]
    elif kind == "config":
        current.context_size = 32768
        current.metrics.update(success_rate=0.5)
        current.config["max_model_len"] = 2048
        logs = [
            Log(
                timestamp="2026-01-01T00:00:01Z",
                level="ERROR",
                message="input length 32768 exceeds max_model_len 2048",
            )
        ]
    elif kind != "normal":
        raise KeyError(kind)
    return Case(
        id=f"{kind}-{variant}",
        description=descriptions[kind],
        baseline=base,
        current=current,
        logs=logs,
        expected=kind,
    )


def cases() -> dict[str, Case]:
    return {
        c.id: c
        for kind in ("latency", "oom", "config", "normal")
        for v in range(3)
        for c in [make_case(kind, v)]
    }
