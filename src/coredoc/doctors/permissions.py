"""List the places local apps can gain access or start themselves automatically."""

from __future__ import annotations

import json
from pathlib import Path

from coredoc.doctors.base import BaseDoctor, lines
from coredoc.models import DoctorResult, Finding, Severity


class PermissionsDoctor(BaseDoctor):
    module = "permissions"
    title = "Permissions Doctor"

    def run(self) -> DoctorResult:
        findings: list[Finding] = []
        facts: dict[str, object] = {}
        for key, argv in {
            "flatpak_apps": ["flatpak", "list", "--app", "--columns=application,name,origin"],
            "flatpak_permissions": ["flatpak", "permissions"],
            "flatpak_overrides": ["flatpak", "override", "--show"],
            "user_units": [
                "systemctl",
                "--user",
                "list-unit-files",
                "--type=service",
                "--no-pager",
            ],
        }.items():
            facts[key] = self.cmd(argv, timeout=8).fact()

        if self._missing(facts["flatpak_apps"]):
            findings.append(self.missing_tool("flatpak", "Flatpak permission checks skipped."))
        else:
            apps = lines(str(self._stdout(facts["flatpak_apps"])), 1000)
            facts["flatpak_app_count"] = len(apps)
            findings.append(
                Finding(
                    "permissions.flatpak_apps",
                    "Flatpak applications inspected",
                    Severity.INFO,
                    f"Found {len(apps)} Flatpak apps.",
                )
            )
            broad = self._broad_flatpak(str(self._stdout(facts["flatpak_overrides"])))
            facts["broad_flatpak_overrides"] = broad
            if broad:
                findings.append(
                    Finding(
                        "permissions.broad_flatpak_overrides",
                        "Broad Flatpak overrides found",
                        Severity.WARN,
                        "Some Flatpak overrides grant broad host access.",
                        evidence=broad[:10],
                        advice=["Review with Flatseal or flatpak override --show."],
                    )
                )

        autostarts = self._desktop_files(
            [Path.home() / ".config/autostart", Path("/etc/xdg/autostart")]
        )
        dbus_user = self._paths([Path.home() / ".local/share/dbus-1/services"])
        dbus_system = self._paths(
            [Path("/usr/share/dbus-1/services"), Path("/usr/share/dbus-1/system-services")]
        )
        polkit_custom = self._paths([Path("/etc/polkit-1/rules.d")])
        portal_stores = self._paths(
            [
                Path.home() / ".local/share/flatpak/db",
                Path.home() / ".local/share/xdg-desktop-portal",
            ]
        )
        facts.update(
            {
                "autostarts": autostarts,
                "dbus_user_services": dbus_user,
                "dbus_system_services_sample": dbus_system[:100],
                "polkit_custom_rules": polkit_custom,
                "portal_stores": portal_stores,
            }
        )
        if autostarts:
            missing_exec = self._autostart_missing_exec(autostarts)
            findings.append(
                Finding(
                    "permissions.autostarts",
                    "Autostart entries found",
                    Severity.INFO,
                    f"Found {len(autostarts)} autostart desktop files.",
                    evidence=autostarts[:8],
                )
            )
            if missing_exec:
                findings.append(
                    Finding(
                        "permissions.autostart_missing_exec",
                        "Autostarts reference missing executables",
                        Severity.WARN,
                        "Some autostart entries may point to removed apps.",
                        evidence=missing_exec[:8],
                    )
                )
        if dbus_user:
            findings.append(
                Finding(
                    "permissions.user_dbus_services",
                    "User DBus activatable services found",
                    Severity.WARN,
                    "User DBus service files can launch programs on demand.",
                    evidence=dbus_user[:8],
                )
            )
        if polkit_custom:
            findings.append(
                Finding(
                    "permissions.custom_polkit_rules",
                    "Custom Polkit rules found",
                    Severity.WARN,
                    "Custom rules in /etc/polkit-1/rules.d can grant privileged actions.",
                    evidence=polkit_custom[:8],
                )
            )
        units = (
            lines(str(self._stdout(facts["user_units"])), 1000)
            if not self._missing(facts["user_units"])
            else []
        )
        enabled = [line for line in units if "enabled" in line.lower()]
        facts["enabled_user_units"] = enabled[:100]
        if enabled:
            findings.append(
                Finding(
                    "permissions.enabled_user_units",
                    "Enabled systemd user services found",
                    Severity.INFO,
                    f"Found {len(enabled)} enabled user-service entries.",
                    evidence=enabled[:8],
                )
            )
        if portal_stores:
            findings.append(
                Finding(
                    "permissions.portal_stores",
                    "Portal permission stores exist",
                    Severity.INFO,
                    "Portal/Flatpak permission database paths are present.",
                    evidence=portal_stores[:8],
                )
            )
        return self.result("Permission surfaces inspected", facts, findings)

    def _desktop_files(self, roots: list[Path]) -> list[str]:
        return [str(p) for root in roots if root.exists() for p in root.glob("*.desktop")][:300]

    def _paths(self, roots: list[Path]) -> list[str]:
        return [str(p) for root in roots if root.exists() for p in root.glob("*")][:300]

    def _autostart_missing_exec(self, paths: list[str]) -> list[str]:
        missing = []
        for path in paths:
            text = self.read_file(path, 10000) or ""
            exec_line = next(
                (
                    line.split("=", 1)[1].strip()
                    for line in text.splitlines()
                    if line.startswith("Exec=")
                ),
                "",
            )
            exe = exec_line.split()[0] if exec_line else ""
            if exe and "/" not in exe and self.cmd(["which", exe]).returncode != 0:
                missing.append(f"{path}: {exe}")
        return missing

    @staticmethod
    def _broad_flatpak(text: str) -> list[str]:
        return [
            line
            for line in lines(text, 200)
            if any(
                x in line.lower()
                for x in [
                    "filesystem=host",
                    "filesystems=host",
                    "filesystem=home",
                    "session-bus",
                    "system-bus",
                    "device=all",
                    "devel",
                ]
            )
        ]

    @staticmethod
    def _missing(fact: object) -> bool:
        return isinstance(fact, dict) and bool(fact.get("missing"))

    @staticmethod
    def _stdout(fact: object) -> str:
        return str(fact.get("stdout", "")) if isinstance(fact, dict) else ""


if __name__ == "__main__":
    print(json.dumps(PermissionsDoctor().run().as_dict(), indent=2))
