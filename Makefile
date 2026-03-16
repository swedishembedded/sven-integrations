VERSION := $(shell cat VERSION | tr -d '[:space:]')
TAG     := v$(VERSION)
DIST    ?= dist
DEB_OUT := target/debian
SKILLS_SYSTEM := /usr/local/share/sven/skills

.PHONY: all build test install deb deb/release clean fmt check help \
        release/build release/tag release/publish \
        release/patch release/minor release/major \
        _require-git-clean

all: build

## build     – install package in editable mode (development)
build:
	pip install -e ".[dev]" --quiet

## test      – run all unit tests
test:
	pytest src/ -v --tb=short

## check     – lint with ruff and type-check with mypy
check:
	ruff check src/ tests/
	mypy src/ --ignore-missing-imports --no-error-summary || true

## fmt       – auto-format code
fmt:
	ruff format src/ tests/

## install   – install to /usr/local (system-wide, requires root or sudo)
install:
	pip install ".[all]" --prefix=/usr/local --quiet
	install -d "$(SKILLS_SYSTEM)"
	cp -r skills/integrations "$(SKILLS_SYSTEM)/"
	@echo ""
	@echo "Installed sven-integrations v$(VERSION)"
	@echo "Skills: $(SKILLS_SYSTEM)/integrations/"
	@echo "Binaries: /usr/local/bin/sven-integrations-*"

## uninstall – remove from /usr/local
uninstall:
	pip uninstall sven-integrations -y || true
	rm -rf "$(SKILLS_SYSTEM)/integrations"

## deb       – build Debian package (output in target/debian/)
deb: deb/release

## deb/release – build optimised Debian package
deb/release:
	@bash scripts/build-deb.sh --out-dir $(DEB_OUT)

## clean     – remove build artifacts
clean:
	rm -rf target/ dist/ build/ *.egg-info src/*.egg-info
	find src/ -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find src/ -name "*.pyc" -delete 2>/dev/null || true

# ── Release targets ───────────────────────────────────────────────────────────

## release/build   – build release artifacts for current platform into dist/
release/build: clean deb/release
	@mkdir -p $(DIST)
	@cp target/debian/sven-integrations_*.deb $(DIST)/ 2>/dev/null || true
	@echo "Artifacts in $(DIST)/"

## release/tag     – create annotated git tag for current version and push
release/tag: _require-git-clean
	@echo "Current version: $(VERSION)"
	@if git rev-parse "$(TAG)" >/dev/null 2>&1; then \
	    echo "error: tag $(TAG) already exists. Bump the version first."; \
	    exit 1; \
	fi
	@echo "Tagging $(TAG) on $$(git rev-parse --short HEAD)..."
	@git tag -a "$(TAG)" -m "Release $(TAG)"
	@git push origin "$(TAG)"
	@echo "Tag $(TAG) pushed — GitHub Actions release workflow will start."

## release/publish – create a GitHub Release and upload dist/ artifacts via gh CLI
release/publish:
	@if [ -z "$$(ls $(DIST)/sven-integrations-* 2>/dev/null)" ]; then \
	    echo "error: no artifacts found in $(DIST)/"; \
	    echo "       Run 'make release/build' first."; \
	    exit 1; \
	fi
	@if ! command -v gh >/dev/null 2>&1; then \
	    echo "error: gh CLI not found (https://cli.github.com/)"; \
	    exit 1; \
	fi
	@ARTIFACTS=$$(find $(DIST) -maxdepth 1 -type f | sort | tr '\n' ' '); \
	gh release create "$(TAG)" \
	    --title "sven-integrations $(TAG)" \
	    --generate-notes \
	    $$ARTIFACTS
	@echo "Release: https://github.com/swedishembedded/sven-integrations/releases/tag/$(TAG)"

## release/patch   – bump patch version, run tests, tag, push → triggers CI
release/patch: test _require-git-clean
	@bash scripts/version-bump.sh patch
	@git push origin main --follow-tags

## release/minor   – bump minor version, run tests, tag, push → triggers CI
release/minor: test _require-git-clean
	@bash scripts/version-bump.sh minor
	@git push origin main --follow-tags

## release/major   – bump major version, run tests, tag, push → triggers CI
release/major: test _require-git-clean
	@bash scripts/version-bump.sh major
	@git push origin main --follow-tags

# Guard: fail if working tree is dirty
_require-git-clean:
	@if [ -n "$$(git status --porcelain)" ]; then \
	    echo "error: working tree is dirty. Commit your changes first."; \
	    git status --short; \
	    exit 1; \
	fi

## help      – list all targets
help:
	@echo ""
	@echo "sven-integrations $(VERSION)"
	@echo ""
	@grep -E '^## ' Makefile | sed 's/## /  /' | column -t -s '–'
	@echo ""
