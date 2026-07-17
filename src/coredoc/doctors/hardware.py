"""Show which hardware is visible, controllable, or missing useful Linux support."""

from __future__ import annotations

import json
from pathlib import Path

from coredoc.doctors.base import BaseDoctor, lines
from coredoc.models import DoctorResult, Finding, Severity


class HardwareDoctor(BaseDoctor):
    module = "hardware"
    title = "Hardware Doctor"

    def run(self) -> DoctorResult:
        facts: dict[str, object] = {}
        findings: list[Finding] = []
        for key, argv in {
            "sensors": ["sensors"],
            "fwupd_devices": ["fwupdmgr", "get-devices"],
            "fwupd_updates": ["fwupdmgr", "get-updates"],
            "lspci": ["lspci", "-nnk"],
            "lsusb": ["lsusb"],
            "lsblk": ["lsblk", "-J"],
            "upower_devices": ["upower", "-e"],
            "liquidctl": ["liquidctl", "list"],
            "openrgb": ["openrgb", "--list-devices"],
            "nvidia_smi": [
                "nvidia-smi",
                "--query-gpu=name,power.draw,temperature.gpu",
                "--format=csv,noheader",
            ],
        }.items():
            facts[key] = self.cmd(argv, timeout=8).fact()

        hwmon = self._hwmon()
        facts["hwmon"] = hwmon
        if hwmon:
            findings.append(
                Finding(
                    "hardware.hwmon_visible",
                    "Hardware monitor entries are visible",
                    Severity.OK,
                    "The kernel exposes hwmon sensor/control entries.",
                    evidence=[str(x) for x in hwmon[:10]],
                )
            )
        elif self._fact_missing(facts["sensors"]):
            findings.append(
                self.missing_tool(
                    "sensors", "lm-sensors is not installed; using sysfs fallback only."
                )
            )
        else:
            findings.append(
                Finding(
                    "hardware.no_hwmon",
                    "No hwmon entries found",
                    Severity.INFO,
                    "No hardware monitoring entries were visible in /sys/class/hwmon.",
                )
            )

        sensors_fact = facts["sensors"]
        if (
            isinstance(sensors_fact, dict)
            and not sensors_fact["missing"]
            and sensors_fact["returncode"] == 0
        ):
            findings.append(
                Finding(
                    "hardware.sensors_output",
                    "lm-sensors returned readings",
                    Severity.OK,
                    "The sensors command is working.",
                    evidence=lines(str(sensors_fact["stdout"]), 8),
                )
            )

        lspci_fact = facts["lspci"]
        if isinstance(lspci_fact, dict) and lspci_fact["missing"]:
            findings.append(self.missing_tool("lspci", "PCI driver checks skipped."))
        elif isinstance(lspci_fact, dict):
            no_driver = self._pci_without_driver(str(lspci_fact["stdout"]))
            facts["pci_without_driver"] = no_driver
            if no_driver:
                findings.append(
                    Finding(
                        "hardware.pci_without_driver",
                        "PCI devices may lack kernel drivers",
                        Severity.WARN,
                        "Some PCI device blocks do not show a Kernel driver in use line.",
                        evidence=no_driver[:10],
                    )
                )

        batteries = self._battery_thresholds()
        facts["battery_thresholds"] = batteries
        if batteries:
            exposed = [b for b in batteries if b["threshold_files"]]
            if exposed:
                findings.append(
                    Finding(
                        "hardware.battery_thresholds",
                        "Battery charge threshold controls are exposed",
                        Severity.OK,
                        "The kernel exposes battery charge limit files.",
                        evidence=[str(b) for b in exposed],
                    )
                )
            else:
                findings.append(
                    Finding(
                        "hardware.no_battery_thresholds",
                        "Battery present but no threshold controls found",
                        Severity.INFO,
                        "Charge limiting may be unsupported or require a vendor kernel module.",
                    )
                )

        fw = facts["fwupd_devices"]
        if self._fact_missing(fw):
            findings.append(self.missing_tool("fwupdmgr", "Firmware-update visibility skipped."))
        elif isinstance(fw, dict) and fw["returncode"] == 0:
            findings.append(
                Finding(
                    "hardware.fwupd_available",
                    "fwupd can query devices",
                    Severity.OK,
                    "Firmware update metadata is accessible.",
                )
            )
        elif isinstance(fw, dict):
            findings.append(
                Finding(
                    "hardware.fwupd_error",
                    "fwupd returned an error",
                    Severity.WARN,
                    "Firmware update discovery failed.",
                    evidence=[str(fw.get("stderr", ""))],
                )
            )

        for tool, key in [
            ("liquidctl", "liquidctl"),
            ("openrgb", "openrgb"),
            ("nvidia-smi", "nvidia_smi"),
        ]:
            if self._fact_missing(facts[key]):
                findings.append(
                    Finding(
                        f"hardware.no_{tool.replace('-', '_')}",
                        f"{tool} is not installed",
                        Severity.INFO,
                        f"Optional hardware-control tool {tool} is unavailable.",
                    )
                )
        dmidecode = self.cmd(["dmidecode", "-t", "system"])
        facts["dmidecode_system"] = dmidecode.fact()
        if dmidecode.returncode != 0 and not dmidecode.missing:
            findings.append(
                Finding(
                    "hardware.dmidecode_needs_root",
                    "DMI system details need elevated access",
                    Severity.INFO,
                    "dmidecode could not read system DMI details as the current user.",
                    evidence=[dmidecode.stderr.strip()],
                )
            )
        return self.result("Hardware control surface inspected", facts, findings)

    def _hwmon(self) -> list[dict[str, object]]:
        out = []
        for root in Path("/sys/class/hwmon").glob("hwmon*"):
            item = {
                "name": self.read_file(root / "name") or root.name,
                "fans": len(list(root.glob("fan*_input"))),
                "pwms": len(list(root.glob("pwm*"))),
                "temps": len(list(root.glob("temp*_input"))),
            }
            out.append(item)
        return out

    def _battery_thresholds(self) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for bat in Path("/sys/class/power_supply").glob("BAT*"):
            out.append(
                {
                    "battery": bat.name,
                    "threshold_files": [p.name for p in bat.glob("charge_control_*_threshold")],
                }
            )
        return out

    @staticmethod
    def _fact_missing(fact: object) -> bool:
        return isinstance(fact, dict) and bool(fact.get("missing"))

    @staticmethod
    def _pci_without_driver(text: str) -> list[str]:
        blocks = [b for b in text.split("\n\n") if b.strip()]
        interesting = []
        for block in blocks:
            first = block.splitlines()[0] if block.splitlines() else ""
            if (
                any(
                    k in first.lower()
                    for k in ["vga", "3d", "network", "ethernet", "audio", "bluetooth"]
                )
                and "Kernel driver in use:" not in block
            ):
                interesting.append(first)
        return interesting


if __name__ == "__main__":
    print(json.dumps(HardwareDoctor().run().as_dict(), indent=2))
