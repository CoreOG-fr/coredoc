"""Check the broad system problems that can explain many smaller failures."""

from __future__ import annotations

import json
import os
from pathlib import Path

from coredoc.doctors.base import BaseDoctor, classify_log_line, lines, percent_from_df
from coredoc.models import DoctorResult, Finding, Severity


class CoreDoctor(BaseDoctor):
    module = "core"
    title = "Core System Doctor"

    def run(self) -> DoctorResult:
        facts: dict[str, object] = {"container": self._container_hint()}
        findings: list[Finding] = []
        self._systemd(facts, findings)
        self._disk(facts, findings)
        self._mounts(facts, findings)
        self._packages(facts, findings)
        self._network(facts, findings)
        self._time(facts, findings)
        self._logs(facts, findings)
        return self.result("Core system health inspected", facts, findings)

    def _systemd(self, facts: dict[str, object], findings: list[Finding]) -> None:
        state = self.cmd(["systemctl", "is-system-running"])
        failed = self.cmd(["systemctl", "--failed", "--no-pager", "--plain"])
        facts["system_state"] = state.fact()
        facts["failed_units"] = failed.fact()
        if state.missing:
            findings.append(self.missing_tool("systemctl", "Systemd boot-state checks skipped."))
            return
        text = state.stdout.strip()
        if text == "running":
            findings.append(
                Finding(
                    "core.system_running",
                    "Systemd reports the system is running",
                    Severity.OK,
                    "systemctl is-system-running returned running.",
                )
            )
        elif self._container_hint():
            findings.append(
                Finding(
                    "core.system_container",
                    "Systemd state is non-running inside a container",
                    Severity.INFO,
                    f"systemctl reported {text or state.stderr.strip()}, which is common in containers.",
                )
            )
        else:
            findings.append(
                Finding(
                    "core.system_degraded",
                    "Systemd does not report a clean running state",
                    Severity.WARN,
                    f"systemctl is-system-running returned: {text or state.stderr.strip()}",
                )
            )
        failed_lines = [line for line in lines(failed.stdout, 100) if "failed" in line.lower()]
        if failed_lines:
            findings.append(
                Finding(
                    "core.failed_units",
                    "Failed systemd units found",
                    Severity.WARN,
                    "Failed units often explain downstream symptoms.",
                    evidence=failed_lines[:15],
                    advice=["Inspect with: systemctl status <unit> and journalctl -u <unit>."],
                )
            )

    def _disk(self, facts: dict[str, object], findings: list[Finding]) -> None:
        for label, argv in {
            "disk_usage": ["df", "-P", "-h"],
            "inode_usage": ["df", "-P", "-i"],
        }.items():
            res = self.cmd(argv)
            facts[label] = res.fact()
            if res.missing:
                findings.append(self.missing_tool("df", f"{label} skipped."))
                continue
            bad: list[str] = []
            warn: list[str] = []
            for line in res.stdout.splitlines()[1:]:
                parts = line.split()
                if len(parts) < 6:
                    continue
                pct = percent_from_df(parts[4])
                if pct is None:
                    continue
                if pct >= 95:
                    bad.append(line)
                elif pct >= 85:
                    warn.append(line)
            if bad:
                findings.append(
                    Finding(
                        f"core.{label}_critical",
                        f"{label.replace('_', ' ').title()} critical",
                        Severity.ERROR,
                        "One or more filesystems are at or above 95% usage.",
                        evidence=bad[:10],
                    )
                )
            if warn:
                findings.append(
                    Finding(
                        f"core.{label}_high",
                        f"{label.replace('_', ' ').title()} high",
                        Severity.WARN,
                        "One or more filesystems are at or above 85% usage.",
                        evidence=warn[:10],
                    )
                )

    def _mounts(self, facts: dict[str, object], findings: list[Finding]) -> None:
        mounts = self.cmd(["findmnt", "-R", "-o", "TARGET,OPTIONS", "-n"])
        facts["mounts"] = mounts.fact()
        if mounts.missing:
            findings.append(self.missing_tool("findmnt", "Read-only mount checks skipped."))
            return
        readonly = []
        for line in mounts.stdout.splitlines():
            parts = line.split(None, 1)
            if (
                len(parts) == 2
                and "ro" in parts[1].split(",")
                and parts[0] in ["/", "/home", "/var"]
            ):
                readonly.append(line)
        if readonly:
            findings.append(
                Finding(
                    "core.readonly_mounts",
                    "Important filesystems are mounted read-only",
                    Severity.ERROR,
                    "A read-only root/home/var mount usually indicates filesystem or recovery-mode trouble.",
                    evidence=readonly,
                )
            )

    def _packages(self, facts: dict[str, object], findings: list[Finding]) -> None:
        checks = [
            ("dpkg_audit", ["dpkg", "--audit"]),
            ("apt_check", ["apt-get", "check"]),
            ("dnf_check", ["dnf", "check"]),
            ("apk_audit", ["apk", "audit"]),
        ]
        for key, argv in checks:
            res = self.cmd(argv, timeout=10)
            facts[key] = res.fact()
            if res.missing:
                continue
            if res.returncode != 0 or lines(res.stdout + res.stderr, 20):
                sev = Severity.ERROR if key in ["dpkg_audit", "apt_check"] else Severity.WARN
                findings.append(
                    Finding(
                        f"core.{key}",
                        "Package manager health issue",
                        sev,
                        f"{' '.join(argv)} reported output or a non-zero exit.",
                        evidence=lines(res.stdout + res.stderr, 10),
                    )
                )
            break

    def _network(self, facts: dict[str, object], findings: list[Finding]) -> None:
        route = self.cmd(["ip", "route", "show", "default"])
        addr = self.cmd(["ip", "-brief", "addr"])
        dns = self.cmd(["getent", "hosts", "example.com"])
        facts.update(
            {"default_route": route.fact(), "ip_brief": addr.fact(), "dns_example": dns.fact()}
        )
        if route.missing:
            findings.append(self.missing_tool("ip", "Network route checks skipped."))
        elif route.returncode == 0 and route.stdout.strip():
            findings.append(
                Finding(
                    "core.default_route",
                    "Default route exists",
                    Severity.OK,
                    "The system has a default network route.",
                    evidence=lines(route.stdout, 3),
                )
            )
        else:
            findings.append(
                Finding(
                    "core.no_default_route",
                    "No default network route found",
                    Severity.WARN,
                    "Internet access may be unavailable or intentionally disabled.",
                )
            )
        if dns.missing:
            findings.append(self.missing_tool("getent", "DNS resolution check skipped."))
        elif dns.returncode != 0:
            findings.append(
                Finding(
                    "core.dns_failed",
                    "DNS resolution failed",
                    Severity.WARN,
                    "getent could not resolve example.com.",
                )
            )

    def _time(self, facts: dict[str, object], findings: list[Finding]) -> None:
        time = self.cmd(
            ["timedatectl", "show", "-p", "NTPSynchronized", "-p", "SystemClockSynchronized"]
        )
        facts["timedatectl"] = time.fact()
        if time.missing:
            findings.append(self.missing_tool("timedatectl", "Time sync check skipped."))
        elif "=no" in time.stdout.lower():
            findings.append(
                Finding(
                    "core.time_unsynced",
                    "System clock is not fully synchronized",
                    Severity.WARN,
                    "timedatectl reports unsynchronized time.",
                    evidence=lines(time.stdout, 5),
                )
            )
        elif time.returncode == 0:
            findings.append(
                Finding(
                    "core.time_synced",
                    "System clock synchronization looks healthy",
                    Severity.OK,
                    "timedatectl did not report unsynchronized state.",
                )
            )

    def _logs(self, facts: dict[str, object], findings: list[Finding]) -> None:
        journal = self.cmd(["journalctl", "-b", "-p", "err", "--no-pager", "-n", "100"])
        kernel = self.cmd(["journalctl", "-k", "-b", "-p", "warning", "--no-pager", "-n", "300"])
        facts.update({"journal_errors": journal.fact(), "kernel_warnings": kernel.fact()})
        if journal.missing:
            findings.append(self.missing_tool("journalctl", "Journal checks skipped."))
            return
        if journal.stderr and "not seeing messages" in journal.stderr.lower():
            findings.append(
                Finding(
                    "core.journal_limited",
                    "Journal access is limited",
                    Severity.INFO,
                    "The current user may not see all system logs.",
                    evidence=[journal.stderr.strip()],
                )
            )
        entries = lines(journal.stdout + "\n" + kernel.stdout, 400)
        for line in entries:
            classified = classify_log_line(line)
            if classified:
                sev, title = classified
                findings.append(
                    Finding(
                        f"core.{title.lower().replace(' ', '_')}",
                        title,
                        sev,
                        "Core logs contain a high-value failure pattern.",
                        evidence=[line],
                    )
                )
                break

    @staticmethod
    def _container_hint() -> bool:
        return Path("/.dockerenv").exists() or bool(os.environ.get("CONTAINER"))


if __name__ == "__main__":
    print(json.dumps(CoreDoctor().run().as_dict(), indent=2))
