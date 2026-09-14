# 十二阶段验收台账

最新补充与对外发布见 RELEASE_STATUS.md；下表是初版里程碑，不覆盖后续实测和失败。

> 本台账中的“通过”均为定义边界内的原型验收，不是生产级保证。最新补充及未覆盖事项以 CONTINUATION_ACCEPTANCE.md 为准；新模型评测包含 needs_attention 和未知分类，不能沿用旧批次100%结果概括项目。

最终范围以本文件及用户确认的十二阶段计划为准；每个阶段须有实际验证记录才标记通过。

| 阶段 | 内容 | 当前状态 | 验收证据 |
|---|---|---|---|
| 1 | 三类故障边界、PRD | 已确认 | 本文件、PRD |
| 2 | 原项目只读盘点 | 通过 | EXISTING_PROJECT_AUDIT；实际结果只读格式适配 |
| 3 | 三角色架构与数据库 | 通过 | SYSTEM_DESIGN、DATABASE_DESIGN 和对应实现 |
| 4 | 六个独立工具 | 通过 | test_tools、test_mcp、test_adapters |
| 5 | 单 Agent 与真实 MCP | 通过 | single-initial 四场景真实模型调用 |
| 6 | Planner/Executor/Reviewer 状态机 | 通过（原型范围） | multi-reviewed、final-ablation 的 plan/tool/draft/review 轨迹 |
| 7 | 工作/会话/历史记忆及 RAG | 通过（小语料） | test_repository、test_vectors；rag-smoke、neural-mcp 四场景 |
| 8 | PostgreSQL/Redis/后台任务 | 通过（单机） | infrastructure.json 八路抢占与租约；container-e2e 重启和缓存停机验证 |
| 9 | 安全/追踪/预算/降级 | 通过（定义边界内） | 预算/429/401/工具重试/注入/引用/OTel 测试；Redis 实际停机 |
| 10 | 演示网页 | 通过 | 浏览器提交 latency-0 并查看完成报告；容器三个场景 HTTP 完成 |
| 11 | 评测与消融 | 通过（合成集） | final-ablation 16 次结果、summary；MANUAL_REVIEW；模型裁判估计另列 |
| 12 | 容器/CI/文档/面试交付 | 本地通过，远程发布未执行 | Linux 干净镜像 30 tests；Compose 三服务；README/RUNBOOK/INTERVIEW；CI 配置未声称远程跑过 |

核心故障：推理延迟异常、显存不足或请求失败、推理参数配置不合理。
不执行任意命令，不修改生产服务器，不自动调参，不训练模型。
replay_case 仅重新运行注册的离线测试案例，绝不执行上传文件里的代码。
模型调用预算按项目控制，初始开发预算上限 10 元，不把账户全部余额视为可消费额度。

## 验收级别与不能外推的结论

本次完成的是可运行、可部署、可演示的工程原型，不是无风险生产系统。先完成基础工具/单 Agent 验证再扩展多 Agent，后期测试继续回归前面阶段。

神经模式在原生环境真实跑通，默认 Compose 为轻量词项检索，不包含大型模型权重。公开数据集是合成模板，不能宣称真实故障准确率；Reviewer 未消除幻觉，已在原始结果中保留。GitHub 发布和公网托管是独立的外部发布动作，当前没有把代码上传到账户或开放公网。
