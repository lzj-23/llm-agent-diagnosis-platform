import re


class UnsafeInput(ValueError):
    pass


def sanitize(value):
    if isinstance(value, dict):
        return {
            k: "[REDACTED]"
            if re.search(r"(?i)password|secret|api.?key|authorization|token$", k)
            else sanitize(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    return redact(value) if isinstance(value, str) else value


def redact(text: str) -> str:
    text = re.sub(r"sk-[A-Za-z0-9_-]+", "[REDACTED]", text)
    return re.sub(r"(?i)(authorization|api_key|password)\s*[:=]\s*\S+", r"\1=[REDACTED]", text)


def validate_question(text: str) -> str:
    if len(text) > 2000 or not text.strip():
        raise UnsafeInput("question_length")
    if re.search(
        r"ignore.{0,30}(instruction|previous)|忽略.{0,12}(指令|规则)|"
        r"泄露.{0,10}(密钥|密码)|rm\s+-rf|powershell\s+-enc",
        text,
        re.IGNORECASE,
    ):
        raise UnsafeInput("prompt_injection_detected")
    return redact(text)
