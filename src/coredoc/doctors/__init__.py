"""Doctor registry used by the CLI, TUI, support bundles, and triage engine."""

from __future__ import annotations

from typing import Any

from coredoc.doctors.audio import AudioDoctor
from coredoc.doctors.clean import CleanDoctor
from coredoc.doctors.core import CoreDoctor
from coredoc.doctors.hardware import HardwareDoctor
from coredoc.doctors.logs import LogsDoctor
from coredoc.doctors.permissions import PermissionsDoctor
from coredoc.doctors.sleep import SleepDoctor
from coredoc.doctors.wayland import WaylandDoctor

DOCTORS: dict[str, type[Any]] = {
    "core": CoreDoctor,
    "audio": AudioDoctor,
    "wayland": WaylandDoctor,
    "sleep": SleepDoctor,
    "clean": CleanDoctor,
    "logs": LogsDoctor,
    "hardware": HardwareDoctor,
    "permissions": PermissionsDoctor,
}

__all__ = [
    "AudioDoctor",
    "CleanDoctor",
    "CoreDoctor",
    "HardwareDoctor",
    "LogsDoctor",
    "PermissionsDoctor",
    "SleepDoctor",
    "WaylandDoctor",
    "DOCTORS",
]
