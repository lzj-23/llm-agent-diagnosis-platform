"""Offline retrieval baseline. Neural embedding/reranking is an optional later backend."""

import math
import re
from collections import Counter

DOCS = [
    {
        "id": "doc-preemption",
        "title": "vLLM KV cache 与抢占",
        "url": "https://docs.vllm.ai/en/v0.12.0/configuration/optimization/",
        "text": "KV cache 不足可导致抢占和重计算。检查 preemption、并发与显存分配。"
        "在资源允许时评估 gpu_memory_utilization 或 tensor_parallel_size，"
        "也可减少 max_num_seqs 或 max_num_batched_tokens，须实测延迟吞吐权衡。",
    },
    {
        "id": "doc-memory",
        "title": "显存故障排查笔记",
        "url": "local://runbooks/memory",
        "text": "CUDA out of memory OOM 显存不足时先查看错误日志及显存峰值，检查并发、"
        "上下文长度与其他进程占用。降低并发后保持模型与输入不变重新测试，不能只凭显存高断定根因。",
    },
    {
        "id": "doc-latency",
        "title": "延迟与排队排查笔记",
        "url": "local://runbooks/latency",
        "text": "TTFT P95 延迟 排队 queue concurrency。并发增加、吞吐接近不变而延迟增大，"
        "提示排队或资源饱和。固定模型、设备、输入长度，对比并发；检查调度日志。",
    },
    {
        "id": "doc-config",
        "title": "配置与输入长度排查笔记",
        "url": "local://runbooks/config",
        "text": "max_model_len context input length 配置 上下文。输入长度超过配置上限会请求失败。"
        "先核对实际输入、模型支持长度和服务上限，再调整输入长度，验证成功率与内存开销。",
    },
]

# Short authored summaries, not copies of vendor documentation. Snapshot dates and
# version scope travel with each retrieved hit; validate against the deployed version.
DOCS += [
    {
        "id": "doc-vllm-prefill",
        "title": "vLLM V1 chunked prefill 权衡",
        "url": "https://docs.vllm.ai/en/v0.12.0/configuration/optimization/#chunked-prefill",
        "version": "vLLM 0.12.0",
        "checked_at": "2026-09-14",
        "text": "chunked prefill将长prefill切块并与decode组批，优先decode。max_num_batched_tokens较小通常利于ITL，较大通常利于TTFT；需按实际模型和GPU复测，不通用于所有负载。",
    },
    {
        "id": "doc-vllm-parallel",
        "title": "vLLM 张量并行与流水并行代价",
        "url": "https://docs.vllm.ai/en/v0.12.0/configuration/optimization/#parallelism-strategies",
        "version": "vLLM 0.12.0",
        "checked_at": "2026-09-14",
        "text": "tensor_parallel_size分片模型权重，可给每卡KV cache留出更多空间，但引入同步开销。pipeline_parallel_size按层分配，可减轻单卡权重占用，同时可能增加延迟。多卡不是无代价的性能提升。",
    },
    {
        "id": "doc-torch-allocated",
        "title": "PyTorch allocated 与 reserved",
        "url": "https://docs.pytorch.org/docs/2.12/notes/cuda.html#memory-management",
        "version": "PyTorch 2.12",
        "checked_at": "2026-09-14",
        "text": "memory_allocated测张量占用，memory_reserved测缓存分配器管理的内存。缓存的未用显存仍可能出现在nvidia-smi中。empty_cache只释放未用缓存，不释放仍被张量占用的显存，不能保证解决OOM。",
    },
    {
        "id": "doc-torch-fragmentation",
        "title": "PyTorch 碎片诊断不能只看峰值",
        "url": "https://docs.pytorch.org/docs/2.12/notes/cuda.html#optimizing-memory-usage-with-pytorch-alloc-conf",
        "version": "PyTorch 2.12",
        "checked_at": "2026-09-14",
        "text": "memory_stats、memory_summary和memory_snapshot用于了解分配模式。max_split_size_mb是native分配器的最后手段，仅在OOM伴随大量inactive split blocks时评估；cudaMallocAsync忽略该设置，且调整可能影响性能。",
    },
    {
        "id": "doc-sglang-prefill",
        "title": "SGLang prefill 与 decode OOM 区分",
        "url": "https://docs.sglang.io/docs/advanced_features/hyperparameter_tuning",
        "version": "unversioned documentation snapshot",
        "checked_at": "2026-09-14",
        "text": "SGLang prefill OOM可评估降低chunked-prefill-size，代价是长输入prefill变慢。decode OOM可评估降低max-running-requests。应先定位失败阶段，再做有界控制变量复测。",
    },
    {
        "id": "doc-sglang-memory",
        "title": "SGLang 静态显存比例",
        "url": "https://docs.sglang.io/docs/advanced_features/hyperparameter_tuning",
        "version": "unversioned documentation snapshot",
        "checked_at": "2026-09-14",
        "text": "mem-fraction-static用于模型权重与KV cache池，仍需给激活和CUDA graph预留空间。降低该比例可能缓解OOM，但会缩小KV池、限制并发和峰值吞吐；不能把提高或降低比例当成无条件修复。",
    },
    {
        "id": "doc-sglang-queue",
        "title": "SGLang 队列与KV缓存观察",
        "url": "https://docs.sglang.io/docs/advanced_features/hyperparameter_tuning",
        "version": "unversioned documentation snapshot",
        "checked_at": "2026-09-14",
        "text": "结合token usage、queue-req与KV cache pool is full的回退日志检查调度。低token usage伴随排队可能过于保守；频繁缓存满回退则可能需要更保守。schedule-conservativeness应结合负载调整。",
    },
]


def tokens(text):
    return re.findall(r"[a-zA-Z_]+|[\u4e00-\u9fff]", text.lower())


def search(query: str, top_k: int = 3) -> dict:
    aliases = {"慢": " latency TTFT queue", "显存": " OOM memory", "配置": " context max_model_len"}
    rewritten = query + "".join(v for k, v in aliases.items() if k in query)
    q = Counter(tokens(rewritten))
    scored = []
    for doc in DOCS:
        d = Counter(tokens(doc["text"]))
        score = sum(q[t] * d[t] for t in q) / max(1, math.sqrt(sum(x * x for x in d.values())))
        if score > 0:
            scored.append({**doc, "score": round(score, 4)})
    scored.sort(key=lambda x: (-x["score"], x["id"]))
    return {
        "query": query,
        "rewritten_query": rewritten,
        "backend": "lexical_baseline",
        "hits": scored[:top_k],
        "empty": not scored,
    }
