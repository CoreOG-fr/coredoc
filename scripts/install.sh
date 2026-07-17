#!/usr/bin/env sh
set -eu

# Install coredoc from a cloned checkout. If you run this script from the
# repository root, it picks the right distro-specific installer for you.

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

if [ -f /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release
else
  echo "Could not detect your distro: /etc/os-release is missing." >&2
  exit 1
fi

ids=" ${ID:-} ${ID_LIKE:-} "
script=""
case "$ids" in
  *" arch "*|*" artix "*|*" endeavouros "*|*" manjaro "*) script="arch.sh" ;;
  *" debian "*|*" ubuntu "*|*" linuxmint "*|*" pop "*) script="debian-ubuntu.sh" ;;
  *" fedora "*|*" rhel "*|*" centos "*|*" rocky "*|*" almalinux "*) script="fedora.sh" ;;
  *" opensuse "*|*" suse "*) script="opensuse.sh" ;;
  *" alpine "*) script="alpine.sh" ;;
  *" nixos "*) script="nix.sh" ;;
esac

if [ -z "$script" ]; then
  echo "Unsupported or unknown distro: ${PRETTY_NAME:-${ID:-unknown}}" >&2
  echo "Run one of scripts/install/*.sh manually if you know which family this system follows." >&2
  exit 1
fi

exec "$repo_root/scripts/install/$script"
