"""Check the Wayland portal path that screen sharing and sandboxed apps depend on."""

from __future__ import annotations

import json
import os
from pathlib import Path

from coredoc.doctors.base import BaseDoctor, lines
from coredoc.models import DoctorResult, Finding, Severity


class WaylandDoctor(BaseDoctor):
    module = "wayland"
    title = "Wayland Doctor"

    def run(self) -> DoctorResult:
        facts: dict[str, object] = {
            "XDG_SESSION_TYPE": os.environ.get("XDG_SESSION_TYPE"),
            "XDG_CURRENT_DESKTOP": os.environ.get("XDG_CURRENT_DESKTOP"),
            "DESKTOP_SESSION": os.environ.get("DESKTOP_SESSION"),
            "WAYLAND_DISPLAY": os.environ.get("WAYLAND_DISPLAY"),
            "DISPLAY": os.environ.get("DISPLAY"),
        }
        findings: list[Finding] = []
        is_wayland = facts["XDG_SESSION_TYPE"] == "wayland" or bool(facts["WAYLAND_DISPLAY"])
        if not is_wayland:
            findings.append(
                Finding(
                    "wayland.not_wayland",
                    "Current session is not Wayland",
                    Severity.INFO,
                    "Wayland-specific checks are informational because this process is not in a Wayland session.",
                )
            )

        for key, argv in {
            "portal_service": ["systemctl", "--user", "is-active", "xdg-desktop-portal"],
            "pipewire_service": ["systemctl", "--user", "is-active", "pipewire"],
            "wireplumber_service": ["systemctl", "--user", "is-active", "wireplumber"],
            "portal_units": [
                "systemctl",
                "--user",
                "list-units",
                "xdg-desktop-portal*",
                "--no-pager",
            ],
        }.items():
            res = self.cmd(argv)
            facts[key] = res.fact()

        descriptors = sorted(
            str(p) for p in Path("/usr/share/xdg-desktop-portal/portals").glob("*.portal")
        )
        facts["portal_descriptors"] = descriptors
        if is_wayland:
            portal_fact = facts["portal_service"]
            pipe_fact = facts["pipewire_service"]
            if isinstance(portal_fact, dict) and portal_fact["missing"]:
                findings.append(self.missing_tool("systemctl", "Cannot inspect portal services."))
            elif isinstance(portal_fact, dict) and portal_fact["returncode"] != 0:
                findings.append(
                    Finding(
                        "wayland.portal_inactive",
                        "XDG Desktop Portal is not active",
                        Severity.ERROR,
                        "Wayland screen sharing and sandbox portals need xdg-desktop-portal.",
                        evidence=[
                            str(portal_fact.get("stdout", "")),
                            str(portal_fact.get("stderr", "")),
                        ],
                        advice=[
                            "Start or inspect xdg-desktop-portal and the backend for your compositor."
                        ],
                    )
                )
            if isinstance(pipe_fact, dict) and pipe_fact["returncode"] != 0:
                findings.append(
                    Finding(
                        "wayland.pipewire_inactive",
                        "PipeWire is not active",
                        Severity.WARN,
                        "Wayland screen capture normally depends on PipeWire.",
                        advice=["Check: systemctl --user status pipewire wireplumber"],
                    )
                )
            if not descriptors:
                findings.append(
                    Finding(
                        "wayland.no_portal_backend",
                        "No portal backend descriptors found",
                        Severity.WARN,
                        "No files were found under /usr/share/xdg-desktop-portal/portals.",
                        advice=[
                            "Install xdg-desktop-portal-gnome, -kde, -gtk, -wlr, or compositor-specific backend."
                        ],
                    )
                )
            else:
                findings.append(
                    Finding(
                        "wayland.portal_backends",
                        "Portal backend descriptors found",
                        Severity.OK,
                        "Installed portal backend descriptors are visible.",
                        evidence=descriptors[:8],
                    )
                )
            self._check_backend_match(
                str(facts.get("XDG_CURRENT_DESKTOP") or ""), descriptors, findings
            )

        confs = self._portal_configs()
        facts["portal_configs"] = confs
        if len(descriptors) > 2 and not confs and is_wayland:
            findings.append(
                Finding(
                    "wayland.portal_conflict_possible",
                    "Multiple portal backends with no explicit selection",
                    Severity.WARN,
                    "The portal dispatcher may select the wrong backend on non-GNOME/KDE compositors.",
                    evidence=descriptors[:8],
                    advice=[
                        "Consider ~/.config/xdg-desktop-portal/portals.conf if screen sharing fails."
                    ],
                )
            )

        browser_flags = self._browser_flags()
        facts["browser_flags"] = browser_flags
        if browser_flags and not any(
            "wayland" in v.lower() or "pipewire" in v.lower() or "ozone" in v.lower()
            for v in browser_flags.values()
        ):
            findings.append(
                Finding(
                    "wayland.browser_flags",
                    "Browser/Electron flags do not mention Wayland",
                    Severity.INFO,
                    "Older Chromium/Electron builds may need Wayland/PipeWire flags for capture or scaling.",
                    evidence=list(browser_flags),
                )
            )

        journal = self.cmd(["journalctl", "--user", "-b", "--no-pager", "-n", "300"])
        facts["portal_journal"] = journal.fact()
        portal_logs = [
            line
            for line in lines(journal.stdout, 300)
            if any(k in line.lower() for k in ["portal", "pipewire", "screencast"])
        ]
        if journal.missing:
            findings.append(self.missing_tool("journalctl", "Cannot inspect portal logs."))
        elif portal_logs:
            findings.append(
                Finding(
                    "wayland.portal_logs",
                    "Portal/PipeWire log messages found",
                    Severity.INFO,
                    "Recent user journal entries mention portal or PipeWire components.",
                    evidence=portal_logs[:10],
                )
            )

        return self.result("Wayland portal stack inspected", facts, findings)

    def _check_backend_match(
        self, desktop: str, descriptors: list[str], findings: list[Finding]
    ) -> None:
        d = desktop.lower()
        joined = " ".join(descriptors).lower()
        expected = None
        if "gnome" in d:
            expected = "gnome"
        elif "kde" in d or "plasma" in d:
            expected = "kde"
        elif any(x in d for x in ["sway", "wlroots", "river"]):
            expected = "wlr"
        elif "hypr" in d:
            expected = "hyprland"
        if expected and expected not in joined:
            findings.append(
                Finding(
                    "wayland.backend_mismatch",
                    "Likely portal backend is missing",
                    Severity.WARN,
                    f"Desktop/compositor looks like {desktop}, but no {expected} portal descriptor was found.",
                )
            )

    def _portal_configs(self) -> list[str]:
        paths = [Path.home() / ".config/xdg-desktop-portal/portals.conf"]
        paths.extend(Path("/usr/share/xdg-desktop-portal").glob("*-portals.conf"))
        return [str(p) for p in paths if p.exists()]

    def _browser_flags(self) -> dict[str, str]:
        flags: dict[str, str] = {}
        for name in ["chrome-flags.conf", "chromium-flags.conf", "electron-flags.conf"]:
            path = Path.home() / ".config" / name
            text = self.read_file(path, 4000)
            if text is not None:
                flags[str(path)] = text
        return flags


if __name__ == "__main__":
    print(json.dumps(WaylandDoctor().run().as_dict(), indent=2))
