#!/usr/bin/env sh
set -eu
. "$(dirname "$0")/common.sh"
root_cmd zypper --non-interactive install python3 python3-pip python3-virtualenv
install_coredoc_from_repo "$(find_repo_root)"
cat <<'EOF_NOTE'

Optional diagnostics for richer output:
  sudo zypper install pciutils usbutils sensors fwupd pulseaudio-utils flatpak upower
EOF_NOTE
