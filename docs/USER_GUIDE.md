# coredoc user guide

coredoc is a terminal-based Linux diagnostics tool that helps you answer three questions:

1. What looks broken?
2. What is probably causing it?
3. What should I try next?

It does not replace Linux tools like `journalctl`, `systemctl`, `pactl`, `df`, `ip`, `fwupdmgr`, or `lspci`. Instead, it reads those tools for you, keeps the evidence, and turns the result into a clear diagnosis.

coredoc is read-only by default. When the TUI offers a safe action, it asks before running anything.

---

## Table of contents

- [What coredoc does](#what-coredoc-does)
- [Install and run](#install-and-run)
- [First run](#first-run)
- [The TUI](#the-tui)
- [CLI commands](#cli-commands)
- [JSON output](#json-output)
- [Support bundles](#support-bundles)
- [Doctors](#doctors)
- [Triage and root causes](#triage-and-root-causes)
- [Fix scenarios](#fix-scenarios)
- [Change detection](#change-detection)
- [Safety model](#safety-model)
- [Common workflows](#common-workflows)
- [Packaging](#packaging)
- [Development](#development)
- [Troubleshooting coredoc itself](#troubleshooting-coredoc-itself)
- [Limitations](#limitations)
- [Glossary](#glossary)

---

## What coredoc does

Linux already has excellent diagnostic tools. The problem is that the clues are scattered.

For example, broken screen sharing might involve:

- Wayland session variables
- XDG Desktop Portal
- portal backend packages
- PipeWire
- WirePlumber
- browser flags
- Flatpak permissions
- user journal logs

coredoc collects those clues and shows you where to start.

It works in two layers:

### Doctors

A doctor checks one part of the system.

Examples:

- `audio` checks PipeWire, PulseAudio, sinks, sources, Bluetooth profiles, and audio logs.
- `sleep` checks suspend mode, wake sources, and sleep-related logs.
- `core` checks broad system health: failed services, disk pressure, DNS, time sync, package health, and kernel errors.

### Triage

The triage engine connects findings from different doctors.

For example:

- If audio is broken and Wayland screen sharing is also broken, PipeWire may be the shared cause.
- If disk usage is critical, that may explain package failures, service errors, and application crashes.
- If the system is degraded, failed units are usually worth checking before app-level symptoms.

The result is a global diagnosis with evidence and suggested next steps.

---

## Install and run

### From the repository

If you are inside the coredoc source folder:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
coredoc
```

If your distro uses `python3` instead of `python`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
coredoc
```

### Distro install scripts

From the repository root, you can let coredoc pick the right installer:

```bash
./scripts/install.sh
```

Or choose one manually:

```bash
./scripts/install/debian-ubuntu.sh
./scripts/install/arch.sh
./scripts/install/fedora.sh
./scripts/install/opensuse.sh
./scripts/install/alpine.sh
./scripts/install/nix.sh
```

These scripts keep coredoc in its own virtualenv and install a launcher in `~/.local/bin`. They do not force-install every optional diagnostic tool; instead, each script prints a short list of useful packages for deeper checks.

### One-command local run

From the coredoc folder:

```bash
python -m venv .venv && source .venv/bin/activate && python -m pip install -U pip && python -m pip install -e . && coredoc
```

### Run without installing

```bash
cd /path/to/coredoc
PYTHONPATH=src python -m coredoc.cli
```

---

## First run

Start the TUI:

```bash
coredoc
```

coredoc will show a loading screen while it checks the system. When it finishes, you will land on the **Global Diagnosis** view.

The first screen tells you:

- the overall severity
- the most useful issue to check first
- warning banners for missing or permission-limited data
- a root-cause tree
- suggested next steps

If you are not sure what to do, press:

```text
f
```

That opens a focused fix view for the top issue.

---

## The TUI

The TUI is the main interactive experience.

### Keybindings

| Key | Action |
| --- | --- |
| `g` | Show Global Diagnosis |
| `d` | Show per-module dashboard |
| `f` | Start fixing the top issue |
| `r` | Refresh checks |
| `b` | Create a support bundle |
| `h` | Open help |
| `?` | Open help |
| `q` | Quit |

### Global Diagnosis

This is the first screen.

It shows:

- a short diagnosis summary
- warning banners
- root causes
- evidence for each cause
- suggested next steps
- safe action buttons when available

Example:

```text
Global diagnosis: WARN
Most likely issue to check first: XDG Desktop Portal stack is unhealthy.

Root-cause tree
1. XDG Desktop Portal stack is unhealthy (warn)
   Portal failures commonly break Wayland screen sharing, Flatpak file pickers,
   and sandbox integration.
   Affects: permissions, wayland
   └─ wayland.portal_inactive: XDG Desktop Portal is not active

Suggested next steps
1. [SAFE] Restart XDG Desktop Portal
   systemctl --user restart xdg-desktop-portal
```

If a safe action is available, coredoc shows a button. Pressing it opens a confirmation dialog. Nothing runs without confirmation.

### Module Dashboard

Press:

```text
d
```

This shows each doctor and its current status.

Example:

```text
core          WARN    Core system health inspected
audio         INFO    Audio stack inspected
wayland       WARN    Wayland portal stack inspected
sleep         OK      Sleep and wake state inspected
```

### Doctor details

Use the sidebar to open a doctor, such as **Audio** or **Sleep**.

A doctor detail view shows:

- the doctor summary
- findings
- evidence
- advice
- a suggested next command

Example:

```text
What next? Run `coredoc fix audio` for a focused fix path, or press `g` for the global view.
```

### Help screen

Press:

```text
h
```

or:

```text
?
```

The help screen explains the basic controls and how doctors relate to global diagnosis.

---

## CLI commands

You can use coredoc without the TUI.

### Show help

```bash
coredoc --help
```

### Open the TUI

```bash
coredoc
```

### Run a fix scenario

```bash
coredoc fix audio
coredoc fix screenshare
coredoc fix sleep-drain
coredoc fix network
coredoc fix system
coredoc fix hardware
coredoc fix permissions
coredoc fix cleanup
```

A fix scenario runs the relevant doctors, applies triage, and prints a focused diagnosis with suggested next steps.

### Run one doctor

```bash
coredoc --json --doctor audio
coredoc --json --doctor sleep
coredoc --json --doctor hardware
```

Doctor output is JSON because it is meant for scripts, support bundles, and detailed inspection.

### Check what changed

```bash
coredoc since last-boot
coredoc since 24h
coredoc since today
coredoc since yesterday
```

This summarizes available journal and package-history clues.

---

## JSON output

Use JSON when you want machine-readable output:

```bash
coredoc --json --doctor audio
```

Top-level fields include:

```json
{
  "module": "audio",
  "title": "Audio Doctor",
  "summary": "Audio stack inspected",
  "severity": "info",
  "facts": {},
  "findings": [],
  "actions": [],
  "suggested_next_command": "coredoc fix audio"
}
```

The `suggested_next_command` field tells a script or frontend where to point the user next.

### Finding fields

Each finding contains:

- `id`: stable machine-readable identifier
- `title`: short human-readable heading
- `severity`: `ok`, `info`, `warn`, `error`, or `unknown`
- `summary`: what coredoc found
- `evidence`: supporting lines or facts
- `advice`: next steps or context
- `fix_id`: optional action reference
- `confidence`: optional score
- `impact`: optional score
- `safety`: optional action safety label
- `tags`: optional machine-readable tags

---

## Support bundles

A support bundle is a sanitized tarball with diagnostic JSON.

Create one from the CLI:

```bash
coredoc --support-bundle --output-dir .
```

Or press:

```text
b
```

inside the TUI.

The bundle is useful when asking for help or filing an issue. It is sanitized, but you should still review it before sharing. Logs can contain usernames, hostnames, paths, and unusual secret formats.

---

## Doctors

### core

The `core` doctor checks broad system health.

It looks at:

- systemd state
- failed units
- disk usage
- inode usage
- read-only mounts
- package-manager health
- default route
- DNS resolution
- time synchronization
- journal access
- kernel warnings
- OOM and firmware patterns

Run it:

```bash
coredoc --json --doctor core
```

Use it when the system feels generally wrong or multiple things are failing.

---

### audio

The `audio` doctor checks Linux audio state.

It looks at:

- `pactl info`
- PipeWire/PulseAudio reachability
- default sink and source
- visible sinks and sources
- Bluetooth card profiles
- PipeWire user services
- user journal audio warnings
- kernel firmware messages related to audio or Bluetooth

Run it:

```bash
coredoc --json --doctor audio
coredoc fix audio
```

Useful manual checks:

```bash
pactl info
pactl list short sinks
systemctl --user status pipewire pipewire-pulse wireplumber
```

---

### wayland

The `wayland` doctor checks the screen-sharing and portal path.

It looks at:

- `XDG_SESSION_TYPE`
- `WAYLAND_DISPLAY`
- current desktop/compositor hints
- `xdg-desktop-portal`
- portal backend descriptors
- PipeWire and WirePlumber
- browser/Electron flag files
- portal-related logs

Run it:

```bash
coredoc --json --doctor wayland
coredoc fix screenshare
```

Useful manual checks:

```bash
echo $XDG_SESSION_TYPE
systemctl --user status xdg-desktop-portal pipewire wireplumber
ls /usr/share/xdg-desktop-portal/portals/
```

---

### sleep

The `sleep` doctor checks suspend and wake behavior.

It looks at:

- `/sys/power/mem_sleep`
- `/sys/power/state`
- ACPI wake sources
- USB wake settings
- previous boot suspend/resume logs
- GPU runtime state
- battery status

Run it:

```bash
coredoc --json --doctor sleep
coredoc fix sleep-drain
```

Useful manual check:

```bash
cat /sys/power/mem_sleep
```

If you see:

```text
[s2idle] deep
```

then `s2idle` is active while `deep` is available. That can matter on some laptops.

---

### clean

The `clean` doctor finds likely leftovers from apps.

It looks at:

- package-manager footprint
- XDG config/data/cache paths
- Flatpak app data
- legacy dotfiles
- autostart entries
- user services

It does **not** delete anything.

Run it:

```bash
coredoc --json --doctor clean --app firefox
coredoc fix cleanup
```

The doctor reports confidence scores so you can decide what to quarantine.

---

### logs

The `logs` doctor summarizes recent warnings and errors.

It looks at:

- current boot journal warnings
- repeated patterns
- kernel warnings
- OOM kills
- firmware failures
- filesystem errors
- GPU warnings
- service failures
- network warnings

Run it:

```bash
coredoc --json --doctor logs
```

If kernel access is restricted, coredoc reports that as a finding instead of crashing.

---

### hardware

The `hardware` doctor checks what Linux can see and control.

It looks at:

- `sensors`
- `/sys/class/hwmon`
- `fwupdmgr`
- PCI devices
- USB devices
- block devices
- battery charge thresholds
- optional tools like `liquidctl`, `openrgb`, and `nvidia-smi`

Run it:

```bash
coredoc --json --doctor hardware
coredoc fix hardware
```

On laptops, this is useful for checking firmware support and battery threshold files.

---

### permissions

The `permissions` doctor shows local permission and startup surfaces.

It looks at:

- Flatpak apps and overrides
- Flatpak portal permissions
- autostart entries
- DBus services
- Polkit rules
- systemd user services

Run it:

```bash
coredoc --json --doctor permissions
coredoc fix permissions
```

Useful when you want to know what can start itself or has broad access.

---

## Triage and root causes

The triage engine reads all doctor findings and connects related symptoms.

Rules live in:

```text
src/coredoc/triage/rules.toml
```

Examples:

- `pipewire_stack`: connects audio and Wayland failures through PipeWire.
- `portal_stack`: connects screen sharing and Flatpak portal symptoms.
- `disk_exhaustion`: puts disk or inode pressure before app-level problems.
- `network_core`: treats default route and DNS failures as base problems.
- `sleep_drain`: connects `s2idle` clues to laptop sleep-drain workflows.

Triage does not prove a root cause with absolute certainty. It gives you a better first move.

---

## Fix scenarios

A fix scenario is a focused path through the relevant doctors.

Examples:

```bash
coredoc fix audio
coredoc fix screenshare
coredoc fix sleep-drain
```

A scenario output includes:

- summary
- likely root causes
- affected modules
- evidence
- suggested next steps
- safe commands when available

At the end, coredoc reminds you:

```text
What next? Run these in the TUI with `coredoc` for guided execution,
or manually copy the commands above. Safe TUI actions still ask first.
```

---

## Change detection

Use `since` when something broke after an update, reboot, suspend, or package change.

```bash
coredoc since last-boot
coredoc since 24h
coredoc since today
```

It checks available sources such as:

- current boot warnings
- previous boot warnings
- APT history
- dpkg history
- kernel version

This is not a full time machine. It is a clue finder.

---

## Safety model

coredoc has three safety levels in practice:

### Read-only diagnostics

Doctors gather information. They do not change the system.

### Safe TUI actions

Some actions are low-risk, such as showing failed units or restarting a user-level service. These can appear as TUI buttons, but coredoc asks before running them.

### Manual or risky actions

Package installs, file deletion, kernel parameter changes, filesystem repair, and permission edits stay as advice. coredoc does not run them automatically.

---

## Common workflows

### Audio does not work

```bash
coredoc fix audio
```

Then open the TUI:

```bash
coredoc
```

Press `f` to focus on the top issue.

### Screen sharing does not work

```bash
coredoc fix screenshare
```

This checks Wayland, portals, PipeWire, permissions, and logs.

### Laptop drains while suspended

```bash
coredoc fix sleep-drain
```

Also check:

```bash
cat /sys/power/mem_sleep
```

### Something broke after an update

```bash
coredoc since last-boot
coredoc fix system
```

### You want to share diagnostics

```bash
coredoc --support-bundle --output-dir .
```

Review the tarball before sharing.

---

## Packaging

### Debian / Ubuntu

```bash
make package-deb
sudo apt install ./dist/coredoc_0.2.0-1_all.deb
```

### Arch

Use the PKGBUILD:

```bash
make package-arch
```

Or build manually on Arch:

```bash
sudo pacman -S --needed base-devel python python-build python-installer python-wheel python-setuptools python-textual
makepkg -si
```

### Fedora / openSUSE

```bash
make package-rpm
```

If Docker or Podman is available:

```bash
packaging/scripts/test_in_fedora.sh
```

### Alpine

```bash
cd packaging/alpine
abuild -r
```

### Flatpak

```bash
make package-flatpak
```

The Flatpak manifest asks for broad host access because diagnostics need to inspect the host. Prefer the native package if you do not want that.

---

## Development

Install editable:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Run tests and checks:

```bash
make test
make lint
```

Run a smoke test:

```bash
coredoc --help
coredoc fix screenshare
coredoc since last-boot
coredoc
```

### Add a doctor

1. Add a file in `src/coredoc/doctors/`.
2. Subclass `BaseDoctor`.
3. Use `self.cmd()` for external commands.
4. Return `DoctorResult` with facts and findings.
5. Add it to `src/coredoc/doctors/__init__.py`.
6. Add tests.

### Add a triage rule

Edit:

```text
src/coredoc/triage/rules.toml
```

Add a rule that matches finding IDs and produces a root cause. Only mark an action as `safe` if it is low-risk and okay to run after confirmation.

---

## Troubleshooting coredoc itself

### `coredoc` command not found

If you installed in a virtualenv, activate it:

```bash
source .venv/bin/activate
```

Then run:

```bash
coredoc --help
```

### TUI does not open

Try the CLI path:

```bash
coredoc fix system
```

Or run without installing:

```bash
PYTHONPATH=src python -m coredoc.cli fix system
```

### Missing tools warnings

This is normal. coredoc is designed to work on minimal systems.

Examples of optional tools:

- `pactl`
- `flatpak`
- `fwupdmgr`
- `sensors`
- `lspci`
- `lsusb`

Install only what you need.

### Permission-limited logs

Normal users may not be able to read all journal or kernel logs.

On systemd systems, membership in `systemd-journal` may help:

```bash
sudo usermod -aG systemd-journal "$USER"
```

Log out and back in after changing groups.

---

## Limitations

- coredoc explains likely causes; it does not guarantee certainty.
- Some checks depend on distro tools and permissions.
- Cross-distro support is defensive, but not every branch is tested on every distro.
- The `since` command is a clue finder, not a full rollback or historical database.
- Safe actions are intentionally conservative.

---

## Glossary

### Doctor

A module that checks one part of the system.

### Finding

A piece of evidence with severity, summary, and advice.

### Triage

The process of connecting findings and deciding what to check first.

### Root cause

The likely underlying issue behind one or more symptoms.

### Safe action

A low-risk command that coredoc can offer in the TUI after confirmation.

### Support bundle

A sanitized tarball of diagnostic JSON for sharing with someone helping you debug.

