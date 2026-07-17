"""Look for the usual reasons a Linux laptop wakes up or drains while asleep."""

from __future__ import annotations

import json
from pathlib import Path

from coredoc.doctors.base import BaseDoctor, lines
from coredoc.models import DoctorResult, Finding, Severity


class SleepDoctor(BaseDoctor):
    module = "sleep"
    title = "Sleep Doctor"

    def run(self) -> DoctorResult:
        findings: list[Finding] = []
        facts: dict[str, object] = {
            "power_state": self.read_file("/sys/power/state"),
            "mem_sleep": self.read_file("/sys/power/mem_sleep"),
            "disk": self.read_file("/sys/power/disk"),
            "wakeup_count": self.read_file("/sys/power/wakeup_count"),
            "batteries": self._batteries(),
        }
        mem_sleep = str(facts.get("mem_sleep") or "")
        if not mem_sleep:
            findings.append(
                Finding(
                    "sleep.no_mem_sleep",
                    "Sleep mode information is unavailable",
                    Severity.INFO,
                    "The kernel did not expose /sys/power/mem_sleep.",
                )
            )
        elif "[s2idle]" in mem_sleep and "deep" in mem_sleep:
            findings.append(
                Finding(
                    "sleep.s2idle_active",
                    "s2idle is active while deep sleep is available",
                    Severity.WARN,
                    "s2idle can drain more battery than deep sleep on some laptops.",
                    evidence=[mem_sleep],
                    advice=[
                        "If battery drains overnight, test deep sleep using your distro's supported kernel parameter method."
                    ],
                )
            )
        elif "[deep]" in mem_sleep:
            findings.append(
                Finding(
                    "sleep.deep_active",
                    "Deep suspend is active",
                    Severity.OK,
                    "The kernel is configured for deep suspend where supported.",
                    evidence=[mem_sleep],
                )
            )
        elif "[s2idle]" in mem_sleep:
            findings.append(
                Finding(
                    "sleep.s2idle_only",
                    "s2idle is the active suspend mode",
                    Severity.INFO,
                    "No deep option appears in mem_sleep; firmware may expose only Modern Standby/S0ix.",
                    evidence=[mem_sleep],
                )
            )

        acpi = self.read_file("/proc/acpi/wakeup", 30000)
        facts["acpi_wakeup"] = acpi
        if acpi:
            enabled = [line for line in lines(acpi, 200) if "*enabled" in line.lower()]
            facts["acpi_wakeup_enabled"] = enabled
            if len(enabled) > 6:
                findings.append(
                    Finding(
                        "sleep.many_acpi_wake_sources",
                        "Many ACPI wake sources are enabled",
                        Severity.WARN,
                        "Unexpected wake sources can cause overnight wakeups or bag drain.",
                        evidence=enabled[:10],
                    )
                )

        usb_wake = self._usb_wakeup()
        facts["usb_wakeup"] = usb_wake
        enabled_usb = [item for item in usb_wake if item.endswith("enabled")]
        if len(enabled_usb) > 5:
            findings.append(
                Finding(
                    "sleep.usb_wakeup_many",
                    "Many USB devices can wake the system",
                    Severity.INFO,
                    "USB wakeups may wake laptops unexpectedly.",
                    evidence=enabled_usb[:10],
                )
            )

        journal = self.cmd(["journalctl", "-b", "-1", "--no-pager", "-n", "500"])
        facts["previous_boot_journal"] = journal.fact()
        if journal.missing:
            findings.append(
                self.missing_tool("journalctl", "Cannot inspect previous suspend/resume logs.")
            )
        else:
            events = [
                line
                for line in lines(journal.stdout, 500)
                if any(
                    k in line.lower()
                    for k in ["suspend", "resume", "wakeup", "acpi", "pm:", "hibernate"]
                )
            ]
            errors = [
                line
                for line in events
                if any(k in line.lower() for k in ["fail", "error", "timeout", "dpm_run_callback"])
            ]
            facts["sleep_events"] = events[:80]
            if errors:
                findings.append(
                    Finding(
                        "sleep.resume_errors",
                        "Suspend/resume errors found",
                        Severity.ERROR,
                        "Previous boot logs contain suspend/resume failures.",
                        evidence=errors[:10],
                    )
                )
            elif events:
                findings.append(
                    Finding(
                        "sleep.resume_events",
                        "Suspend/resume events found",
                        Severity.INFO,
                        "Previous boot contains sleep-related events.",
                        evidence=events[:8],
                    )
                )

        gpu = self._gpu_runtime()
        facts["gpu_runtime"] = gpu
        active_gpus = [x for x in gpu if x.endswith("active")]
        if active_gpus:
            findings.append(
                Finding(
                    "sleep.gpu_runtime_active",
                    "Some GPU PCI devices are runtime-active",
                    Severity.INFO,
                    "Active GPU runtime state can be normal, but may matter for sleep drain on hybrid laptops.",
                    evidence=active_gpus[:8],
                )
            )
        return self.result("Sleep and wake state inspected", facts, findings)

    def _batteries(self) -> list[dict[str, str | None]]:
        out = []
        for bat in Path("/sys/class/power_supply").glob("BAT*"):
            out.append(
                {
                    "name": bat.name,
                    "capacity": self.read_file(bat / "capacity"),
                    "status": self.read_file(bat / "status"),
                }
            )
        return out

    def _usb_wakeup(self) -> list[str]:
        items = []
        for path in Path("/sys/bus/usb/devices").glob("*/power/wakeup"):
            value = self.read_file(path)
            if value:
                items.append(f"{path}: {value}")
        return items[:200]

    def _gpu_runtime(self) -> list[str]:
        pci = self.cmd(["lspci", "-nn"])
        devices = [
            line.split()[0]
            for line in pci.stdout.splitlines()
            if any(k in line.lower() for k in ["vga", "3d controller", "display"])
        ]
        states = []
        for dev in devices:
            path = Path("/sys/bus/pci/devices") / f"0000:{dev}" / "power/runtime_status"
            value = self.read_file(path)
            if value:
                states.append(f"{dev}: {value}")
        return states


if __name__ == "__main__":
    print(json.dumps(SleepDoctor().run().as_dict(), indent=2))
