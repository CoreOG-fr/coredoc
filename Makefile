PYTHON ?= python3
PKG_VERSION := 0.2.0

.PHONY: install uninstall test lint package-deb package-rpm package-arch package-flatpak package-alpine all clean

install:
	$(PYTHON) -m pip install .

uninstall:
	$(PYTHON) -m pip uninstall -y coredoc

test:
	$(PYTHON) -m pytest --cov=coredoc.backends --cov-report=term-missing

lint:
	$(PYTHON) -m ruff check src tests
	$(PYTHON) -m black --check src tests
	$(PYTHON) -m isort --check-only src tests
	$(PYTHON) -m mypy src

package-deb:
	mkdir -p dist
	if dpkg-checkbuilddeps >/dev/null 2>&1; then \
		dpkg-buildpackage -us -uc -b && mv ../coredoc_$(PKG_VERSION)-1_all.deb dist/ || true; \
	else \
		echo "Debian build dependencies missing; using dpkg-deb fallback builder."; \
		packaging/scripts/build_deb_manual.sh; \
	fi

package-rpm:
	mkdir -p dist
	cp packaging/rpm/coredoc.spec dist/
	@echo "RPM spec copied to dist/. Run packaging/scripts/test_in_fedora.sh to build in Fedora."

package-arch:
	mkdir -p dist
	cp packaging/arch/PKGBUILD dist/
	@echo "PKGBUILD copied to dist/. Run makepkg in a clean Arch environment."

package-alpine:
	mkdir -p dist
	cp packaging/alpine/APKBUILD dist/
	@echo "APKBUILD copied to dist/. Run abuild on Alpine."

package-flatpak:
	mkdir -p dist
	cp packaging/flatpak/io.github.coredoc.coredoc.yml dist/
	@if command -v flatpak-builder >/dev/null; then flatpak-builder --force-clean build-dir packaging/flatpak/io.github.coredoc.coredoc.yml; else echo "flatpak-builder not installed; manifest copied only"; fi

all: test lint package-deb package-rpm package-arch package-alpine package-flatpak

clean:
	rm -rf build dist *.egg-info .pytest_cache .coverage
