from __future__ import annotations

from collections import Counter
from typing import Any

from coredoc.backends.base import Doctor
from coredoc.backends.utils import command_fact, lines, sev_from_findings
from coredoc.models import DoctorResult, Finding, Severity


class LogsDoctor(Doctor):
    module = "logs"
    title = "Logs Doctor"

    def gather(self) -> DoctorResult:
        findings: list[Finding] = []
        journal = self.runner.run(["journalctl", "-b", "-p", "warning", "--no-pager", "-n", "200"])
        facts: dict[str, Any] = {"journal": command_fact(journal)}
        if journal.missing:
            findings.append(
                Finding(
                    "logs.no_journalctl",
                    "journalctl is missing",
                    Severity.WARN,
                    "coredoc cannot read systemd journal entries.",
                )
            )
        elif journal.returncode != 0:
            findings.append(
                Finding(
                    "logs.journal_error",
                    "journalctl failed",
                    Severity.ERROR,
                    "journalctl returned an error.",
                    evidence=[journal.stderr.strip()],
                )
            )
        entries = lines(journal.stdout, 200)
        facts["entry_count"] = len(entries)
        stems = [e.split(":", 3)[-1].strip()[:120] for e in entries]
        repeated = [(msg, n) for msg, n in Counter(stems).most_common(10) if n > 1]
        facts["repeated_patterns"] = repeated
        if entries:
            findings.append(
                Finding(
                    "logs.warnings",
                    "Recent warnings/errors found",
                    Severity.WARN,
                    f"journalctl returned {len(entries)} warning-or-higher entries from this boot.",
                    evidence=entries[:8],
                    advice=["Repeated messages are usually more useful than isolated warnings."],
                )
            )
        if repeated:
            findings.append(
                Finding(
                    "logs.repeated",
                    "Repeated log patterns detected",
                    Severity.WARN,
                    "The same warning appears multiple times.",
                    evidence=[f"{n}x {m}" for m, n in repeated[:8]],
                    advice=["Prioritize repeated patterns when troubleshooting."],
                )
            )
        if not entries and not journal.missing and journal.returncode == 0:
            findings.append(
                Finding(
                    "logs.clean",
                    "No recent warnings",
                    Severity.OK,
                    "No warning-or-higher journal entries were found in the current boot.",
                )
            )
        return DoctorResult(
            self.module,
            self.title,
            "Recent warning logs summarised",
            sev_from_findings(findings),
            facts,
            findings,
            [],
        )
