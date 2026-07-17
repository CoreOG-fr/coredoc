from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from coredoc.models import DoctorResult, Severity


@dataclass(frozen=True)
class TriageAction:
    id: str
    title: str
    description: str
    safety: str
    command: list[str] = field(default_factory=list)
    modules: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "safety": self.safety,
            "command": self.command,
            "modules": self.modules,
        }


@dataclass(frozen=True)
class RootCause:
    id: str
    title: str
    summary: str
    severity: Severity
    confidence: float
    impact: float
    affected_modules: list[str]
    evidence: list[str]
    actions: list[TriageAction] = field(default_factory=list)

    def score(self) -> float:
        sev_weight = {
            Severity.ERROR: 100.0,
            Severity.WARN: 70.0,
            Severity.UNKNOWN: 45.0,
            Severity.INFO: 20.0,
            Severity.OK: 0.0,
        }[self.severity]
        return (
            sev_weight
            + (self.confidence * 20.0)
            + (self.impact * 20.0)
            + len(self.affected_modules)
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "impact": self.impact,
            "affected_modules": self.affected_modules,
            "evidence": self.evidence,
            "actions": [a.as_dict() for a in self.actions],
            "score": self.score(),
        }


@dataclass(frozen=True)
class GlobalDiagnosis:
    summary: str
    severity: Severity
    root_causes: list[RootCause]
    action_plan: list[TriageAction]
    warning_banners: list[str]
    doctor_results: dict[str, DoctorResult]

    def as_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "severity": self.severity.value,
            "root_causes": [r.as_dict() for r in self.root_causes],
            "action_plan": [a.as_dict() for a in self.action_plan],
            "warning_banners": self.warning_banners,
            "doctor_results": {k: v.as_dict() for k, v in self.doctor_results.items()},
        }
