from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DiagnosisStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class Evidence(BaseModel):
    source: str
    kind: str
    summary: str
    reference: str | None = None
    confidence: float = Field(ge=0, le=1)


class Finding(BaseModel):
    title: str
    severity: str
    explanation: str
    evidence: list[Evidence] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class DiagnosisTask(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    service_name: str
    question: str
    status: DiagnosisStatus = DiagnosisStatus.pending
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    findings: list[Finding] = Field(default_factory=list)
