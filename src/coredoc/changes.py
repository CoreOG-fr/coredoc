from __future__ import annotations

import json
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from coredoc.doctors.base import BaseDoctor, lines
from coredoc.guidance import since_footer


@dataclass(frozen=True)
class ChangeReport:
    timeframe: str
    summary: str
    facts: dict[str, Any] = field(default_factory=dict)
    changes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "timeframe": self.timeframe,
            "summary": self.summary,
            "facts": self.facts,
            "changes": self.changes,
            "warnings": self.warnings,
        }


class ChangeDetector(BaseDoctor):
    module = "changes"
    title = "Change Detector"

    def __init__(self, timeframe: str = "last-boot") -> None:
        self.timeframe = timeframe

    def run_report(self) -> ChangeReport:
        facts: dict[str, Any] = {"kernel": platform.release()}
        warnings: list[str] = []
        changes: list[str] = []
        since_args = self._since_args()
        current = self.cmd(["journalctl", "-b", "-p", "warning", "--no-pager", "-n", "300"])
        previous = self.cmd(["journalctl", "-b", "-1", "-p", "warning", "--no-pager", "-n", "300"])
        facts["current_boot_warnings"] = current.fact()
        facts["previous_boot_warnings"] = previous.fact()
        if current.missing:
            warnings.append("journalctl is not available; journal diff skipped.")
        else:
            cur_lines = lines(current.stdout, 300)
            prev_lines = lines(previous.stdout, 300) if not previous.missing else []
            new_count = max(0, len(cur_lines) - len(prev_lines))
            changes.append(
                f"Current boot has {len(cur_lines)} warning/error lines; previous boot has {len(prev_lines)}. Delta: {new_count}."
            )
            new_patterns = sorted(
                set(self._normalize(line) for line in cur_lines)
                - set(self._normalize(line) for line in prev_lines)
            )
            changes.extend(f"New log pattern: {p}" for p in new_patterns[:8])
        apt_history = self._apt_history(since_args)
        facts["apt_history"] = apt_history
        if apt_history:
            changes.append(
                f"APT history has {len(apt_history)} relevant lines for {self.timeframe}."
            )
            changes.extend(apt_history[:12])
        if not changes:
            changes.append("No obvious changes found with available data.")
        return ChangeReport(
            self.timeframe, f"Change scan for {self.timeframe} complete", facts, changes, warnings
        )

    def run(self):  # type: ignore[no-untyped-def]
        raise NotImplementedError("Use run_report() for change detection")

    def _since_args(self) -> str:
        mapping = {
            "last-boot": "last boot",
            "today": "today",
            "yesterday": "yesterday",
            "24h": "24 hours ago",
            "1h": "1 hour ago",
        }
        return mapping.get(self.timeframe, self.timeframe)

    def _apt_history(self, since: str) -> list[str]:
        del since
        paths = [Path("/var/log/apt/history.log"), Path("/var/log/dpkg.log")]
        out: list[str] = []
        for path in paths:
            text = self.read_file(path, 50000)
            if text:
                out.extend(
                    line
                    for line in text.splitlines()[-80:]
                    if any(
                        k in line
                        for k in [
                            "Install:",
                            "Upgrade:",
                            "Remove:",
                            " install ",
                            " upgrade ",
                            " remove ",
                        ]
                    )
                )
        return out[:80]

    @staticmethod
    def _normalize(line: str) -> str:
        return " ".join(line.split()[3:])[-180:].lower() if line.split() else line.lower()


def report_to_text(report: ChangeReport) -> str:
    rows = [report.summary, "", "Changes:"]
    rows.extend(f"- {change}" for change in report.changes)
    if report.warnings:
        rows.append("")
        rows.append("Warnings:")
        rows.extend(f"- {warning}" for warning in report.warnings)
    rows.append("")
    rows.append(since_footer())
    return "\n".join(rows)


if __name__ == "__main__":
    print(json.dumps(ChangeDetector().run_report().as_dict(), indent=2))
