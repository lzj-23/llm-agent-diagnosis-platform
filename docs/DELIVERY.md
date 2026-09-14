# 首轮本地交付说明（历史快照）

本文保留当时验收结果，不作为当前发布状态；最新状态见 RELEASE_STATUS.md。

> 补充验收见 CONTINUATION_ACCEPTANCE.md：37项Windows/容器测试、真实上下文错误复测、报告质量告警、资源路径修复。下表保留此前批次结果，不代表最新评测所有任务成功。18080首页404已修复并在浏览器验证，旧客户端限制描述仅为历史记录。

## 已交付

- 后端、六工具、真实 Tool Calling/MCP、三角色诊断、工作/会话/历史记忆。
- 词项基线和可选神经 RAG；后者已真实运行 4 个案例。
- 前端、PostgreSQL、Redis、任务幂等、租约恢复、有限重试、预算、安全与链路。
- Windows 测试、Linux 干净容器测试、Docker Compose 和 CI 配置。
- 演示脚本、原始评测、错误案例、开发记录、简历草案与面试追问。

## 本次主要证据

| 验证 | 实测结果 | 文件 |
|---|---|---|
| 自动测试 | Windows 30 项；Linux 30 项 | evaluation-results/unit-tests.xml、container-tests.xml |
| 对照任务 | 16/16 完成，四模板 × 四配置 | evaluation-results/final-ablation/ |
| 单 Agent 平均耗时 | 23.43 秒 | final-ablation/summary.json |
| 多 Agent 平均耗时 | 38.00 秒 | 同上 |
| 神经检索端到端 | 4/4 完成，4 次实际检索 | evaluation-results/neural-mcp/ |
| PostgreSQL 并发 | 8 路不重复抢占、过期接管、旧所有者拒绝写入 | evaluation-results/infrastructure.json |
| 容器端到端 | 延迟、OOM、配置三场景完成 | evaluation-results/container-e2e/ |
| 真实服务重启 | 三条已完成记录保留 | container-e2e/after-restart.json |
| Redis 停机/恢复 | 停机仍可从 PostgreSQL 查询三条记录 | container-e2e/redis-unavailable.json、redis-restored.json |
| 模型裁判 | 16 份、14 份格式/原文校验通过；2 份无效保留 | final-ablation/judge-reviews.json |

所有故障类别命中数字都针对简单合成模板，不能外推真实故障准确率。开发复核发现模型仍有错误推断，见 MANUAL_REVIEW.md。多 Agent 在本次数据上更慢，不能宣称质量显著更好。

## 如何查看

当前已在内置浏览器打开的原生演示入口：`http://127.0.0.1:18081/`，可查看已完成的延迟报告和全部评测文件。

本机 Compose 工作台：`http://127.0.0.1:18080/`，其中 PostgreSQL 保留三个已完成报告。其健康接口、完整任务 API 和重启均已验证，但本次内置浏览器报告 ERR_BLOCKED_BY_CLIENT，未解决该客户端端口限制。因此保留已验证的 18081 原生入口演示；两种模式不共享任务库，不伪装成同一次浏览器容器验证。

若重启电脑导致服务停止，按 RUNBOOK 重新启动。原生轻量开发服务地址是 8000；此前开发验收临时使用过 18081，不与容器数据库共享历史。

## 尚未执行的外部发布

本项目保存在独立本地 Git 仓库，尚未上传 GitHub，也没有公网在线地址。源码发布和云托管属于独立动作；已有模型密钥不应随代码上传。GitHub 公开仓库可展示源码与离线评测，不能自动提供运行中的 Python 服务。

## 边界

不是生产运维系统；不自动修复、不运行上传代码、不训练模型、不承诺零幻觉。默认镜像使用 lexical 模式，神经检索是已验证的原生可选配置。CI 已提供并在本地执行等价测试，不声称 GitHub Actions 已远程通过。进一步产品化要补独立真实事故集、权限隔离、部署认证及运行容量验证。
