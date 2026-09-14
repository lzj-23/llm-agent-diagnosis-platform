import pytest
from pydantic import ValidationError

from diagnosis_agent.domain.models import DiagnosisTask, Evidence


def test_task_starts_pending() -> None:
    task = DiagnosisTask(service_name="demo-service", question="为什么响应变慢？")

    assert task.status.value == "pending"
    assert task.findings == []


def test_evidence_confidence_is_bounded() -> None:
    with pytest.raises(ValidationError):
        Evidence(source="metric", kind="latency", summary="P95 增长", confidence=1.2)
