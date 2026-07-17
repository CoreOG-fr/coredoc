#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION=0.2.0
BUILD="$ROOT/build/debroot"
rm -rf "$BUILD"
mkdir -p "$BUILD/DEBIAN" "$BUILD/usr/bin" "$BUILD/usr/lib/python3/dist-packages" "$BUILD/usr/share/man/man1" "$BUILD/usr/share/doc/coredoc"
cp -a "$ROOT/src/coredoc" "$BUILD/usr/lib/python3/dist-packages/"
cat > "$BUILD/usr/bin/coredoc" <<'PY'
#!/usr/bin/env python3
from coredoc.cli import main
raise SystemExit(main())
PY
chmod 0755 "$BUILD/usr/bin/coredoc"
gzip -c "$ROOT/man/coredoc.1" > "$BUILD/usr/share/man/man1/coredoc.1.gz"
cp "$ROOT/README.md" "$ROOT/docs/ARCHITECTURE.md" "$ROOT/docs/TRIAGE.md" "$ROOT/docs/SECURITY.md" "$BUILD/usr/share/doc/coredoc/"
cat > "$BUILD/DEBIAN/control" <<CTRL
Package: coredoc
Version: ${VERSION}-1
Section: admin
Priority: optional
Architecture: all
Maintainer: coredoc contributors <noreply@users.noreply.github.com>
Depends: python3 (>= 3.10), python3-textual
Description: modular TUI-based Linux diagnostics and first-aid tool
 coredoc wraps fragmented Linux diagnostic tools into a coherent Textual TUI
 that explains what is broken and what to check next.
CTRL
mkdir -p "$ROOT/dist"
dpkg-deb --build "$BUILD" "$ROOT/dist/coredoc_${VERSION}-1_all.deb"
dpkg-deb --contents "$ROOT/dist/coredoc_${VERSION}-1_all.deb" | grep -E 'usr/bin/coredoc|usr/share/man/man1/coredoc.1.gz' >/dev/null
