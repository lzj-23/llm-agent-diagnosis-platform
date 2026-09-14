"""Conservative report lint, not a semantic correctness classifier."""

import re


def audit_report(report):
    findings = []
    fields = [("conclusion", report["conclusion"])]
    fields += [("recommendation", text) for text in report["recommendations"]]
    fields += [("verification", text) for text in report["verification"]]
    for field, text in fields:
        for sentence in re.split(r"[。；，,\n]", text):
            # Negated exclusions are caveats, not assertions of absence.
            negated = re.search(
                r"(?:无法|不能|不可|不足以|不等于|尚未|未能|未).{0,8}排除", sentence
            )
            planned = (
                field != "conclusion"
                and re.search(r"^(?:建议|需|请|监控|检查|验证|复测|观察|确认|在)", text.strip())
                and not re.search(r"(?:已|已经)排除", sentence)
            )
            if (
                not negated
                and not planned
                and re.search(
                    r"(?:已|可以|能够|可)?排除.{0,16}(?:OOM|显存不足|计算瓶颈|性能退化)",
                    sentence,
                    re.IGNORECASE,
                )
            ):
                findings.append(
                    {
                        "code": "unsupported_exclusion",
                        "quote": sentence,
                        "message": "排除故障需要充分证据，日志缺失或单次指标不足以支持。",
                    }
                )
            if re.search(
                r"并发.{0,8}(?:限制为|设置为|控制在|等于|设为).{0,12}(?:QPS|请求/秒)",
                sentence,
                re.IGNORECASE,
            ) or re.search(
                r"并发(?:数)?.{0,4}(?:高于|低于|大于|小于)\s*QPS", sentence, re.IGNORECASE
            ):
                findings.append(
                    {
                        "code": "check_units",
                        "quote": sentence,
                        "message": "人工核对并发数与请求速率的量纲；两者不能直接等同。",
                    }
                )
            if not re.search(
                r"(?:未|没有|尚未|不能声称).{0,4}(?:修复|已修复|已解决)"
                r"|(?:无法|不能).{0,16}声称已修复",
                sentence,
            ) and re.search(r"(?:已修复|修复成功|已解决故障)", sentence):
                findings.append(
                    {
                        "code": "unexecuted_repair",
                        "quote": sentence,
                        "message": "平台没有执行修复权限，不能声称故障已修复。",
                    }
                )
    return findings
