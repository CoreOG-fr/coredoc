from __future__ import annotations

from pathlib import Path
from typing import Any

from coredoc.backends.base import Doctor
from coredoc.backends.utils import command_fact, lines, sev_from_findings
from coredoc.models import DoctorResult, Finding, Severity


class SleepDoctor(Doctor):
    module = "sleep"
    title = "Sleep Doctor"

    def _read(self, path: str) -> str | None:
        try:
            return Path(path).read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            return None

    def gather(self) -> DoctorResult:
        findings: list[Finding] = []
        mem_sleep = self._read("/sys/power/mem_sleep")
        disk = self._read("/sys/power/disk")
        facts: dict[str, Any] = {"mem_sleep": mem_sleep, "disk": disk}
        journal = self.runner.run(["journalctl", "-b", "-1", "--no-pager", "-n", "160"])
        facts["previous_boot_journal"] = command_fact(journal)
        wake_lines = [
            line
            for line in lines(journal.stdout, 160)
            if any(
                k in line.lower()
                for k in ["suspend", "resume", "wakeup", "acpi", "battery", "nvidia", "amdgpu"]
            )
        ]
        facts["sleep_related_events"] = wake_lines[:60]
        usb_wakeup: list[str] = []
        for p in Path("/sys/bus/usb/devices").glob("*/power/wakeup"):
            val = self._read(str(p))
            if val:
                usb_wakeup.append(f"{p}: {val}")
        facts["usb_wakeup"] = usb_wakeup[:100]

        if mem_sleep is None:
            findings.append(
                Finding(
                    "sleep.no_mem_sleep",
                    "Cannot read sleep modes",
                    Severity.UNKNOWN,
                    "The kernel did not expose /sys/power/mem_sleep or coredoc lacks access.",
                )
            )
        elif "[s2idle]" in mem_sleep and "deep" in mem_sleep:
            findings.append(
                Finding(
                    "sleep.s2idle_active",
                    "s2idle is the active suspend mode",
                    Severity.WARN,
                    "s2idle can drain battery faster than deep sleep on some laptops.",
                    evidence=[mem_sleep],
                    advice=[
                        "If your laptop drains overnight, test deep sleep by setting mem_sleep_default=deep or using your distro's supported method."
                    ],
                )
            )
        elif "[deep]" in mem_sleep:
            findings.append(
                Finding(
                    "sleep.deep_active",
                    "Deep sleep is active",
                    Severity.OK,
                    "The kernel is configured to use deep suspend where supported.",
                    evidence=[mem_sleep],
                )
            )
        enabled_usb = [x for x in usb_wakeup if x.endswith("enabled")]
        if len(enabled_usb) > 5:
            findings.append(
                Finding(
                    "sleep.usb_wakeup_many",
                    "Many USB devices can wake the system",
                    Severity.INFO,
                    "USB wakeups can cause overnight resume or bag drain.",
                    evidence=enabled_usb[:8],
                    advice=["Disable wake for devices that should not wake the laptop."],
                )
            )
        if wake_lines:
            findings.append(
                Finding(
                    "sleep.resume_events",
                    "Suspend/resume events found",
                    Severity.INFO,
                    "The previous boot journal contains sleep-related events.",
                    evidence=wake_lines[:8],
                )
            )
        return DoctorResult(
            self.module,
            self.title,
            "Sleep configuration inspected",
            sev_from_findings(findings),
            facts,
            findings,
            [],
        )
