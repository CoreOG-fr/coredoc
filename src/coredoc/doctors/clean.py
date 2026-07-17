"""Find likely app leftovers and suggest quarantine instead of deleting anything."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from coredoc.doctors.base import BaseDoctor, lines
from coredoc.models import DoctorResult, Finding, Severity


class CleanDoctor(BaseDoctor):
    module = "clean"
    title = "Clean Doctor"

    def __init__(self, app_name: str | None = None) -> None:
        self.app_name = (app_name or "").strip()

    def run(self) -> DoctorResult:
        facts: dict[str, object] = {
            "app_name": self.app_name,
            "mode": "targeted" if self.app_name else "overview",
        }
        findings: list[Finding] = []
        packages = self._installed_packages()
        facts["installed_packages_sample"] = packages[:200]
        if not self.app_name:
            findings.append(
                Finding(
                    "clean.overview",
                    "Clean doctor overview mode",
                    Severity.INFO,
                    f"Detected {len(packages)} installed packages/apps from available managers.",
                    advice=[
                        "Pass app_name to scan for specific leftovers, e.g. CleanDoctor('firefox').run()."
                    ],
                )
            )
            facts["common_leftover_roots"] = [str(p) for p in self._roots() if p.exists()]
            return self.result("Uninstall cleanup overview completed", facts, findings)

        names = self._name_variants(self.app_name)
        facts["name_variants"] = sorted(names)
        footprints = self._package_footprints(self.app_name)
        facts["package_footprints"] = footprints
        installed = [
            name
            for name, fact in footprints.items()
            if not fact["missing"] and fact["returncode"] == 0
        ]
        if installed:
            findings.append(
                Finding(
                    "clean.package_installed",
                    "Package-manager footprint found",
                    Severity.INFO,
                    f"The app appears installed through: {', '.join(installed)}.",
                    advice=[
                        "Use the package manager for package removal before quarantining user data."
                    ],
                )
            )
        else:
            findings.append(
                Finding(
                    "clean.package_not_found",
                    "No package-manager footprint found",
                    Severity.INFO,
                    "The app may be removed, manually installed, or named differently.",
                )
            )

        candidates = self._leftover_candidates(names)
        facts["leftover_candidates"] = candidates
        high = [c for c in candidates if int(c["confidence"]) >= 75]
        if high and not installed:
            findings.append(
                Finding(
                    "clean.high_confidence_leftovers",
                    "High-confidence leftovers found for a non-installed app",
                    Severity.WARN,
                    "coredoc found user config/cache/data paths matching the app name.",
                    evidence=[f"{c['confidence']} {c['path']}" for c in high[:10]],
                    advice=["Move to a quarantine directory first; do not delete blindly."],
                )
            )
        elif candidates:
            findings.append(
                Finding(
                    "clean.leftover_candidates",
                    "User data candidates found",
                    Severity.INFO,
                    "Matching config/cache/data paths were found.",
                    evidence=[f"{c['confidence']} {c['path']}" for c in candidates[:10]],
                )
            )

        autostarts = self._desktop_file_matches(
            names, [Path.home() / ".config/autostart", Path("/etc/xdg/autostart")]
        )
        user_units = self._unit_matches(names)
        facts["autostarts"] = autostarts
        facts["user_units"] = user_units
        for label, data in [("autostart", autostarts), ("user service", user_units)]:
            if data:
                findings.append(
                    Finding(
                        f"clean.{label.replace(' ', '_')}",
                        f"Matching {label} entries found",
                        Severity.WARN,
                        f"The app appears in {label} entries.",
                        evidence=[str(x) for x in data[:10]],
                        advice=["Review and quarantine only if the app was removed."],
                    )
                )
        return self.result(
            "Uninstall leftovers inspected", facts, findings, ["quarantine_suggested"]
        )

    def _installed_packages(self) -> list[str]:
        commands = [
            ["dpkg-query", "-W", "-f=${binary:Package}\n"],
            ["rpm", "-qa"],
            ["pacman", "-Qq"],
            ["apk", "info"],
            ["flatpak", "list", "--app", "--columns=application"],
            ["snap", "list"],
        ]
        names: list[str] = []
        for argv in commands:
            res = self.cmd(argv)
            if not res.missing and res.returncode == 0:
                names.extend(lines(res.stdout, 5000))
        return sorted(set(names))

    def _package_footprints(self, app: str) -> dict[str, dict[str, object]]:
        commands = {
            "dpkg": ["dpkg-query", "-L", app],
            "rpm": ["rpm", "-ql", app],
            "pacman": ["pacman", "-Ql", app],
            "apk": ["apk", "info", "-L", app],
            "flatpak": ["flatpak", "info", app],
            "snap": ["snap", "info", app],
        }
        return {name: self.cmd(argv).fact() for name, argv in commands.items()}

    def _roots(self) -> list[Path]:
        return [
            Path.home() / ".config",
            Path.home() / ".local/share",
            Path.home() / ".cache",
            Path.home() / ".var/app",
        ]

    def _leftover_candidates(self, names: set[str]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for root in self._roots():
            if not root.exists():
                continue
            for child in root.iterdir():
                score = self._score(child.name, names, exact_bonus=90)
                if score:
                    out.append(
                        {"path": str(child), "confidence": score, "reason": "XDG path name match"}
                    )
        for child in Path.home().glob(".*"):
            if (
                child.name in [".", ".."]
                or child.is_dir()
                and child.name in [".cache", ".config", ".local"]
            ):
                continue
            score = self._score(child.name.lstrip("."), names, exact_bonus=70)
            if score:
                out.append(
                    {"path": str(child), "confidence": score, "reason": "legacy dotfile match"}
                )
        return sorted(out, key=lambda x: int(x["confidence"]), reverse=True)[:100]

    def _desktop_file_matches(self, names: set[str], roots: list[Path]) -> list[str]:
        matches = []
        for root in roots:
            if not root.exists():
                continue
            for path in root.glob("*.desktop"):
                text = self.read_file(path, 10000) or ""
                hay = f"{path.name}\n{text}".lower()
                if any(name in hay for name in names):
                    matches.append(str(path))
        return matches

    def _unit_matches(self, names: set[str]) -> list[str]:
        roots = [Path.home() / ".config/systemd/user"]
        matches = []
        for root in roots:
            if root.exists():
                for path in root.glob("*.service"):
                    hay = f"{path.name}\n{self.read_file(path, 10000) or ''}".lower()
                    if any(name in hay for name in names):
                        matches.append(str(path))
        units = self.cmd(["systemctl", "--user", "list-unit-files", "--type=service", "--no-pager"])
        for line in lines(units.stdout, 500):
            if any(name in line.lower() for name in names):
                matches.append(line)
        return sorted(set(matches))

    @staticmethod
    def _name_variants(name: str) -> set[str]:
        base = name.lower().strip()
        return {base, base.replace(" ", "-"), base.replace(" ", "_"), base.split(".")[-1]}

    @staticmethod
    def _score(candidate: str, names: set[str], exact_bonus: int) -> int:
        c = candidate.lower()
        if c in names:
            return exact_bonus
        if any(c == name.replace("-", "_") or c == name.replace("_", "-") for name in names):
            return max(75, exact_bonus - 10)
        if any(name and name in c for name in names):
            return 60
        return 0


if __name__ == "__main__":
    print(json.dumps(CleanDoctor(os.environ.get("COREDOC_APP")).run().as_dict(), indent=2))
