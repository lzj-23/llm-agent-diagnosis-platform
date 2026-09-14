# Synthetic v2：确定性故障挑战集

## 为什么要合成

项目没有获授权的生产事故库，也不应把网上片段或个人日志包装成真实事故。因此 Synthetic v2 用程序生成可复现的因果场景，验证 Agent 是否会取证、处理冲突并遵守结论边界。它是开发者编写的挑战集，不是独立盲测，更不是生产准确率证明。

## 生成方式

生成器位于 `backend/src/diagnosis_agent/evaluation/synthetic.py`。每个案例由固定种子、基线运行、受控变量变化、日志规则和隐藏评分标签组成；同一版本重复生成得到相同 JSON 与 SHA256。

八类场景：

1. `queue_saturation`：提高并发、等待队列和 TTFT，吞吐接近平台期。
2. `context_limit`：输入 token 数超过 `max_model_len`，成功率下降并记录拒绝日志。
3. `kv_cache_pressure`：长上下文与高并发下显存接近容量，并出现抢占。
4. `external_memory_contention`：观察到外部 GPU 进程占用，随后出现 CUDA OOM。
5. `telemetry_missing`：成功率下降，但 TTFT 与显存遥测缺失。
6. `conflicting_evidence`：日志有 OOM，聚合显存峰值却较低，要求解释采样边界。
7. `mixed_queue_oom`：排队、延迟和 OOM 同时出现，不允许强行给出唯一根因。
8. `normal_control`：配置不变、指标只在 2% 内波动且无异常日志。

案例总数为 96：development 48、validation 24、frozen 24，每组在八类场景间均衡。生成命令：

```powershell
$env:PYTHONPATH='backend/src'
.venv\Scripts\python.exe backend/scripts/generate_synthetic_dataset.py
```

输出位于 `data/synthetic-v2/<split>/`：

- `cases.json`：只含 Agent 可使用的描述、日志、指标与配置；`expected` 固定为 `unknown`。
- `labels.json`：期望类别、根因评分提示、必需工具、允许/禁止论断和歧义说明。
- `manifest.json`：案例数、案例哈希、标签哈希和一致性检查结果。

标签不会传入模型或 MCP 工具，只在运行结束后由评测脚本合并。标签文件仍随公开仓库发布，因此 frozen 只表示开发流程中的固定留出集，不是对外保密或第三方独立测试集。

## 自动一致性检查

当前检查包括：ID 唯一、三组互斥、场景均衡、重复生成一致、全部标记 synthetic、标签不出现在工具输出、上下文上限关系正确、排队数值与日志一致、正常对照无故障日志。自动测试不能证明模拟数据符合真实硬件分布。

## 冻结抽样实跑

`evaluate_synthetic_v2.py` 从 frozen 中固定选择每类第一个案例。评测时只把这 8 个 `cases.json` 暂存进私有 runtime，由真实 MCP 子进程读取；运行结束即删除暂存文件。`labels.json` 不进入 Agent 上下文。

```powershell
$env:PYTHONPATH='backend/src'
.venv\Scripts\python.exe backend/scripts/evaluate_synthetic_v2.py \
  --output evaluation-results/synthetic-v2-frozen-smoke-v2
```

2026-09-14 第二轮固定抽样的实际结果：

- 8/8 完成端到端运行，7/8 类别命中；
- 5/8 通过最终证据门禁，3/8 进入 `needs_attention`；
- 8/8 覆盖日志、指标、对比三个必需工具，且本轮均由模型自主选择；
- 精确禁止短语命中 0 次，但这不是语义幻觉率；
- 211,310 tokens，按项目配置价格估算 0.216856 元。

三个被拦截的报告均保留：排队案例把 `max_num_seqs=16` 写成已确定根因；混合故障案例声称可以确认未超过上下文限制，但没有 token 证据；正常案例谈到离线回放，却没有引用对应回放证据。门禁失败不是脚本失败，而是系统拒绝自动放行不充分论断。

第一轮修复前结果也保存在 `evaluation-results/synthetic-v2-frozen-smoke/`：6/8 类别命中、1/8 通过门禁。随后修正了报告精简约束、否定修复语句误报和异常组错误分类；第二轮不覆盖第一轮。

## 解释边界

- 类别命中只比较 `latency/oom/config/normal/unknown`，不证明根因解释正确。
- `mixed_queue_oom` 暴露了单标签分类的歧义：模型选 `oom`，冻结标签为 `unknown`。看到结果后没有改标签；后续版本应另设多症状标签和根因置信度，不能回写本轮分数。
- 温度为 0 也不保证供应商模型逐字复现；确定的是数据与源代码哈希，不是模型响应。
- `required_tool_coverage` 可能包含编排器补全，所以结果另外记录模型自主选择数和 fallback 工具。
- 本轮没有人工逐句盲评，`semantic_rubric_scored=false`；不能报告“幻觉率 0%”。
- 下一步提高外部有效性需要授权脱敏的真实事故、独立标注者、重复运行和跨模型对照。
