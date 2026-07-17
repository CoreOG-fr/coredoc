from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    OK = "ok"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Finding:
    id: str
    title: str
    severity: Severity
    summary: str
    evidence: list[str] = field(default_factory=list)
    advice: list[str] = field(default_factory=list)
    fix_id: str | None = None
    confidence: float | None = None
    impact: float | None = None
    safety: str | None = None
    tags: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "severity": self.severity.value,
            "summary": self.summary,
            "evidence": self.evidence,
            "advice": self.advice,
            "fix_id": self.fix_id,
            "confidence": self.confidence,
            "impact": self.impact,
            "safety": self.safety,
            "tags": self.tags,
        }


@dataclass(frozen=True)
class DoctorResult:
    module: str
    title: str
    summary: str
    severity: Severity
    facts: dict[str, Any] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "title": self.title,
            "summary": self.summary,
            "severity": self.severity.value,
            "facts": self.facts,
            "findings": [f.as_dict() for f in self.findings],
            "actions": self.actions,
        }
