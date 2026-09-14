# Synthetic fixtures

这里仅存放可公开提交的合成日志和脱敏评测样例。不得提交真实 API Key、个人信息、公司内部日志、完整模型输出或两个既有项目的原始数据。

`example-case.json` 是可直接导入的合成案例。完整 fixture 由 `backend/src/diagnosis_agent/tools/fixtures.py` 确定性生成，包含四类、每类三个轻微变体：

1. 正常基线；
2. TTFT 明显升高；
3. CUDA OOM；
4. 上下文长度超过配置限制。

工具失败、输入攻击和预算不足使用自动测试注入，不伪装成真实线上故障。公开评测报告中的模型输出来自本项目合成数据，不是原有项目或公司日志。
