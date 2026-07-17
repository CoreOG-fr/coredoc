from __future__ import annotations

from typing import Any

from coredoc.backends.base import Doctor
from coredoc.backends.utils import command_fact, lines, sev_from_findings
from coredoc.models import DoctorResult, Finding, Severity


class AudioDoctor(Doctor):
    module = "audio"
    title = "Audio Doctor"

    def gather(self) -> DoctorResult:
        findings: list[Finding] = []
        facts: dict[str, Any] = {}
        pactl = self.runner.run(["pactl", "info"])
        facts["pactl_info"] = command_fact(pactl)
        systemctl = self.runner.run(
            ["systemctl", "--user", "is-active", "pipewire", "pipewire-pulse", "wireplumber"]
        )
        facts["user_services"] = command_fact(systemctl)
        sinks = self.runner.run(["pactl", "list", "short", "sinks"])
        sources = self.runner.run(["pactl", "list", "short", "sources"])
        facts["sinks"] = command_fact(sinks)
        facts["sources"] = command_fact(sources)
        journal = self.runner.run(
            ["journalctl", "--user", "-b", "-p", "warning", "--no-pager", "-n", "80"]
        )
        audio_warnings = [
            line
            for line in lines(journal.stdout, 80)
            if any(k in line.lower() for k in ["pipewire", "wireplumber", "pulse", "bluez", "alsa"])
        ]
        facts["recent_audio_warnings"] = audio_warnings

        if pactl.missing:
            findings.append(
                Finding(
                    "audio.pactl_missing",
                    "pactl is not installed",
                    Severity.WARN,
                    "coredoc cannot inspect PulseAudio/PipeWire compatibility state without pactl.",
                    advice=["Install pulseaudio-utils or the distro package that provides pactl."],
                )
            )
        elif pactl.returncode != 0:
            findings.append(
                Finding(
                    "audio.server_unreachable",
                    "Audio server is unreachable",
                    Severity.ERROR,
                    "pactl could not connect to PulseAudio/PipeWire Pulse compatibility service.",
                    evidence=[pactl.stderr.strip()],
                    advice=[
                        "Check whether pipewire-pulse or pulseaudio is running.",
                        "Try: systemctl --user status pipewire pipewire-pulse wireplumber",
                    ],
                )
            )
        elif "PipeWire" in pactl.stdout:
            findings.append(
                Finding(
                    "audio.pipewire",
                    "PipeWire audio server detected",
                    Severity.OK,
                    "PipeWire is responding through pactl.",
                )
            )
        elif "Server Name: PulseAudio" in pactl.stdout:
            findings.append(
                Finding(
                    "audio.pulseaudio",
                    "PulseAudio is active",
                    Severity.INFO,
                    "The system is using PulseAudio rather than PipeWire Pulse compatibility.",
                    advice=[
                        "This is fine if intentional. If Wayland screen sharing or modern Bluetooth routing fails, check PipeWire migration docs for your distro."
                    ],
                )
            )

        if not sinks.missing and sinks.returncode == 0 and not lines(sinks.stdout):
            findings.append(
                Finding(
                    "audio.no_sinks",
                    "No output devices visible",
                    Severity.ERROR,
                    "The audio server reported no sinks.",
                    advice=[
                        "Check ALSA devices with aplay -l.",
                        "Look for missing firmware or muted hardware in dmesg.",
                    ],
                )
            )
        if not sources.missing and sources.returncode == 0 and not lines(sources.stdout):
            findings.append(
                Finding(
                    "audio.no_sources",
                    "No input devices visible",
                    Severity.WARN,
                    "The audio server reported no sources.",
                    advice=[
                        "If you expect a microphone, check Bluetooth headset profile and privacy toggles."
                    ],
                )
            )
        if audio_warnings:
            findings.append(
                Finding(
                    "audio.recent_warnings",
                    "Recent audio warnings found",
                    Severity.WARN,
                    "journalctl contains recent audio-related warnings.",
                    evidence=audio_warnings[:8],
                    advice=["Open the Logs Doctor for the full warning context."],
                )
            )
        severity = sev_from_findings(findings)
        return DoctorResult(
            self.module,
            self.title,
            "Audio stack inspected",
            severity,
            facts,
            findings,
            ["restart_pipewire"],
        )
