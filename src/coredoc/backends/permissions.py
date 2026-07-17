from __future__ import annotations

from pathlib import Path
from typing import Any

from coredoc.backends.base import Doctor
from coredoc.backends.utils import command_fact, lines, sev_from_findings
from coredoc.models import DoctorResult, Finding, Severity


class PermissionsDoctor(Doctor):
    module = "permissions"
    title = "Permissions Doctor"

    def _glob_paths(self, pattern: str, limit: int = 100) -> list[str]:
        return [str(p) for p in Path.home().glob(pattern)][:limit]

    def gather(self) -> DoctorResult:
        findings: list[Finding] = []
        facts: dict[str, Any] = {}
        flatpak = self.runner.run(["flatpak", "list", "--app", "--columns=application"])
        overrides = self.runner.run(["flatpak", "override", "--show"])
        user_units = self.runner.run(
            ["systemctl", "--user", "list-unit-files", "--type=service", "--no-pager"]
        )
        facts.update(
            {
                "flatpak_apps": command_fact(flatpak),
                "flatpak_overrides": command_fact(overrides),
                "user_units": command_fact(user_units),
            }
        )
        autostarts = self._glob_paths(".config/autostart/*.desktop")
        portal_grants = self._glob_paths(".local/share/flatpak/db/*") + self._glob_paths(
            ".local/share/xdg-desktop-portal/*"
        )
        dbus_services = self._glob_paths(".local/share/dbus-1/services/*.service")
        polkit_rules = [str(p) for p in Path("/etc/polkit-1/rules.d").glob("*.rules")][:100]
        facts.update(
            {
                "autostarts": autostarts,
                "portal_grants": portal_grants,
                "dbus_services": dbus_services,
                "polkit_rules": polkit_rules,
            }
        )
        if not flatpak.missing and flatpak.returncode == 0:
            apps = lines(flatpak.stdout, 200)
            findings.append(
                Finding(
                    "permissions.flatpak",
                    "Flatpak applications visible",
                    Severity.INFO,
                    f"Found {len(apps)} Flatpak apps.",
                    evidence=apps[:8],
                    advice=[
                        "Review broad filesystem or device permissions with Flatseal or coredoc details."
                    ],
                )
            )
        if overrides.returncode == 0 and overrides.stdout.strip():
            findings.append(
                Finding(
                    "permissions.flatpak_overrides",
                    "Flatpak overrides configured",
                    Severity.WARN,
                    "User or global Flatpak permission overrides are present.",
                    evidence=lines(overrides.stdout, 8),
                    advice=["Confirm each override is intentional."],
                )
            )
        if autostarts:
            findings.append(
                Finding(
                    "permissions.autostart",
                    "User autostart entries found",
                    Severity.INFO,
                    f"Found {len(autostarts)} user autostart files.",
                    evidence=autostarts[:8],
                )
            )
        if dbus_services:
            findings.append(
                Finding(
                    "permissions.dbus_user",
                    "User DBus services found",
                    Severity.INFO,
                    f"Found {len(dbus_services)} user DBus service files.",
                    evidence=dbus_services[:8],
                )
            )
        if polkit_rules:
            findings.append(
                Finding(
                    "permissions.polkit",
                    "System Polkit rules found",
                    Severity.INFO,
                    f"Found {len(polkit_rules)} Polkit rule files.",
                    evidence=polkit_rules[:8],
                )
            )
        if user_units.returncode == 0 and user_units.stdout.strip():
            enabled = [line for line in lines(user_units.stdout, 200) if "enabled" in line]
            if enabled:
                findings.append(
                    Finding(
                        "permissions.user_services",
                        "Enabled user services found",
                        Severity.INFO,
                        f"Found {len(enabled)} enabled user service entries.",
                        evidence=enabled[:8],
                    )
                )
        if not findings:
            findings.append(
                Finding(
                    "permissions.none",
                    "No permission surfaces found",
                    Severity.OK,
                    "No inspected user permission surfaces contained entries.",
                )
            )
        return DoctorResult(
            self.module,
            self.title,
            "Permission surfaces inspected",
            sev_from_findings(findings),
            facts,
            findings,
            [],
        )
