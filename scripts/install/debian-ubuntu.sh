#!/usr/bin/env sh
set -eu
. "$(dirname "$0")/common.sh"
root_cmd apt-get update
root_cmd apt-get install -y python3 python3-venv python3-pip
install_coredoc_from_repo "$(find_repo_root)"
cat <<'EOF_NOTE'

Optional diagnostics for richer output:
  sudo apt-get install -y pciutils usbutils lm-sensors fwupd pulseaudio-utils flatpak
EOF_NOTE
