#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if command -v docker >/dev/null 2>&1; then RUNTIME=docker; elif command -v podman >/dev/null 2>&1; then RUNTIME=podman; else echo "Need docker or podman" >&2; exit 1; fi
"$RUNTIME" run --rm -v "$ROOT:/src:Z" fedora:latest bash -lc '
  set -euo pipefail
  dnf -y install rpm-build python3-devel python3-setuptools python3-wheel python3-pip tar gzip
  cd /src
  mkdir -p /tmp/rpmbuild/{SOURCES,SPECS}
  git init >/dev/null 2>&1 || true
  tar --exclude=.git -czf /tmp/rpmbuild/SOURCES/coredoc-0.2.0.tar.gz --transform s,^,coredoc-0.2.0/, .
  cp packaging/rpm/coredoc.spec /tmp/rpmbuild/SPECS/
  rpmbuild --define "_topdir /tmp/rpmbuild" -ba /tmp/rpmbuild/SPECS/coredoc.spec
'
