from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, cast

try:
    import tomllib  # type: ignore[import-not-found]
except ModuleNotFoundError:  # Python 3.10 fallback
    tomllib = None

from coredoc.doctors import DOCTORS
from coredoc.models import DoctorResult, Finding, Severity
from coredoc.triage.models import GlobalDiagnosis, RootCause, TriageAction


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    summary: str
    finding_ids: list[str]
    severity: Severity
    confidence: float
    impact: float
    affected_modules: list[str]
    actions: list[TriageAction]


class TriageEngine:
    """Connect findings from different doctors and decide what to check first."""

    def __init__(self, rules_path: str | None = None) -> None:
        self.rules_path = rules_path
        self.rules = self._load_rules()

    def diagnose(self, results: dict[str, DoctorResult] | None = None) -> GlobalDiagnosis:
        doctor_results = results or self.run_doctors()
        findings = [finding for result in doctor_results.values() for finding in result.findings]
        causes = self._match_rules(findings)
        matched_finding_ids = {
            fid
            for rule in self.rules
            for fid in rule.finding_ids
            if any(f.id == fid for f in findings)
        }
        causes.extend(
            self._fallback_causes(
                doctor_results, findings, {c.id for c in causes}, matched_finding_ids
            )
        )
        causes = sorted(causes, key=lambda c: c.score(), reverse=True)
        actions = self._rank_actions(causes)
        banners = self._warning_banners(doctor_results)
        severity = self._global_severity(causes, doctor_results)
        summary = self._summary(severity, causes)
        return GlobalDiagnosis(summary, severity, causes, actions, banners, doctor_results)

    def run_doctors(self, scenario: str | None = None) -> dict[str, DoctorResult]:
        names = self._scenario_doctors(scenario)
        out: dict[str, DoctorResult] = {}
        for name in names:
            cls = DOCTORS[name]
            doctor = cls("") if name == "clean" else cls()
            out[name] = doctor.run()
        return out

    def _scenario_doctors(self, scenario: str | None) -> list[str]:
        mapping = {
            "audio": ["core", "audio", "logs", "hardware"],
            "sound": ["core", "audio", "logs", "hardware"],
            "screenshare": ["core", "wayland", "audio", "permissions", "logs"],
            "screen-share": ["core", "wayland", "audio", "permissions", "logs"],
            "sleep": ["core", "sleep", "hardware", "logs"],
            "sleep-drain": ["core", "sleep", "hardware", "logs"],
            "network": ["core", "logs"],
            "system": ["core", "logs"],
            "cleanup": ["core", "clean", "logs"],
            "permissions": ["core", "permissions", "logs"],
            "hardware": ["core", "hardware", "logs"],
        }
        if scenario in mapping:
            return mapping[scenario]
        return list(DOCTORS)

    def _load_rules(self) -> list[Rule]:
        if self.rules_path:
            data = cast(dict[str, Any], _load_toml(Path(self.rules_path).read_text()))
        else:
            text = resources.files("coredoc.triage").joinpath("rules.toml").read_text()
            data = cast(dict[str, Any], _load_toml(text))
        rules = []
        rule_items = cast(list[dict[str, Any]], data.get("rules", []))
        for item in rule_items:
            actions = [
                TriageAction(
                    id=a["id"],
                    title=a["title"],
                    description=a["description"],
                    safety=a["safety"],
                    command=list(a.get("command", [])),
                    modules=list(item.get("affected_modules", [])),
                )
                for a in item.get("actions", [])
            ]
            rules.append(
                Rule(
                    id=item["id"],
                    title=item["title"],
                    summary=item["summary"],
                    finding_ids=list(item.get("finding_ids", [])),
                    severity=Severity(item["severity"]),
                    confidence=float(item["confidence"]),
                    impact=float(item["impact"]),
                    affected_modules=list(item.get("affected_modules", [])),
                    actions=actions,
                )
            )
        return rules

    def _match_rules(self, findings: list[Finding]) -> list[RootCause]:
        by_id = {f.id: f for f in findings}
        causes = []
        for rule in self.rules:
            matched = [by_id[fid] for fid in rule.finding_ids if fid in by_id]
            if not matched:
                continue
            evidence = [f"{f.id}: {f.title} — {f.summary}" for f in matched]
            modules = sorted({f.id.split(".", 1)[0] for f in matched} | set(rule.affected_modules))
            severity = max([rule.severity] + [f.severity for f in matched], key=self._sev_weight)
            causes.append(
                RootCause(
                    rule.id,
                    rule.title,
                    rule.summary,
                    severity,
                    min(1.0, rule.confidence + 0.03 * (len(matched) - 1)),
                    rule.impact,
                    modules,
                    evidence,
                    rule.actions,
                )
            )
        return causes

    def _fallback_causes(
        self,
        results: dict[str, DoctorResult],
        findings: list[Finding],
        existing: set[str],
        matched_finding_ids: set[str],
    ) -> list[RootCause]:
        causes = []
        for finding in findings:
            if (
                finding.id in matched_finding_ids
                or finding.severity in {Severity.OK, Severity.INFO}
                or finding.id.startswith("missing")
            ):
                continue
            rid = f"finding_{finding.id.replace('.', '_')}"
            if rid in existing:
                continue
            module = finding.id.split(".", 1)[0]
            causes.append(
                RootCause(
                    rid,
                    finding.title,
                    finding.summary,
                    finding.severity,
                    getattr(finding, "confidence", 0.65) or 0.65,
                    getattr(finding, "impact", 0.5) or 0.5,
                    [module],
                    [f"{finding.id}: {finding.title} — {finding.summary}"],
                    [],
                )
            )
        if not causes and all(r.severity in {Severity.OK, Severity.INFO} for r in results.values()):
            causes.append(
                RootCause(
                    "no_major_root_cause",
                    "No major root cause found",
                    "The inspected modules did not report an error or warning that needs prioritization.",
                    Severity.OK,
                    0.8,
                    0.1,
                    list(results),
                    [],
                    [],
                )
            )
        return causes

    def _rank_actions(self, causes: list[RootCause]) -> list[TriageAction]:
        seen = set()
        actions = []
        for cause in causes:
            for action in cause.actions:
                if action.id not in seen:
                    actions.append(action)
                    seen.add(action.id)
        return actions

    def _warning_banners(self, results: dict[str, DoctorResult]) -> list[str]:
        banners = []
        for name, result in results.items():
            for finding in result.findings:
                if "missing" in finding.id or "limited" in finding.id or "restricted" in finding.id:
                    banners.append(f"{name}: {finding.title}")
        return banners[:8]

    def _global_severity(
        self, causes: list[RootCause], results: dict[str, DoctorResult]
    ) -> Severity:
        values = [c.severity for c in causes] or [r.severity for r in results.values()]
        return max(values, key=self._sev_weight, default=Severity.OK)

    def _summary(self, severity: Severity, causes: list[RootCause]) -> str:
        if not causes:
            return "No diagnosis available."
        top = causes[0]
        if severity == Severity.ERROR:
            return f"Critical issue first: {top.title}."
        if severity == Severity.WARN:
            return f"Most likely issue to check first: {top.title}."
        return "No high-priority root cause found."

    @staticmethod
    def _sev_weight(severity: Severity) -> int:
        return {
            Severity.OK: 0,
            Severity.INFO: 1,
            Severity.UNKNOWN: 2,
            Severity.WARN: 3,
            Severity.ERROR: 4,
        }[severity]


def diagnosis_to_text(diagnosis: GlobalDiagnosis) -> str:
    lines: list[str] = [diagnosis.summary, "", "Root causes:"]
    for idx, cause in enumerate(diagnosis.root_causes, 1):
        lines.append(f"{idx}. [{cause.severity.value}] {cause.title}")
        lines.append(f"   {cause.summary}")
        if cause.affected_modules:
            lines.append(f"   Affects: {', '.join(cause.affected_modules)}")
        for ev in cause.evidence[:3]:
            lines.append(f"   - {ev}")
    lines.append("")
    lines.append("Action plan:")
    if diagnosis.action_plan:
        for idx, action in enumerate(diagnosis.action_plan, 1):
            cmd = " ".join(action.command) if action.command else "manual"
            lines.append(f"{idx}. [{action.safety}] {action.title}: {action.description} ({cmd})")
    else:
        lines.append("No direct safe action is available; review the root-cause evidence.")
    lines.append("")
    from coredoc.guidance import fix_footer

    lines.append(fix_footer())
    return "\n".join(lines)


def _load_toml(text: str) -> dict[str, object]:
    if tomllib is not None:
        return cast(dict[str, object], tomllib.loads(text))
    return _parse_rules_toml(text)


def _parse_rules_toml(text: str) -> dict[str, object]:
    import ast

    rules: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    current_action: dict[str, object] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line == "[[rules]]":
            current = {"actions": []}
            rules.append(current)
            current_action = None
            continue
        if line == "[[rules.actions]]":
            if current is None:
                continue
            current_action = {}
            actions = current.setdefault("actions", [])
            assert isinstance(actions, list)
            actions.append(current_action)
            continue
        if "=" not in line:
            continue
        key, value_text = [part.strip() for part in line.split("=", 1)]
        try:
            value = ast.literal_eval(value_text)
        except Exception:
            try:
                value = float(value_text)
            except ValueError:
                value = value_text.strip('"')
        target = current_action if current_action is not None else current
        if target is not None:
            target[key] = value
    return {"rules": rules}
