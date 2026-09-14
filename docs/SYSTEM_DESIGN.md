# 系统设计与实现边界

## 数据流

浏览器 → FastAPI → PostgreSQL 任务表 → Worker → Planner → Executor ↔ MCP 六工具 → Reviewer → 引用校验 → 持久化报告 → 浏览器。

Redis 缓存任务快照（1 秒 TTL），不是权威队列。后台队列由 PostgreSQL 持久化任务表实现。数据库不可用时不偷偷切换到 SQLite；只有启动时未配置数据库，才显式使用轻量 SQLite 模式。

| 组件 | 实际职责 | 主要文件 |
|---|---|---|
| Web | 提交、轮询、历史、轨迹、报告下载、案例导入 | frontend/ |
| FastAPI | 校验、鉴权、幂等 API、SSE 事件流 | backend/src/diagnosis_agent/api.py |
| Planner | 产生工具取证计划，不输出根因 | agents/engine.py |
| Executor | 真实模型 Tool Calling，最多 6 轮，每轮最多 6 个工具 | agents/engine.py |
| Reviewer | 读取草稿与独立证据，列出 issues 并修订 | agents/engine.py |
| MCP | 独立子进程，stdio JSON-RPC；非函数直接调用冒充 MCP | tools/mcp_server.py、mcp_client.py |
| RAG | 词项基线，或 BGE → SQLite exact cosine Top-10 → CrossEncoder Top-3 | rag/ |
| 存储 | 任务、事件、历史摘要；租约与 fencing | storage/ |
| 可观测性 | 结构化任务事件、父子 OTel spans、用量 | telemetry.py |

三个 Agent 是同一模型的三个独立角色调用，并非三个训练好的模型，也不是并行自治进程。它们具有不同输入和输出契约。Reviewer 可以修改结论，但其判断本身仍可能错误。

## 状态与恢复

任务状态：pending → running → completed / needs_attention。人工点击“重试任务”后 needs_attention → pending。

运行内步骤以事件保存：running、plan、mcp_connected、model/tool、draft、review、completed。任务表与事件表都是可持久化状态；不是只存 Python 内存。

Worker 通过 SELECT FOR UPDATE SKIP LOCKED 抢占 PostgreSQL 任务，租约 90 秒，每 15 秒心跳。原 Worker 失去所有权后不能写结果。中断后重建证据并重新取证；**不保证外部模型调用 exactly-once**，上次响应未知时可能重复调用和计费。现在是“证据检查点恢复”，不是逐 token 精确恢复。

幂等键约束同键同载荷返回原任务，同键不同载荷返回 409。两个 Worker 提供有限并发；尚未做集群容量/高并发压测。

## 工具契约

- query_logs：注册案例日志的脱敏与错误统计。
- query_metrics：携带模型、设备、上下文、并发、prompt、max_tokens 的基线和当前值。
- compare_runs：差值、变化条件、可比性告警，不把相关性当因果。
- replay_case：重跑已注册离线规则，**不会启动 vLLM 或重新测 GPU**。
- search_docs：检索经过人工整理的排障短文，返回来源 ID；只读，无任意网络/文件权限。
- generate_report：校验引用 ID 并组装候选报告。Agent 引用必须来自本任务实际收集证据。

每个工具有 Pydantic 参数契约，禁止未知字段和路径穿越。工具白名单中没有 shell、删库、重启服务或生产配置写入。

## 知识与记忆

工作记忆是当前任务证据；短期记忆是最近同会话 3 条成功诊断摘要；历史记忆从最近 100 条按词项重叠选 2 条。它不是无限上下文或语义向量长期记忆，且只用于单用户工作台。摘要不替代当前证据。

向量库使用 SQLite 保存 float32 向量与文档元数据，以精确余弦扫描检索，小型语料足够，未实现 ANN 大规模索引。切分窗口 300 字符、重叠 60；目前 4 篇短排障资料形成 4 个 chunk，代码支持更长文档切分。不是已有 Enterprise RAG 的全部知识库。

词项基线有有限中文别名改写；神经模式使用原始查询。返回 empty 和检索结果用于失败分析。CrossEncoder 真正计算重排分数，不是名称占位。

## 安全与成本

输入长度/请求体大小控制、同源检查、可选访问口令、危险提示启发式拦截、密钥字段脱敏、引用约束、工具范围限制共同组成边界。Prompt 注入启发式不能保证拦截一切攻击；真正的安全边界是没有危险工具可执行。

API Key 只在后端环境变量中，前端访问口令不是模型 Key。运行历史可能含业务内容，不提交 Git。导入真实日志前需用户确认有权向配置的模型服务发送，并自行检查脱敏完整性。

每次模型请求先在 SQLite 预算账本事务预留费用；失败重试不退回预留。预算按运行目录共享，Compose 与原生各有账本，不是云账户全局余额控制。HTTP 超时 40 秒、瞬态错误最多 3 次；401 不重试。同一个 ModelClient 连续失败进入 30 秒熔断。工具超时 60 秒，可重试失败最多 2 次。

费用价格基于本次使用的 qwen3.8-flash 输入 0.8、输出 2.7 元/百万 token。更换模型须同步修改价格设置/实现，不能把估算当账单。

## 未覆盖的生产工作

没有实时 GPU 采集、生产服务自动修复、多租户隔离、SSO、HA 数据库、迁移框架、备份恢复演练或大规模故障集。前端显示任务进度；SSE 是任务事件流，不是模型 token 流。CI 有自动测试及镜像构建，不包含自动生产部署。工程原型完整不等于已经生产级运营。
