# 发布验收：工程原型，不是生产事故覆盖承诺

最新挑战集更新：新增96例确定性Synthetic v2、隐藏标签隔离和冻结8类抽样；自动测试93项。第二轮抽样7/8类别命中、5/8通过证据门禁，详见[SYNTHETIC_DATASET.md](SYNTHETIC_DATASET.md)。数据是开发者合成、测试不是独立盲评，不能宣称生产准确率。

此前逐条证据核对更新：默认增加模型辅助的片段级核对、覆盖/引用约束和程序时间差校验，当时自动测试78项。详见[GROUNDING.md](GROUNDING.md)，以下56/42项均为历史批次。核对模型仍有误报，不能宣称零幻觉。

后续质量修订更新：增加一次有上限的模型修订与重新审计，并增加输出截断恢复，自动化测试增至56项。历史失败、误报和新增开发挑战均保留，详见[QUALITY_REPAIR.md](QUALITY_REPAIR.md)。以下42项测试及release-smoke数字是首次发布记录，不是新版本统计。

## 本轮交付内容

- 修正已观察到的规则误报：未来验证动作不等于已经排除风险；观察QPS与并发关系不等于量纲混用；否定语句不作为肯定断言。
- 模型在限定轮次内漏取证时，编排器仅补全query_logs/query_metrics/compare_runs三个只读、当前case范围内工具。日志标记mandatory_evidence_fallback，不把系统补全计为模型自主决策能力。
- 42项自动测试通过，增加工具遗漏恢复和误报回归。Linux/远程验收另外记录，不从Windows结果推断。
- 真实RTX3050上运行0.8B模型，日志记录25/25层GPU卸载；相同1201token输入在512上下文拒绝、2048接受。实验未制造GPU OOM，也不是vLLM/SGLang验证。GPU设备级采样不是分配器峰值。
- 知识语料增至11份简短笔记，来源和小规模检索检查见KNOWLEDGE_SOURCES.md。
- 提供不调用大模型的静态公开回放，展示已保存报告、执行事件、证据和复测。它不能实时诊断用户问题；完整Agent仍在本机Compose运行。

## 评测必须连同失败一起看

recovery-v2是开发过程中的16任务回归：多Agent组4/4完成，整体13/16完成。该批运行期间语料有更新，不作为严格RAG消融或跨版本性能对比。

release-smoke为代码冻结后的4任务验收，manifest记录源代码SHA256且source_unchanged=true。四个类别均命中，但其中1份报告存在“无OOM日志即可排除显存不足”的不充分推断，被规则标记needs_attention；3个自动完成。保留原报告而不删掉失败案例。不能承诺零幻觉、100%自动完成或多Agent一定更好。

## 公开发布与隐私

2026-09-14：公开仓库及静态回放已发布并实际打开验证。首次发布提交b97e3dd的GitHub Actions checks（34855524783）和replay-pages（34855524781）均成功。Windows与干净Linux容器各42项测试通过；Linux原始结果见evaluation-results/release-smoke/container-tests.xml。最终神经检索容器的端到端任务完成，记录见evaluation-results/release-neural；该任务使用合成OOM案例、真实检索与模型调用，不是真实GPU OOM事故。

- 仓库：https://github.com/lzj-23/llm-agent-diagnosis-platform
- 静态回放：https://lzj-23.github.io/llm-agent-diagnosis-platform/
- 最新提交的测试状态以仓库Actions为准；上述运行编号对应首次发布，不冒充后续提交的测试记录。

用户已授权公开仓库及官方GitHub CLI登录。发布使用GitHub隐私邮箱和干净的发布快照，避免把原开发提交中的私人邮箱公开。本地main保留实际开发历史；公开快照不伪造过往提交时间或开发次数。runtime、本机.env、权重和未脱敏服务日志均不发布。

## 仍不宣称的能力

真实GPU OOM与生产事故覆盖、多租户隔离、线上容量与SLA、自动修复、安全审计、统计显著的RAG/多Agent优势。这些不是通过多跑几个合成模板就能补齐的结论。公网回放不等于公网实时Agent部署。
