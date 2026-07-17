from __future__ import annotations

from coredoc.triage.models import RootCause

MODULE_NEXT_COMMANDS = {
    "core": "coredoc fix system",
    "audio": "coredoc fix audio",
    "wayland": "coredoc fix screenshare",
    "sleep": "coredoc fix sleep-drain",
    "clean": "coredoc fix cleanup",
    "logs": "coredoc fix system",
    "hardware": "coredoc fix hardware",
    "permissions": "coredoc fix permissions",
}

ROOT_CAUSE_SCENARIOS = {
    "pipewire_stack": "audio",
    "portal_stack": "screenshare",
    "systemd_degraded": "system",
    "time_unsynced": "system",
    "disk_exhaustion": "system",
    "firmware_failures": "hardware",
    "network_core": "network",
    "sleep_drain": "sleep-drain",
    "flatpak_broad_permissions": "permissions",
}


def suggested_next_command(module: str) -> str:
    return MODULE_NEXT_COMMANDS.get(module, "coredoc fix system")


def scenario_for_root_cause(cause: RootCause | None) -> str:
    if cause is None:
        return "system"
    if cause.id in ROOT_CAUSE_SCENARIOS:
        return ROOT_CAUSE_SCENARIOS[cause.id]
    modules = cause.affected_modules
    if "wayland" in modules:
        return "screenshare"
    if "audio" in modules:
        return "audio"
    if "sleep" in modules:
        return "sleep-drain"
    if "hardware" in modules:
        return "hardware"
    if "permissions" in modules:
        return "permissions"
    return "system"


def what_next_for_module(module: str) -> str:
    command = suggested_next_command(module)
    return f"What next? Run `{command}` for a focused fix path, or press `g` for the global view."


def fix_footer() -> str:
    return (
        "What next? Run these in the TUI with `coredoc` for guided execution, "
        "or manually copy the commands above. Safe TUI actions still ask first."
    )


def since_footer() -> str:
    return (
        "What next? If this looks like a regression, run `coredoc fix <problem>` "
        "with the symptom you are seeing, such as `audio`, `screenshare`, or `sleep-drain`."
    )
