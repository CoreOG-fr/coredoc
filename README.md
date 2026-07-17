# coredoc

coredoc helps you answer the Linux question everyone hates: “what is actually broken, and what should I check first?”

```
                            __
  _________  ________  ____/ /___  _____
 / ___/ __ \/ ___/ _ \/ __  / __ \/ ___/
/ /__/ /_/ / /  /  __/ /_/ / /_/ / /__
\___/\____/_/   \___/\__,_/\____/\___/
```

It is a terminal UI and CLI for local diagnostics. It reads the same tools you already reach for — `journalctl`, `systemctl`, `pactl`, `df`, `ip`, `fwupdmgr`, `lspci`, `flatpak`, and friends — then turns the pieces into a clear diagnosis with evidence and next steps.

coredoc is read-only by default. When it offers a safe action in the TUI, it asks before running anything.

## Install scripts

Clone the project, then run the auto-installer:

```bash
git clone https://github.com/CoreOG-fr/coredoc.git
cd coredoc
./scripts/install.sh
coredoc
```

If you prefer to pick the script yourself:

```bash
# Debian / Ubuntu
./scripts/install/debian-ubuntu.sh

# Arch Linux
./scripts/install/arch.sh

# Fedora
./scripts/install/fedora.sh

# openSUSE
./scripts/install/opensuse.sh

# Alpine
./scripts/install/alpine.sh

# Nix profile install, if you use Nix
./scripts/install/nix.sh
```

The scripts install coredoc into an isolated virtualenv under `~/.local/share/coredoc/venv` and place a small `coredoc` launcher in `~/.local/bin`.

If your shell cannot find it, add this to your shell profile:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

The scripts install only the Python runtime pieces needed to run coredoc. They also print optional diagnostic packages for richer checks, such as `pciutils`, `usbutils`, `lm_sensors`, `fwupd`, `pulseaudio-utils`, and Flatpak tools.

## 30 seconds to try it

From the repository:

```bash
cd /home/user/coredoc
python3 -m pip install --user -e .
coredoc
```

Or run it without installing:

```bash
cd /home/user/coredoc
PYTHONPATH=src python3 -m coredoc.cli
```

## A useful first command

Screen sharing on Linux can fail because of Wayland, portals, PipeWire, browser flags, or a broken user service. Ask coredoc where to start:

```bash
coredoc fix screenshare
```

Example shape of the output:

```text
Most likely issue to check first: XDG Desktop Portal stack is unhealthy.

Root causes:
1. [warn] XDG Desktop Portal stack is unhealthy
   Portal failures commonly break Wayland screen sharing, Flatpak file pickers,
   and sandbox integration.

Action plan:
1. [safe] Restart XDG Desktop Portal
   systemctl --user restart xdg-desktop-portal
```

Other scenarios:

```bash
coredoc fix audio
coredoc fix sleep-drain
coredoc fix network
coredoc since last-boot
coredoc since 24h
```

## The TUI

Run:

```bash
coredoc
```

The first screen is **Global Diagnosis**. It shows:

- a short health summary
- a root-cause tree
- evidence from the doctors that matched each cause
- suggested next steps
- warning banners when data is missing or permission-limited

Keyboard shortcuts:

| Key | Action |
| --- | --- |
| `g` | Global diagnosis |
| `d` | Per-module dashboard |
| `r` | Refresh checks |
| `b` | Write a support bundle |
| `q` | Quit |

Safe actions, such as showing failed units or restarting a user-level PipeWire/portal service, appear as buttons and require confirmation.

## JSON mode

For scripts, bug reports, or tests:

```bash
coredoc --json --doctor core
coredoc --json --doctor audio
coredoc --json --doctor clean --app firefox
coredoc fix screenshare --json
coredoc since last-boot --json
```

## Doctors included today

- `core`: boot state, failed units, disk and inode pressure, mounts, packages, route, DNS, time sync, journal access, OOM, firmware, and kernel warnings.
- `audio`: PipeWire/PulseAudio reachability, sinks, sources, Bluetooth profiles, user services, and firmware-related audio clues.
- `wayland`: compositor/session hints, XDG Desktop Portal, portal backends, PipeWire screen capture, and browser/Electron flags.
- `sleep`: suspend mode, wake sources, USB wake settings, sleep logs, GPU runtime state, and battery hints.
- `clean`: package-manager footprint and leftover config/cache/data candidates, with confidence scores. It reports quarantine candidates; it does not delete files.
- `logs`: warning/error journal summaries, repeated patterns, and common failure classes.
- `hardware`: sensors, firmware tooling, PCI/USB inventory, battery charge thresholds, and optional control tools.
- `permissions`: Flatpak permissions, portal stores, autostarts, DBus services, Polkit rules, and user services.

## Debian and Ubuntu

Build the package:

```bash
make package-deb
```

Install it:

```bash
sudo apt install ./dist/coredoc_0.2.0-1_all.deb
coredoc
```

## Fedora and openSUSE RPM

```bash
make package-rpm
packaging/scripts/test_in_fedora.sh   # if Docker or Podman is available
```

## Arch Linux / AUR

```bash
make package-arch
# then inspect packaging/arch/PKGBUILD and build in a clean Arch environment
```

## Alpine

```bash
cd packaging/alpine
abuild -r
```

## Flatpak

The manifest is in:

```text
packaging/flatpak/io.github.coredoc.coredoc.yml
```

It requests broad host/device access because diagnostics need to see the host. If that is too much for your use case, prefer the native package.

```bash
make package-flatpak
```

## Nix

An optional flake lives in:

```text
packaging/nix/flake.nix
```

## Documentation

- [User guide](docs/USER_GUIDE.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Triage design](docs/TRIAGE.md)
- [Security model](docs/SECURITY.md)
- [Contributing](CONTRIBUTING.md)

## Development

```bash
make test
make lint
make all
```

`make test` runs the test suite with coverage. `make lint` runs Ruff, Black, isort, and mypy.

## Safety model

coredoc reads first and acts only when you explicitly ask it to. The TUI can run actions marked `safe`, and even those require confirmation. Manual or risky fixes — package installs, kernel parameter changes, filesystem repair, deletion, and permission changes — stay as advice.

Support bundles are sanitized, but you should still review them before sharing. Logs can contain hostnames, usernames, paths, and unusual secret formats.

## Contributing

If you know a Linux failure mode that wastes people’s time, coredoc probably needs a rule or a doctor for it. Start with [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT.
