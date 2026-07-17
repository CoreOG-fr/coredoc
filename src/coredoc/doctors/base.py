"""Shared helpers for doctors that read the system and explain what they found."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from coredoc.models import DoctorResult, Finding, Severity


@dataclass(frozen=True)
class CmdResult:
    """Output from a command that coredoc ran without changing the system."""

    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    missing: bool = False
    timed_out: bool = False

    def fact(self, limit: int = 6000) -> dict[str, Any]:
        return {
            "argv": list(self.argv),
            "returncode": self.returncode,
            "missing": self.missing,
            "timed_out": self.timed_out,
            "stdout": self.stdout.strip()[:limit],
            "stderr": self.stderr.strip()[:2000],
        }


class BaseDoctor(ABC):
    """Common base for doctors: run safe commands, read small files, and return findings."""

    module = "base"
    title = "Base Doctor"

    def cmd(self, argv: Sequence[str], timeout: float = 5.0) -> CmdResult:
        """Run a command without a shell, with a timeout and captured output."""
        if not argv:
            raise ValueError("argv must not be empty")
        exe = argv[0]
        if shutil.which(exe) is None:
            return CmdResult(tuple(argv), 127, "", f"missing command: {exe}", missing=True)
        try:
            proc = subprocess.run(
                list(argv),
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = (
                exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "timeout")
            )
            return CmdResult(tuple(argv), 124, stdout, stderr, timed_out=True)
        return CmdResult(tuple(argv), proc.returncode, proc.stdout, proc.stderr)

    def read_file(self, path: str | Path, limit: int = 20000) -> str | None:
        try:
            return Path(path).read_text(encoding="utf-8", errors="replace")[:limit].strip()
        except OSError:
            return None

    def missing_tool(self, tool: str, detail: str = "Some checks were skipped.") -> Finding:
        return Finding(
            f"{self.module}.missing_{tool}",
            f"{tool} is not available",
            Severity.INFO,
            detail,
            advice=[f"Install the package that provides {tool} if you want this check."],
        )

    def result(
        self,
        summary: str,
        facts: dict[str, Any],
        findings: list[Finding],
        actions: list[str] | None = None,
    ) -> DoctorResult:
        if not findings:
            findings = [
                Finding(
                    f"{self.module}.ok",
                    "No obvious problems found",
                    Severity.OK,
                    "The inspected checks did not report a problem.",
                )
            ]
        return DoctorResult(
            self.module,
            self.title,
            summary,
            max_severity(findings),
            facts,
            findings,
            actions or [],
        )

    @abstractmethod
    def run(self) -> DoctorResult:
        """Inspect one part of the system and return evidence-backed findings."""


def lines(text: str, limit: int = 200) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and line.strip() != "-- No entries --"
    ][:limit]


def max_severity(findings: Sequence[Finding]) -> Severity:
    order = {
        Severity.OK: 0,
        Severity.INFO: 1,
        Severity.UNKNOWN: 2,
        Severity.WARN: 3,
        Severity.ERROR: 4,
    }
    return max((f.severity for f in findings), key=lambda s: order[s], default=Severity.OK)


def percent_from_df(value: str) -> int | None:
    match = re.search(r"(\d+)%", value)
    return int(match.group(1)) if match else None


def is_desktop_session() -> bool:
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def classify_log_line(line: str) -> tuple[Severity, str] | None:
    lower = line.lower()
    classes = [
        (Severity.ERROR, "Out-of-memory kill", ["out of memory", "oom-killer", "killed process"]),
        (
            Severity.ERROR,
            "Filesystem or disk I/O error",
            ["i/o error", "ext4-fs error", "xfs", "btrfs error", "no space left"],
        ),
        (
            Severity.WARN,
            "Firmware load failure",
            ["firmware: failed", "direct firmware load", "failed to load firmware"],
        ),
        (
            Severity.WARN,
            "GPU/display warning",
            ["gpu hang", "nvrm", "amdgpu", "i915", "nouveau", "drm"],
        ),
        (
            Severity.WARN,
            "Service failure",
            ["failed to start", "main process exited", "unit failed"],
        ),
        (Severity.WARN, "Network warning", ["netdev watchdog", "link is down", "networkmanager"]),
    ]
    for severity, title, needles in classes:
        if any(needle in lower for needle in needles):
            return severity, title
    return None
