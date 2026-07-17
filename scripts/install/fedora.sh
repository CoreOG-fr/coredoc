#!/usr/bin/env sh
set -eu
. "$(dirname "$0")/common.sh"
root_cmd dnf install -y python3 python3-pip
install_coredoc_from_repo "$(find_repo_root)"
cat <<'EOF_NOTE'

Optional diagnostics for richer output:
  sudo dnf install -y pciutils usbutils lm_sensors fwupd pulseaudio-utils flatpak upower
EOF_NOTE
