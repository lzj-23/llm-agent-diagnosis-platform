# Frontend

无构建步骤的 HTML/CSS/JavaScript 工作台，由 FastAPI 同源提供。支持任务提交、执行轨迹、基线/当前指标表、证据链、报告下载、历史恢复和评测记录。UI 使用 textContent 渲染模型文本，不使用未过滤的 HTML。页面轮询任务状态；后端另提供 SSE 事件接口。通过 node --check 和真实浏览器任务验证。
