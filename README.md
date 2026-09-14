# LLM Agent Diagnosis Platform

一个可本地部署的多 Agent 诊断工作台。输入故障描述和案例数据，Planner 制定取证计划，Executor 通过真实 MCP 调用工具，Reviewer 审核证据，输出候选原因、引用、建议和复测步骤。

定位是**可运行、可评测的工程原型**，不是已经上线运营的生产诊断系统。已接入真实大模型 API；评测主要使用合成数据，另有一次本机 llama.cpp 上下文错误的复现、Agent诊断与受控复测。不能据此宣称真实生产准确率或修复收益。

最新发布验收、GPU实测与尚存限制见 [RELEASE_STATUS](docs/RELEASE_STATUS.md)。早期验收文档保留为历史记录。

- GitHub：<https://github.com/lzj-23/llm-agent-diagnosis-platform>
- 公开回放入口：<https://lzj-23.github.io/llm-agent-diagnosis-platform/>（由Pages工作流部署，不是实时Agent）
- 本机实时工作台：启动Compose后访问 `http://127.0.0.1:18080/`。

## 当前能力

- 三类故障：延迟异常、显存/请求失败、参数配置；另有正常对照。
- 六个独立工具、真实 MCP stdio、模型 Tool Calling、单/多 Agent 对照。
- 工作证据、会话记忆、历史摘要；词项检索基线及可选 BGE 向量检索/CrossEncoder 重排。
- FastAPI 后台任务、幂等提交、PostgreSQL 租约与持久化、Redis 可降级缓存。
- 网页任务提交、执行轨迹、证据、报告下载、历史任务、失败恢复、评测记录。
- 工具白名单、结构化校验、输入拦截、脱敏、预算、重试、OpenTelemetry 本地链路。
- Docker Compose、自动测试、CI 配置、原始评测 JSON/CSV、开发问题与面试材料。

## 快速开始

需要 Docker Engine + Compose。先复制 `.env.example` 为 `backend/.env`，填写 `LLM_API_BASE`、`LLM_API_KEY`、`LLM_MODEL`。兼容 OpenAI Chat Completions 的模型须支持工具调用。仓库不包含密钥；没有密钥仍能运行工具测试，但不能完成模型诊断。

```bash
docker compose up --build -d
docker compose ps
```

启动后访问：

- 工作台：`http://127.0.0.1:18080/`
- API 文档：`http://127.0.0.1:18080/docs`
- 健康检查：`http://127.0.0.1:18080/health`

选择 `latency-0`、`oom-0` 或 `config-0`，点击“开始诊断”。一次任务会调用付费模型，默认预算上限为本运行目录累计预留 10 元。费用是按所配置价格估算，不等于账单。

Windows 原生轻量模式（Python 3.10–3.12，不依赖数据库服务）：

```powershell
.\scripts\bootstrap.ps1
# 用编辑器将 .env.example 另存为 backend/.env 并填写模型参数
.\scripts\test.ps1
.\scripts\run-api.ps1
```

此模式地址为 `http://127.0.0.1:8000/`，数据持久化到 `runtime/tasks.sqlite`。Compose 模式使用 PostgreSQL 和 Redis，不要混淆两者的记录。

停止 Compose 用 `docker compose stop`，再次启动用 `docker compose start`。不要用 `down -v`，它会删除数据库卷。所有服务仅绑定本机回环地址；公网部署还需要 TLS、可靠认证、访问限流和秘密管理。

## 向量检索与评测

默认 `RAG_BACKEND=lexical` 是不下载模型的轻量检索基线，不冒充 Embedding。完整神经检索见 [运行手册](docs/RUNBOOK.md)。

```powershell
.venv\Scripts\python.exe -m diagnosis_agent.evaluation.run --full --count 1 --output evaluation-results/my-run
.venv\Scripts\python.exe backend/scripts/summarize_evaluation.py evaluation-results/my-run
```

这会执行 4 个场景 × 4 种配置，消耗模型额度。原始数据及局限见 [评测说明](docs/EVALUATION.md)，不预先填造质量指标。

## 目录

```text
backend/           FastAPI、Agent、MCP、RAG、数据库与测试
data/fixtures/     可导入的合成案例 JSON
evaluation-results/ 实际运行结果；不是生产事故数据
docs/              架构、验收、运行/演示/面试手册
frontend/          无构建依赖的 HTML/CSS/JavaScript 工作台
scripts/           Windows 开发脚本、知识库构建
runtime/           私有运行记录、预算和链路；不提交 Git
```

## 资料边界

Enterprise RAG 和 AI-Inference-Benchmark 仅作为本机只读数据源。新仓库不会提交其中的源码、模型、日志、隐私数据或固定机器路径。开发阶段使用合成数据；后续通过环境变量显式配置外部目录。

## 当前状态

本次本机的入口、验收数字与客户端限制集中在 [交付说明](docs/DELIVERY.md)。

按阶段查看 [验收台账](docs/STAGE_GATES.md)，按实现查看 [系统设计](docs/SYSTEM_DESIGN.md)，按演示查看 [演示与面试材料](docs/INTERVIEW.md)。GitHub 展示代码不等于免费托管 Python 后端；没有配置个人 API Key 的访客只能查看源码与已保存的演示结果。

开发中的实际问题、排查证据和面试复述持续记录在 [工程过程记录](docs/ENGINEERING_JOURNAL.md)。预期风险单独列出，不作为已经发生的项目经历。
