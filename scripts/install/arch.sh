#!/usr/bin/env sh
set -eu
. "$(dirname "$0")/common.sh"
root_cmd pacman -S --needed --noconfirm python python-pip
PYTHON=python install_coredoc_from_repo "$(find_repo_root)"
cat <<'EOF_NOTE'

Optional diagnostics for richer output:
  sudo pacman -S --needed pciutils usbutils lm_sensors fwupd pulseaudio-utils flatpak upower

For Wayland screen sharing, also install the portal backend for your desktop:
  sudo pacman -S --needed xdg-desktop-portal xdg-desktop-portal-gtk
  # or xdg-desktop-portal-kde / -gnome / -wlr / -hyprland as appropriate
EOF_NOTE
