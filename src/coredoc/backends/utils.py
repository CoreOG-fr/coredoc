from __future__ import annotations

from coredoc.models import Finding, Severity
from coredoc.runner import CommandResult


def sev_from_findings(findings: list[Finding]) -> Severity:
    order = {
        Severity.ERROR: 4,
        Severity.WARN: 3,
        Severity.UNKNOWN: 2,
        Severity.INFO: 1,
        Severity.OK: 0,
    }
    if not findings:
        return Severity.OK
    return max((f.severity for f in findings), key=lambda s: order[s])


def lines(text: str, limit: int = 50) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and line.strip() != "-- No entries --"
    ][:limit]


def command_fact(res: CommandResult) -> dict[str, object]:
    return {
        "argv": list(res.argv),
        "returncode": res.returncode,
        "missing": res.missing,
        "stdout": res.stdout.strip()[:4000],
        "stderr": res.stderr.strip()[:1000],
    }
