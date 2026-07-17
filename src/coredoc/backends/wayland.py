from __future__ import annotations

import os
from typing import Any

from coredoc.backends.base import Doctor
from coredoc.backends.utils import command_fact, lines, sev_from_findings
from coredoc.models import DoctorResult, Finding, Severity


class WaylandDoctor(Doctor):
    module = "wayland"
    title = "Wayland Doctor"

    def gather(self) -> DoctorResult:
        findings: list[Finding] = []
        session_type = os.environ.get("XDG_SESSION_TYPE", "unknown")
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "unknown")
        wayland_display = os.environ.get("WAYLAND_DISPLAY")
        facts: dict[str, Any] = {
            "session_type": session_type,
            "desktop": desktop,
            "wayland_display": wayland_display,
        }
        portal = self.runner.run(["systemctl", "--user", "is-active", "xdg-desktop-portal"])
        facts["portal_service"] = command_fact(portal)
        packages = self.runner.run(
            [
                "sh",
                "-c",
                "command -v dpkg >/dev/null && dpkg -l 'xdg-desktop-portal*' 2>/dev/null || true",
            ]
        )
        facts["portal_packages"] = command_fact(packages)
        pw = self.runner.run(["systemctl", "--user", "is-active", "pipewire"])
        facts["pipewire_service"] = command_fact(pw)
        browser_flags = {}
        for name in ["chrome-flags.conf", "chromium-flags.conf", "electron-flags.conf"]:
            path = os.path.expanduser(f"~/.config/{name}")
            if os.path.exists(path):
                try:
                    with open(path, encoding="utf-8", errors="replace") as fh:
                        browser_flags[name] = fh.read()[:2000]
                except OSError as exc:
                    browser_flags[name] = str(exc)
        facts["browser_flags"] = browser_flags

        if session_type != "wayland":
            findings.append(
                Finding(
                    "wayland.not_wayland",
                    "Current session is not Wayland",
                    Severity.INFO,
                    f"XDG_SESSION_TYPE is {session_type}.",
                    advice=[
                        "Wayland-specific screen sharing checks are less relevant in this session."
                    ],
                )
            )
        if portal.missing or portal.returncode != 0:
            findings.append(
                Finding(
                    "wayland.portal_inactive",
                    "XDG Desktop Portal is not active",
                    Severity.WARN,
                    "Screen sharing and sandbox file pickers often need xdg-desktop-portal.",
                    evidence=[portal.stderr or portal.stdout],
                    advice=[
                        "Install and start xdg-desktop-portal plus the backend for your desktop: gnome, kde, gtk, wlr, hyprland, or lxqt."
                    ],
                )
            )
        if pw.missing or pw.returncode != 0:
            findings.append(
                Finding(
                    "wayland.pipewire_inactive",
                    "PipeWire is not active",
                    Severity.WARN,
                    "Wayland screen capture commonly depends on PipeWire.",
                    advice=["Check: systemctl --user status pipewire wireplumber."],
                )
            )
        pkg_text = packages.stdout.lower()
        if (
            session_type == "wayland"
            and packages.returncode == 0
            and "xdg-desktop-portal" not in pkg_text
        ):
            findings.append(
                Finding(
                    "wayland.portal_pkg_missing",
                    "No portal package detected",
                    Severity.WARN,
                    "The package query did not find xdg-desktop-portal packages.",
                    advice=["Install the portal backend matching your compositor."],
                )
            )
        if browser_flags and not any(
            "ozone" in v.lower() or "wayland" in v.lower() for v in browser_flags.values()
        ):
            findings.append(
                Finding(
                    "wayland.browser_flags",
                    "Browser flags do not mention Wayland",
                    Severity.INFO,
                    "Some Chromium/Electron apps need Wayland or PipeWire flags on older builds.",
                    evidence=list(browser_flags),
                    advice=["Only change flags if screen sharing or scaling is broken."],
                )
            )
        journal = self.runner.run(["journalctl", "--user", "-b", "--no-pager", "-n", "80"])
        portal_warnings = [
            line
            for line in lines(journal.stdout, 80)
            if "portal" in line.lower() or "pipewire" in line.lower()
        ]
        facts["portal_warnings"] = portal_warnings[:20]
        if portal_warnings:
            findings.append(
                Finding(
                    "wayland.portal_logs",
                    "Portal/PipeWire log messages found",
                    Severity.INFO,
                    "Recent user journal entries mention portal or PipeWire components.",
                    evidence=portal_warnings[:6],
                )
            )
        return DoctorResult(
            self.module,
            self.title,
            "Wayland and portal state inspected",
            sev_from_findings(findings),
            facts,
            findings,
            ["start_portal"],
        )
