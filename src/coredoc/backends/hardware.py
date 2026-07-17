from __future__ import annotations

from pathlib import Path
from typing import Any

from coredoc.backends.base import Doctor
from coredoc.backends.utils import command_fact, lines, sev_from_findings
from coredoc.models import DoctorResult, Finding, Severity


class HardwareDoctor(Doctor):
    module = "hardware"
    title = "Hardware Doctor"

    def gather(self) -> DoctorResult:
        findings: list[Finding] = []
        facts: dict[str, Any] = {}
        sensors = self.runner.run(["sensors"])
        fwupd = self.runner.run(["fwupdmgr", "get-devices"])
        lspci = self.runner.run(["lspci", "-nn"])
        lsusb = self.runner.run(["lsusb"])
        facts.update(
            {
                "sensors": command_fact(sensors),
                "fwupd": command_fact(fwupd),
                "lspci": command_fact(lspci),
                "lsusb": command_fact(lsusb),
            }
        )
        batteries = []
        for bat in Path("/sys/class/power_supply").glob("BAT*"):
            threshold_files = [p.name for p in bat.glob("charge_*_threshold")]
            batteries.append({"battery": bat.name, "threshold_files": threshold_files})
        facts["batteries"] = batteries
        hwmons = [str(p) for p in Path("/sys/class/hwmon").glob("hwmon*/name")]
        facts["hwmon_names"] = []
        for p in hwmons:
            try:
                facts["hwmon_names"].append(f"{p}: {Path(p).read_text().strip()}")
            except OSError:
                pass
        if sensors.missing:
            findings.append(
                Finding(
                    "hardware.no_sensors",
                    "lm-sensors is not installed",
                    Severity.INFO,
                    "Install lm-sensors to expose temperature and fan sensor summaries.",
                )
            )
        elif sensors.returncode == 0:
            findings.append(
                Finding(
                    "hardware.sensors",
                    "Sensor data available",
                    Severity.OK,
                    "The sensors command returned hardware readings.",
                    evidence=lines(sensors.stdout, 8),
                )
            )
        if fwupd.missing:
            findings.append(
                Finding(
                    "hardware.no_fwupd",
                    "fwupd is not installed",
                    Severity.INFO,
                    "Firmware update discovery is unavailable without fwupd.",
                )
            )
        elif fwupd.returncode == 0:
            findings.append(
                Finding(
                    "hardware.fwupd",
                    "fwupd devices visible",
                    Severity.OK,
                    "Firmware update metadata can be queried.",
                )
            )
        if any(b["threshold_files"] for b in batteries):
            findings.append(
                Finding(
                    "hardware.battery_thresholds",
                    "Battery charge thresholds exposed",
                    Severity.OK,
                    "The kernel exposes battery charge control threshold files.",
                    evidence=[str(b) for b in batteries],
                )
            )
        else:
            findings.append(
                Finding(
                    "hardware.no_battery_thresholds",
                    "No battery threshold controls found",
                    Severity.INFO,
                    "This machine may not support Linux-visible charge limiting, or it may require a vendor module.",
                )
            )
        if lspci.returncode == 0 and any(
            "nvidia" in line.lower() for line in lspci.stdout.splitlines()
        ):
            findings.append(
                Finding(
                    "hardware.nvidia",
                    "NVIDIA hardware detected",
                    Severity.INFO,
                    "Some fan and power controls depend on driver support and may differ between X11 and Wayland.",
                )
            )
        return DoctorResult(
            self.module,
            self.title,
            "Hardware control surface inspected",
            sev_from_findings(findings),
            facts,
            findings,
            [],
        )
