#!/usr/bin/env sh
set -eu
. "$(dirname "$0")/common.sh"
root_cmd apk add python3 py3-pip py3-virtualenv
install_coredoc_from_repo "$(find_repo_root)"
cat <<'EOF_NOTE'

Optional diagnostics for richer output:
  sudo apk add pciutils usbutils lm-sensors fwupd pulseaudio-utils flatpak upower
EOF_NOTE
