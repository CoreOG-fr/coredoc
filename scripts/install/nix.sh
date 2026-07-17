#!/usr/bin/env sh
set -eu
if command -v nix >/dev/null 2>&1 && [ -f "$(dirname "$0")/../../packaging/nix/flake.nix" ]; then
  echo "Using the project flake."
  cd "$(dirname "$0")/../.."
  nix profile install ./packaging/nix
else
  echo "Nix is not available or the flake is missing." >&2
  exit 1
fi
