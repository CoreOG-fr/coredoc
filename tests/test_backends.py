from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from coredoc.backends.audio import AudioDoctor
from coredoc.backends.clean import CleanDoctor
from coredoc.backends.hardware import HardwareDoctor
from coredoc.backends.logs import LogsDoctor
from coredoc.backends.permissions import PermissionsDoctor
from coredoc.backends.sleep import SleepDoctor
from coredoc.backends.wayland import WaylandDoctor
from coredoc.models import Severity
from coredoc.runner import CommandResult
from coredoc.support_bundle import sanitize


class FakeRunner:
    def __init__(self, mapping: dict[str, CommandResult] | None = None) -> None:
        self.mapping = mapping or {}
        self.calls: list[tuple[str, ...]] = []

    def run(self, argv: Sequence[str], timeout: float = 5.0) -> CommandResult:
        del timeout
        key = " ".join(argv)
        self.calls.append(tuple(argv))
        return self.mapping.get(key, CommandResult(tuple(argv), 127, "", "missing", True))


def res(
    argv: str, code: int = 0, out: str = "", err: str = "", missing: bool = False
) -> CommandResult:
    return CommandResult(tuple(argv.split()), code, out, err, missing)


def test_audio_detects_pipewire_and_empty_sinks() -> None:
    runner = FakeRunner(
        {
            "pactl info": res("pactl info", out="Server Name: PulseAudio (on PipeWire 1.0)\n"),
            "systemctl --user is-active pipewire pipewire-pulse wireplumber": res(
                "systemctl --user is-active pipewire pipewire-pulse wireplumber",
                out="active\nactive\nactive\n",
            ),
            "pactl list short sinks": res("pactl list short sinks", out=""),
            "pactl list short sources": res("pactl list short sources", out="1\tmic\n"),
            "journalctl --user -b -p warning --no-pager -n 80": res(
                "journalctl --user -b -p warning --no-pager -n 80", out="wireplumber warning\n"
            ),
        }
    )
    result = AudioDoctor(runner=runner).gather()  # type: ignore[arg-type]
    ids = {f.id for f in result.findings}
    assert "audio.pipewire" in ids
    assert "audio.no_sinks" in ids
    assert result.severity == Severity.ERROR


def test_audio_handles_missing_pactl() -> None:
    result = AudioDoctor(runner=FakeRunner()).gather()  # type: ignore[arg-type]
    assert any(f.id == "audio.pactl_missing" for f in result.findings)


def test_wayland_portal_inactive(monkeypatch) -> None:
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    runner = FakeRunner(
        {
            "systemctl --user is-active xdg-desktop-portal": res(
                "systemctl --user is-active xdg-desktop-portal", code=3, out="inactive"
            ),
            "systemctl --user is-active pipewire": res(
                "systemctl --user is-active pipewire", out="active"
            ),
            "journalctl --user -b --no-pager -n 80": res(
                "journalctl --user -b --no-pager -n 80", out="portal warning"
            ),
        }
    )
    result = WaylandDoctor(runner=runner).gather()  # type: ignore[arg-type]
    assert any(f.id == "wayland.portal_inactive" for f in result.findings)


def test_sleep_reads_s2idle(monkeypatch, tmp_path: Path) -> None:
    # Exercise parsing branch directly by monkeypatching helper rather than /sys.
    doctor = SleepDoctor(runner=FakeRunner({"journalctl -b -1 --no-pager -n 160": res("journalctl -b -1 --no-pager -n 160", out="PM: suspend entry (s2idle)\nresume\n")}))  # type: ignore[arg-type]
    monkeypatch.setattr(
        doctor, "_read", lambda path: "[s2idle] deep" if path.endswith("mem_sleep") else "platform"
    )
    result = doctor.gather()
    assert any(f.id == "sleep.s2idle_active" for f in result.findings)


def test_clean_finds_leftovers(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = tmp_path / ".config" / "demoapp"
    cfg.mkdir(parents=True)
    runner = FakeRunner(
        {"dpkg-query -L demoapp": res("dpkg-query -L demoapp", out="/usr/bin/demoapp\n")}
    )
    result = CleanDoctor("demoapp", runner=runner).gather()  # type: ignore[arg-type]
    assert str(cfg) in result.facts["leftover_candidates"]
    assert any(f.id == "clean.leftovers" for f in result.findings)


def test_clean_no_app() -> None:
    result = CleanDoctor("", runner=FakeRunner()).gather()  # type: ignore[arg-type]
    assert result.severity == Severity.INFO


def test_logs_repeated_patterns() -> None:
    out = "Jul 1 host svc: repeated badness\nJul 1 host svc: repeated badness\n"
    runner = FakeRunner(
        {
            "journalctl -b -p warning --no-pager -n 200": res(
                "journalctl -b -p warning --no-pager -n 200", out=out
            )
        }
    )
    result = LogsDoctor(runner=runner).gather()  # type: ignore[arg-type]
    assert any(f.id == "logs.repeated" for f in result.findings)


def test_hardware_battery_threshold(monkeypatch, tmp_path: Path) -> None:
    # Basic command-handling path. Real /sys is not required for this assertion.
    runner = FakeRunner(
        {
            "sensors": res("sensors", out="temp1: +40.0 C"),
            "fwupdmgr get-devices": res("fwupdmgr get-devices", out="System Firmware"),
            "lspci -nn": res("lspci -nn", out="VGA NVIDIA"),
            "lsusb": res("lsusb", out="Bus 001"),
        }
    )
    result = HardwareDoctor(runner=runner).gather()  # type: ignore[arg-type]
    assert any(f.id == "hardware.sensors" for f in result.findings)
    assert any(f.id == "hardware.nvidia" for f in result.findings)


def test_permissions_flatpak_overrides(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = FakeRunner(
        {
            "flatpak list --app --columns=application": res(
                "flatpak list --app --columns=application", out="org.example.App\n"
            ),
            "flatpak override --show": res(
                "flatpak override --show", out="[Context]\nfilesystems=home;\n"
            ),
            "systemctl --user list-unit-files --type=service --no-pager": res(
                "systemctl --user list-unit-files --type=service --no-pager",
                out="foo.service enabled\n",
            ),
        }
    )
    result = PermissionsDoctor(runner=runner).gather()  # type: ignore[arg-type]
    assert any(f.id == "permissions.flatpak_overrides" for f in result.findings)
    assert any(f.id == "permissions.user_services" for f in result.findings)


def test_sanitize_redacts_secrets() -> None:
    assert "<redacted>" in sanitize("token=abc123")
    assert "<redacted>" in sanitize("Authorization: Bearer nope")
