from __future__ import annotations

from pathlib import Path
from typing import Any

from coredoc.backends.base import Doctor
from coredoc.backends.utils import command_fact, sev_from_findings
from coredoc.models import DoctorResult, Finding, Severity
from coredoc.runner import CommandRunner


class CleanDoctor(Doctor):
    module = "clean"
    title = "Clean Doctor"

    def __init__(self, app_name: str = "", runner: CommandRunner | None = None) -> None:
        super().__init__(runner=runner)
        self.app_name = app_name.strip()

    def _candidates(self) -> list[str]:
        if not self.app_name:
            return []
        names = {self.app_name, self.app_name.lower(), self.app_name.replace(" ", "-").lower()}
        roots = [Path.home() / ".config", Path.home() / ".local/share", Path.home() / ".cache"]
        found: list[str] = []
        for root in roots:
            if not root.exists():
                continue
            for child in root.iterdir():
                if child.name.lower() in names or self.app_name.lower() in child.name.lower():
                    found.append(str(child))
        return sorted(set(found))

    def gather(self) -> DoctorResult:
        facts: dict[str, Any] = {
            "app_name": self.app_name,
            "quarantine_dir": str(Path.home() / ".local/share/coredoc/quarantine"),
        }
        findings: list[Finding] = []
        if not self.app_name:
            findings.append(
                Finding(
                    "clean.no_app",
                    "No application selected",
                    Severity.INFO,
                    "Enter an application name to inspect package footprint and user leftovers.",
                )
            )
            return DoctorResult(
                self.module, self.title, "No app selected", Severity.INFO, facts, findings, []
            )
        dpkg = self.runner.run(["dpkg-query", "-L", self.app_name])
        rpm = self.runner.run(["rpm", "-ql", self.app_name])
        pacman = self.runner.run(["pacman", "-Ql", self.app_name])
        flatpak = self.runner.run(["flatpak", "info", self.app_name])
        facts.update(
            {
                "dpkg_files": command_fact(dpkg),
                "rpm_files": command_fact(rpm),
                "pacman_files": command_fact(pacman),
                "flatpak_info": command_fact(flatpak),
            }
        )
        candidates = self._candidates()
        facts["leftover_candidates"] = candidates
        managers = [
            name
            for name, res in [
                ("dpkg", dpkg),
                ("rpm", rpm),
                ("pacman", pacman),
                ("flatpak", flatpak),
            ]
            if not res.missing and res.returncode == 0
        ]
        if managers:
            findings.append(
                Finding(
                    "clean.installed",
                    "Installed footprint found",
                    Severity.INFO,
                    f"The app appears installed via: {', '.join(managers)}.",
                    advice=[
                        "Use the distro package manager for package removal, then quarantine user leftovers with coredoc."
                    ],
                )
            )
        else:
            findings.append(
                Finding(
                    "clean.not_installed",
                    "No package-manager footprint found",
                    Severity.WARN,
                    "The app name was not found through common package managers.",
                    advice=[
                        "It may be an AppImage, manually installed binary, differently named package, or already removed."
                    ],
                )
            )
        if candidates:
            findings.append(
                Finding(
                    "clean.leftovers",
                    "User data candidates found",
                    Severity.WARN,
                    "coredoc found config/cache/data paths that match the app name.",
                    evidence=candidates[:10],
                    advice=[
                        "Use quarantine rather than delete. Review paths before moving anything."
                    ],
                    fix_id="quarantine_leftovers",
                )
            )
        autostart = Path.home() / ".config/autostart"
        autostarts = []
        if autostart.exists():
            for p in autostart.glob("*.desktop"):
                try:
                    text = p.read_text(encoding="utf-8", errors="replace").lower()
                except OSError:
                    continue
                if self.app_name.lower() in text or self.app_name.lower() in p.name.lower():
                    autostarts.append(str(p))
        facts["autostarts"] = autostarts
        if autostarts:
            findings.append(
                Finding(
                    "clean.autostart",
                    "Matching autostart entries found",
                    Severity.WARN,
                    "The app appears in user autostart entries.",
                    evidence=autostarts,
                    advice=["Disable or quarantine the autostart file if the app was removed."],
                )
            )
        return DoctorResult(
            self.module,
            self.title,
            "Uninstall leftovers inspected",
            sev_from_findings(findings),
            facts,
            findings,
            ["quarantine_leftovers"],
        )
