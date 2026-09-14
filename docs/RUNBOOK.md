# 运行、故障排查与复现

## 可选神经检索容器

先准备本地BGE embedding和reranker模型snapshot目录，在Linux/WSL终端设置只读挂载路径：

```bash
export EMBEDDING_MODEL_DIR=/your/cache/embedding-snapshot
export RERANKER_MODEL_DIR=/your/cache/reranker-snapshot
docker compose -f docker-compose.yml -f docker-compose.neural.yml up --build -d
```

它与默认Compose共用PostgreSQL/Redis/runtime卷，工作台仍为18080。首次构建下载CPU PyTorch及sentence-transformers依赖，耗时和磁盘占用显著增加；模型本体不进入镜像。默认轻量模式不需要这些模型。神经可选依赖尚未提供完整哈希锁定，不承诺未来版本完全相同。

打包安装时应设置 `PROJECT_ROOT` 为包含 frontend 和 evaluation-results 的项目根目录，Docker已设为 `/app`。首页404但health正常时优先核对此配置，不要据此关闭浏览器安全保护。

## 复现实测上下文错误

使用 `backend/scripts/measure_local.py`，显式传入自己已有的 `--server`、`--model` 和一个尚不存在的 `--output` 目录；分别以 `--context 512` 和 `--context 2048` 运行。脚本会占用本机18082并在结束时关闭自己启动的CPU推理进程。请先确认该端口空闲。它不是Agent可自行调用的生产工具。

`verify_local_case.py` 把512上下文实测错误导入独立runtime并调用真实模型；该步骤有模型费用。`summarize_local.py` 从两次结果生成可公开的脱敏复测摘要。见各脚本 `--help`。原日志可能包含本机文件路径，不应直接发布。

## 配置

把根目录 `.env.example` 复制到 `backend/.env`，填写兼容 Chat Completions 的模型地址、Key、模型名。不要在网页输入模型 Key，不要提交 `.env`。

默认绑定本机。WEB_API_KEY 留空仅适合单用户回环访问；设置后在网页“访问口令”输入相同值。不得把开发用数据库密码直接用于公网。

Docker 启动：`docker compose up --build -d`。健康状态：`docker compose ps`。应用日志：`docker compose logs --tail 50 app`。不要运行会输出整个含密钥配置的 `docker compose config` 并分享截图。

Windows 安装 Docker Desktop 或在 WSL 使用 Docker Engine 均可。本项目在 WSL Ubuntu + Docker Engine 上进行容器验证；Windows 的 localhost 端口转发异常时先在 WSL 内检查健康接口，不必立即修改防火墙或开放公网。

本机 WSL 演示可运行 `.\scripts\run-compose-wsl.ps1` 并保持终端运行，避免 WSL 空闲退出一起停止容器。默认发行版可通过 `-Distro` 修改。当前演示使用隐藏保活进程，不创建系统开机任务；重启电脑后需要重新启动。

## 神经检索

原生环境安装：

```powershell
.venv\Scripts\python.exe -m pip install -e 'backend[neural]'
$env:RAG_BACKEND='neural'
$env:EMBEDDING_MODEL='BAAI/bge-small-zh-v1.5'
$env:RERANKER_MODEL='BAAI/bge-reranker-base'
.venv\Scripts\python.exe scripts/build_knowledge.py
.\scripts\run-api.ps1
```

首次需要下载模型，也可以将两个模型变量设为已有本地模型目录。开发验证仅只读复用了原项目模型缓存。模型文件不上传 GitHub。

轻量 Docker 镜像没有包含 PyTorch/模型权重，默认 lexical。需要容器神经模式时增加 `pip install ./backend[neural]` 镜像构建步骤、挂载模型缓存并设 RAG_BACKEND；这不是默认镜像已经提供的功能。原生神经模式与真实 MCP 已单独端到端验证。

## 运行测试

```powershell
.\scripts\test.ps1
.venv\Scripts\python.exe -m diagnosis_agent.evaluation.run --full --count 1 --output evaluation-results/recheck
.venv\Scripts\python.exe backend/scripts/summarize_evaluation.py evaluation-results/recheck
```

普通 pytest 使用假模型、真实 MCP 和临时 SQLite，不收费。evaluation.run 使用真实模型，会收费。count=1 是 4 个模板；count=3 是 12 个合成变体，不能当成 12 个独立真实事故。

## 导入数据

模板：`data/fixtures/example-case.json`。网页支持 1 MB 以下 JSON，包含 baseline/current/logs。改变案例 ID 可避免冲突；同 ID 导入返回 409，不覆盖旧证据。

原始 Benchmark/RAG 结果不应直接作为 Case 上传；通过 `tools/service.py:benchmark_adapter` 与 `tools/adapters.py` 只读适配后组合 Case。比较前核对条件和测量单位。未测量值填 null，不能填 0 假装测过。

## 故障码与处理

| 错误 | 处理 |
|---|---|
| missing_api_key / model_http_401 | 在本地配置正确凭证并重启；不要无限重试 |
| model_http_403 / 404 | 核对模型权限、工作空间地址及模型名 |
| model_timeout_or_rate_limit | 已有限重试；等待供应商恢复后点击重试任务 |
| budget_exhausted | 检查预算、预留账本与账单；经本人决定提高额度，不自动绕过 |
| context_budget_exceeded | 缩短输入和证据；不能声称支持无限日志 |
| unsupported_citation / missing_evidence | 查看草稿与证据；不接受无依据结果 |
| incomplete_tool_coverage | 模型没完成必要取证；保留轨迹后重试 |
| tool_timeout | 查看 MCP stderr、加载模型和调用耗时 |
| needs_attention | 打开历史任务，先理解错误，再恢复；不要重复狂点 |

Redis 故障会降级读数据库。PostgreSQL 故障需要恢复数据库；后台任务依赖它，不应谎报成功。服务重启后任务表仍在；running 超过租约后可接管。不得删除 runtime 或数据库卷来“修复”问题。

## 公开展示

GitHub 用来展示代码、README、原始评测和截图。GitHub Pages 不能直接运行 FastAPI/PostgreSQL。面试现场可以本机打开工作台，或录屏。公网在线版需要另行配置托管、HTTPS、认证、费用限额；不能把个人 API Key 发给访客。
