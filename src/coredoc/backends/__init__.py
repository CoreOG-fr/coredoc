from __future__ import annotations

from coredoc.backends.audio import AudioDoctor
from coredoc.backends.clean import CleanDoctor
from coredoc.backends.hardware import HardwareDoctor
from coredoc.backends.logs import LogsDoctor
from coredoc.backends.permissions import PermissionsDoctor
from coredoc.backends.sleep import SleepDoctor
from coredoc.backends.wayland import WaylandDoctor

DOCTORS = {
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
    "WaylandDoctor",
    "SleepDoctor",
    "CleanDoctor",
    "LogsDoctor",
    "HardwareDoctor",
    "PermissionsDoctor",
    "DOCTORS",
]
