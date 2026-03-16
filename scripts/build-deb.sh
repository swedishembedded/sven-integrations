#!/usr/bin/env bash
# build-deb.sh — Build a Debian package for sven-integrations.
#
# Usage:
#   bash scripts/build-deb.sh [OPTIONS]
#
# Options:
#   --out-dir DIR   Output directory (default: target/debian/)
#   --arch ARCH     Target architecture: amd64, arm64 (default: current)
#   --venv DIR      Python venv to install from (default: .venv)
#
# Prerequisites: dpkg-deb, python3, pip
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

OUT_DIR="${ROOT}/target/debian"
ARCH_OVERRIDE=""
VENV_DIR="${ROOT}/.venv"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --out-dir)  OUT_DIR="$2";       shift 2 ;;
        --arch)     ARCH_OVERRIDE="$2"; shift 2 ;;
        --venv)     VENV_DIR="$2";      shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

if ! command -v dpkg-deb &>/dev/null; then
    echo "error: dpkg-deb not found. Install the 'dpkg' package." >&2
    exit 1
fi

if [[ -n "${ARCH_OVERRIDE}" ]]; then
    ARCH="${ARCH_OVERRIDE}"
else
    ARCH="$(dpkg --print-architecture)"
fi

VERSION="$(cat "${ROOT}/VERSION" | tr -d '[:space:]')"
PKG_NAME="sven-integrations_${VERSION}_${ARCH}"
STAGING="${ROOT}/target/debian-staging/${PKG_NAME}"

echo "Building ${PKG_NAME}.deb"

# Create staging tree
rm -rf "${STAGING}"
install -d \
    "${STAGING}/DEBIAN" \
    "${STAGING}/usr/bin" \
    "${STAGING}/usr/share/sven/skills/integrations" \
    "${STAGING}/usr/share/doc/sven-integrations"

# Install Python package into staging
SITE_PACKAGES="${STAGING}/usr/lib/python3/dist-packages"
install -d "${SITE_PACKAGES}"

# Build and install the wheel
cd "${ROOT}"
python3 -m pip install --quiet build 2>/dev/null || true
python3 -m build --wheel --outdir "${ROOT}/target/wheels/" >/dev/null 2>&1

WHEEL=$(ls "${ROOT}/target/wheels/"sven_integrations-*.whl 2>/dev/null | tail -1)
if [[ -z "${WHEEL}" ]]; then
    echo "error: no wheel found in target/wheels/" >&2
    exit 1
fi

# Install only the wheel itself, without bundling its dependencies.
# click and other runtime deps are declared as Debian package dependencies
# (python3-click) so dpkg resolves them from the system, avoiding file
# conflicts with packages like python3-click already installed on the host.
python3 -m pip install --quiet \
    --target "${SITE_PACKAGES}" \
    --no-compile \
    --no-deps \
    "${WHEEL}"

# Create wrapper scripts in /usr/bin for each entry point
TOOLS=(
    gimp blender inkscape audacity libreoffice
    obs-studio kdenlive shotcut zoom drawio mermaid anygen comfyui
)
MODULES=(
    gimp blender inkscape audacity libreoffice
    obs_studio kdenlive shotcut zoom drawio mermaid anygen comfyui
)

for i in "${!TOOLS[@]}"; do
    tool="${TOOLS[$i]}"
    module="${MODULES[$i]}"
    wrapper="${STAGING}/usr/bin/sven-integrations-${tool}"
    cat > "${wrapper}" <<EOF
#!/usr/bin/env python3
import sys
sys.path.insert(0, "/usr/lib/python3/dist-packages")
from sven_integrations.${module}.cli import main
if __name__ == "__main__":
    main()
EOF
    chmod 755 "${wrapper}"
done

# Install skills
cp -r "${ROOT}/skills/integrations/." "${STAGING}/usr/share/sven/skills/integrations/"

# Copyright file
cat > "${STAGING}/usr/share/doc/sven-integrations/copyright" <<EOF
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: sven-integrations

Files: *
Copyright: 2024 Sven Contributors
License: Apache-2.0
EOF

# Installed-size
INST_SIZE="$(du -sk "${STAGING}" | cut -f1)"

# DEBIAN/control
cat > "${STAGING}/DEBIAN/control" <<EOF
Package: sven-integrations
Version: ${VERSION}
Architecture: ${ARCH}
Maintainer: Sven Contributors <team@agentsven.com>
Installed-Size: ${INST_SIZE}
Depends: python3 (>= 3.10), python3-click
Recommends: python3-lxml, python3-pil, ffmpeg
Section: utils
Priority: optional
Description: Sven agent tool harnesses for desktop application control
 sven-integrations provides structured CLI interfaces for controlling desktop
 applications including GIMP, Blender, Inkscape, Audacity, LibreOffice,
 OBS Studio, Kdenlive, Shotcut, Zoom, Draw.io, Mermaid, AnyGen, and
 ComfyUI. Each tool installs as a sven skill under
 /usr/share/sven/skills/integrations/.
EOF

# DEBIAN/postinst
cat > "${STAGING}/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
exit 0
EOF
chmod 755 "${STAGING}/DEBIAN/postinst"

# Build the package
mkdir -p "${OUT_DIR}"
DEB_PATH="${OUT_DIR}/${PKG_NAME}.deb"
dpkg-deb --build --root-owner-group "${STAGING}" "${DEB_PATH}"

echo ""
echo "Package built: ${DEB_PATH}"
echo "To install:  sudo dpkg -i ${DEB_PATH}"
