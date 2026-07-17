#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if command -v docker >/dev/null 2>&1; then RUNTIME=docker; elif command -v podman >/dev/null 2>&1; then RUNTIME=podman; else echo "Need docker or podman" >&2; exit 1; fi
"$RUNTIME" run --rm -v "$ROOT:/src" archlinux:latest bash -lc '
  set -euo pipefail
  pacman -Syu --noconfirm base-devel python python-build python-installer python-wheel python-setuptools python-textual namcap
  cd /src
  namcap packaging/arch/PKGBUILD || true
'
