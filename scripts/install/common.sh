#!/usr/bin/env sh
set -eu

find_repo_root() {
  here=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
  if [ ! -f "$here/pyproject.toml" ] || [ ! -d "$here/src/coredoc" ]; then
    echo "Could not find the coredoc repository root." >&2
    exit 1
  fi
  printf '%s\n' "$here"
}

install_coredoc_from_repo() {
  repo=${1:-$(find_repo_root)}
  python_bin=${PYTHON:-python3}
  venv_dir=${COREDOC_VENV:-"$HOME/.local/share/coredoc/venv"}
  bin_dir=${COREDOC_BIN_DIR:-"$HOME/.local/bin"}

  mkdir -p "$venv_dir" "$bin_dir"
  "$python_bin" -m venv "$venv_dir"
  "$venv_dir/bin/python" -m pip install --upgrade pip
  "$venv_dir/bin/python" -m pip install -e "$repo"

  cat > "$bin_dir/coredoc" <<EOF_WRAPPER
#!/usr/bin/env sh
exec "$venv_dir/bin/coredoc" "\$@"
EOF_WRAPPER
  chmod +x "$bin_dir/coredoc"

  echo "coredoc installed."
  echo "Run: $bin_dir/coredoc"
  case ":$PATH:" in
    *":$bin_dir:"*) ;;
    *) echo "Note: add $bin_dir to PATH if 'coredoc' is not found." ;;
  esac
}

root_cmd() {
  if command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  elif command -v doas >/dev/null 2>&1; then
    doas "$@"
  else
    echo "Need sudo or doas to install system packages." >&2
    exit 1
  fi
}
