import pytest

from diagnosis_agent.agents.quality import audit_report


@pytest.mark.parametrize(
    "text,code",
    [
        ("当前已排除OOM风险", "unsupported_exclusion"),
        ("将并发限制为4.2 QPS", "check_units"),
        ("故障已修复", "unexecuted_repair"),
    ],
)
def test_known_failure_patterns(text, code):
    issues = audit_report({"conclusion": text, "recommendations": [], "verification": []})
    assert issues[0]["code"] == code


def test_caveat_is_not_positive_exclusion():
    assert not audit_report(
        {"conclusion": "现有日志无法排除OOM风险", "recommendations": [], "verification": []}
    )


@pytest.mark.parametrize(
    "text",
    [
        "监控调整后GPU显存峰值是否接近16GB上限，排除OOM风险",
        "在相同配置下逐步增加并发（如8, 16, 24），观察QPS拐点与延迟变化关系",
    ],
)
def test_observed_false_positives_are_planned_verification(text):
    assert not audit_report(
        {"conclusion": "待验证的候选原因", "recommendations": [], "verification": [text]}
    )


def test_negated_exclusion_does_not_hide_an_unexecuted_repair():
    issues = audit_report(
        {"conclusion": "无法排除OOM风险，但故障已修复", "recommendations": [], "verification": []}
    )
    assert issues[0]["code"] == "unexecuted_repair"


def test_not_equivalent_to_exclusion_is_a_caveat():
    assert not audit_report(
        {"conclusion": "排队存在不等于已排除计算瓶颈", "recommendations": [], "verification": []}
    )
