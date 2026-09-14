# 排障知识来源与评测范围

2026-09-14核对，代码中的文本是简短中文摘要，不是完整文档副本。检索命中携带来源URL，新摘要同时携带版本及核对日期。

- [vLLM 0.12.0优化文档](https://docs.vllm.ai/en/v0.12.0/configuration/optimization/)：抢占、chunked prefill与并行代价。适用版本需与部署环境核对。
- [PyTorch 2.12 CUDA内存管理](https://docs.pytorch.org/docs/2.12/notes/cuda.html#memory-management)：allocated/reserved、empty_cache边界及分配器诊断。
- [SGLang参数调优](https://docs.sglang.io/docs/advanced_features/hyperparameter_tuning)：prefill/decode OOM、静态显存比例和队列观察。页面未固定发布版本，保留核对日期，不默认适用于所有历史版本。

语料为11份短笔记，其中3份为项目自写的通用排障笔记，另8份引用官方资料。不是11份完整技术手册，也不是大规模知识库。

`evaluation-results/retrieval-v2`包含固定语料SHA256及7条相关性检查。题目直接来自同一语料，不是独立盲测：词项召回Top-3为6/7，神经检索为7/7；MRR@3分别约0.786、0.929。仅用于验证管道与暴露排序差异，不能声称生产效果提升。
