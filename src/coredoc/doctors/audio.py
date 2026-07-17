"""Check whether Linux audio is reachable, routed, and using sensible profiles."""

from __future__ import annotations

import json

from coredoc.doctors.base import BaseDoctor, is_desktop_session, lines
from coredoc.models import DoctorResult, Finding, Severity


class AudioDoctor(BaseDoctor):
    module = "audio"
    title = "Audio Doctor"

    def run(self) -> DoctorResult:
        facts: dict[str, object] = {}
        findings: list[Finding] = []
        pactl = self.cmd(["pactl", "info"])
        facts["pactl_info"] = pactl.fact()
        if pactl.missing:
            findings.append(
                self.missing_tool("pactl", "Cannot inspect PulseAudio/PipeWire routing.")
            )
        elif pactl.returncode != 0:
            sev = Severity.ERROR if self._desktop() else Severity.WARN
            findings.append(
                Finding(
                    "audio.server_unreachable",
                    "Audio server is unreachable",
                    sev,
                    "pactl could not connect to PulseAudio or PipeWire's Pulse server.",
                    evidence=[pactl.stderr.strip() or pactl.stdout.strip()],
                    advice=[
                        "Check: systemctl --user status pipewire pipewire-pulse wireplumber pulseaudio"
                    ],
                )
            )
        else:
            server = self._line_value(pactl.stdout, "Server Name:")
            facts["server_name"] = server
            if "pipewire" in server.lower():
                findings.append(
                    Finding("audio.pipewire", "PipeWire Pulse server detected", Severity.OK, server)
                )
            elif "pulseaudio" in server.lower():
                findings.append(
                    Finding("audio.pulseaudio", "Native PulseAudio detected", Severity.INFO, server)
                )

        audio_cmds = {
            "default_sink": ["pactl", "get-default-sink"],
            "default_source": ["pactl", "get-default-source"],
            "sinks": ["pactl", "list", "short", "sinks"],
            "sources": ["pactl", "list", "short", "sources"],
            "cards": ["pactl", "list", "cards"],
        }
        audio_results = {key: self.cmd(argv) for key, argv in audio_cmds.items()}
        for key, result in audio_results.items():
            facts[key] = result.fact()

        sinks = audio_results["sinks"]
        sources = audio_results["sources"]
        cards = audio_results["cards"]
        if not sinks.missing and sinks.returncode == 0 and not lines(sinks.stdout):
            findings.append(
                Finding(
                    "audio.no_sinks",
                    "No audio output devices are visible",
                    Severity.ERROR if self._desktop() else Severity.WARN,
                    "The audio server is reachable but reported no sinks.",
                    advice=["Check ALSA devices with aplay -l and kernel firmware errors."],
                )
            )
        if not sources.missing and sources.returncode == 0 and not lines(sources.stdout):
            findings.append(
                Finding(
                    "audio.no_sources",
                    "No audio input devices are visible",
                    Severity.WARN,
                    "The audio server reported no input sources.",
                    advice=[
                        "If you expect a microphone, check headset profile and privacy switches."
                    ],
                )
            )
        cards_text = cards.stdout
        bt_evidence = self._bluetooth_profile_findings(cards_text)
        findings.extend(bt_evidence)

        services = self.cmd(
            ["systemctl", "--user", "is-active", "pipewire", "pipewire-pulse", "wireplumber"]
        )
        facts["pipewire_services"] = services.fact()
        if services.missing:
            findings.append(self.missing_tool("systemctl", "Cannot inspect user audio services."))
        elif services.returncode != 0 and "pipewire" in str(facts.get("server_name", "")).lower():
            findings.append(
                Finding(
                    "audio.pipewire_service_inactive",
                    "One or more PipeWire user services are inactive",
                    Severity.WARN,
                    "PipeWire is detected but service health is not fully active.",
                    evidence=lines(services.stdout + services.stderr, 5),
                )
            )

        journal = self.cmd(
            ["journalctl", "--user", "-b", "-p", "warning", "--no-pager", "-n", "200"]
        )
        facts["audio_journal"] = journal.fact()
        warn_lines = [line for line in lines(journal.stdout, 200) if self._audio_related(line)]
        if journal.missing:
            findings.append(self.missing_tool("journalctl", "Cannot inspect recent audio logs."))
        elif warn_lines:
            findings.append(
                Finding(
                    "audio.recent_warnings",
                    "Recent audio-related warnings found",
                    Severity.WARN,
                    "The user journal contains PipeWire/Pulse/ALSA/Bluetooth warnings.",
                    evidence=warn_lines[:10],
                    advice=["Use the Logs doctor for surrounding context."],
                )
            )

        kernel = self.cmd(["journalctl", "-k", "-b", "--no-pager", "-n", "400"])
        facts["kernel_audio"] = kernel.fact()
        firmware = [line for line in lines(kernel.stdout, 400) if self._firmware_audio(line)]
        if firmware:
            findings.append(
                Finding(
                    "audio.firmware_errors",
                    "Audio or Bluetooth firmware load errors found",
                    Severity.WARN,
                    "Kernel logs mention firmware/device failures that may affect audio.",
                    evidence=firmware[:8],
                )
            )
        return self.result("Audio stack inspected", facts, findings, ["restart_pipewire"])

    def _desktop(self) -> bool:
        return is_desktop_session()

    @staticmethod
    def _line_value(text: str, prefix: str) -> str:
        for line in text.splitlines():
            if line.strip().startswith(prefix):
                return line.split(":", 1)[1].strip()
        return "unknown"

    @staticmethod
    def _audio_related(line: str) -> bool:
        return any(
            k in line.lower()
            for k in ["pipewire", "wireplumber", "pulse", "alsa", "bluez", "bluetooth", "snd"]
        )

    @staticmethod
    def _firmware_audio(line: str) -> bool:
        lower = line.lower()
        return (
            "firmware" in lower
            and any(k in lower for k in ["snd", "sof", "hda", "blue", "bt", "audio"])
        ) or "sof-audio" in lower

    def _bluetooth_profile_findings(self, cards_text: str) -> list[Finding]:
        findings: list[Finding] = []
        if "bluez_card" not in cards_text:
            return findings
        active_profiles = [
            line.strip() for line in cards_text.splitlines() if "Active Profile:" in line
        ]
        facts = active_profiles[:5]
        bad = [
            p
            for p in active_profiles
            if any(x in p.lower() for x in ["headset", "handsfree", "hsp", "hfp"])
        ]
        if bad:
            findings.append(
                Finding(
                    "audio.bluetooth_low_quality_profile",
                    "Bluetooth headset is in call/low-quality profile",
                    Severity.WARN,
                    "A Bluetooth card is using a headset/handsfree profile instead of A2DP music playback.",
                    evidence=bad[:5],
                    advice=["Switch to A2DP when not using the microphone."],
                )
            )
        elif facts:
            findings.append(
                Finding(
                    "audio.bluetooth_profile",
                    "Bluetooth audio profile detected",
                    Severity.INFO,
                    "Bluetooth audio cards are visible.",
                    evidence=facts,
                )
            )
        return findings


if __name__ == "__main__":
    print(json.dumps(AudioDoctor().run().as_dict(), indent=2))
