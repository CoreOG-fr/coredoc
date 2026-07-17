"""Turn recent warning and error logs into a small set of useful clues."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from typing import Any, cast

from coredoc.doctors.base import BaseDoctor, classify_log_line, lines
from coredoc.models import DoctorResult, Finding, Severity


class LogsDoctor(BaseDoctor):
    module = "logs"
    title = "Logs Doctor"

    def __init__(self, since: str | None = None) -> None:
        self.since = since

    def run(self) -> DoctorResult:
        findings: list[Finding] = []
        facts: dict[str, object] = {"since": self.since}
        argv = ["journalctl", "-b", "-p", "warning", "--no-pager", "-n", "1000", "-o", "short-iso"]
        if self.since:
            argv.extend(["--since", self.since])
        journal = self.cmd(argv, timeout=8)
        facts["journal_warning"] = journal.fact()
        if journal.missing:
            findings.append(
                self.missing_tool(
                    "journalctl", "Falling back to dmesg/traditional logs where possible."
                )
            )
        elif journal.stderr and "not seeing messages" in journal.stderr.lower():
            findings.append(
                Finding(
                    "logs.limited_access",
                    "Journal access is limited",
                    Severity.INFO,
                    "The current user may not see system logs from other users/services.",
                    evidence=[journal.stderr.strip()],
                    advice=[
                        "Add the user to adm or systemd-journal if appropriate, or run with elevated privileges for support collection."
                    ],
                )
            )

        entries = lines(journal.stdout, 1000) if not journal.missing else []
        facts["entry_count"] = len(entries)
        if entries:
            grouped = self._group_by_hour(entries)
            facts["groups_by_hour"] = dict(list(grouped.items())[:24])
            repeated = self._repeated(entries)
            facts["repeated_patterns"] = repeated[:20]
            classes = self._classes(entries)
            facts["classes"] = classes
            if repeated:
                findings.append(
                    Finding(
                        "logs.repeated_patterns",
                        "Repeated log patterns detected",
                        Severity.WARN,
                        "The same warning/error appears multiple times.",
                        evidence=[f"{n}x {msg}" for msg, n in repeated[:10]],
                        advice=["Repeated messages usually point to the highest-value fix."],
                    )
                )
            for title, data in classes.items():
                sev = Severity.ERROR if str(data["severity"]) == "error" else Severity.WARN
                findings.append(
                    Finding(
                        f"logs.{self._slug(title)}",
                        title,
                        sev,
                        f"Detected {data['count']} matching log entries.",
                        evidence=cast(list[str], data["examples"])[:5],
                    )
                )
            if not repeated and not classes:
                findings.append(
                    Finding(
                        "logs.warnings_present",
                        "Recent warnings found",
                        Severity.WARN,
                        f"journalctl returned {len(entries)} warning-or-higher entries.",
                        evidence=entries[:8],
                    )
                )
        else:
            findings.append(
                Finding(
                    "logs.no_warnings",
                    "No warning-or-higher journal entries found",
                    Severity.OK,
                    "No relevant current-boot warnings were found by journalctl.",
                )
            )

        dmesg = self.cmd(["dmesg", "--level=err,warn", "--time-format=iso"], timeout=5)
        facts["dmesg_warn"] = dmesg.fact()
        if dmesg.missing:
            findings.append(self.missing_tool("dmesg", "Kernel warning fallback skipped."))
        elif dmesg.returncode != 0 and dmesg.stderr:
            findings.append(
                Finding(
                    "logs.dmesg_restricted",
                    "Kernel log access is restricted",
                    Severity.INFO,
                    "dmesg could not be read by this user.",
                    evidence=[dmesg.stderr.strip()],
                )
            )
        return self.result("Warning and error logs summarised", facts, findings)

    def _repeated(self, entries: list[str]) -> list[tuple[str, int]]:
        norm = [self._normalize(line) for line in entries]
        return [(msg, count) for msg, count in Counter(norm).most_common(20) if count > 1]

    def _classes(self, entries: list[str]) -> dict[str, dict[str, Any]]:
        classes: dict[str, dict[str, Any]] = {}
        for line in entries:
            classified = classify_log_line(line)
            if not classified:
                continue
            sev, title = classified
            bucket = classes.setdefault(title, {"severity": sev.value, "count": 0, "examples": []})
            bucket["count"] = int(bucket["count"]) + 1
            examples = bucket["examples"]
            if isinstance(examples, list) and len(examples) < 8:
                examples.append(line)
        return classes

    @staticmethod
    def _group_by_hour(entries: list[str]) -> dict[str, int]:
        grouped: dict[str, int] = defaultdict(int)
        for line in entries:
            grouped[line[:13] if len(line) >= 13 else "unknown"] += 1
        return grouped

    @staticmethod
    def _normalize(line: str) -> str:
        line = re.sub(r"^\S+\s+", "", line)
        line = re.sub(r"\bpid=\d+\b|\[\d+\]|\b\d{2,}\b", "#", line.lower())
        return line[-180:]

    @staticmethod
    def _slug(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


if __name__ == "__main__":
    print(json.dumps(LogsDoctor().run().as_dict(), indent=2))
