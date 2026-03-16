#!/usr/bin/env bash
# version-bump.sh — Bump the version of sven-integrations.
#
# Usage:
#   bash scripts/version-bump.sh <patch|minor|major>
#
# What it does:
#   1. Reads current version from VERSION file
#   2. Bumps the appropriate component
#   3. Updates VERSION and pyproject.toml
#   4. Commits with "chore: release vX.Y.Z"
#   5. Creates annotated git tag vX.Y.Z
#
# After running this, push with:
#   git push origin main --follow-tags
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

BUMP_TYPE="${1:-patch}"

if [[ ! "$BUMP_TYPE" =~ ^(patch|minor|major)$ ]]; then
    echo "Usage: $0 <patch|minor|major>" >&2
    exit 1
fi

# Read current version
CURRENT="$(cat "${ROOT}/VERSION" | tr -d '[:space:]')"

# Split into components
IFS='.' read -r MAJOR MINOR PATCH <<< "${CURRENT}"

# Bump
case "${BUMP_TYPE}" in
    patch) PATCH=$((PATCH + 1)) ;;
    minor) MINOR=$((MINOR + 1)); PATCH=0 ;;
    major) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
esac

NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}"
TAG="v${NEW_VERSION}"

echo "Bumping ${CURRENT} → ${NEW_VERSION} (${BUMP_TYPE})"

# Update VERSION file
echo "${NEW_VERSION}" > "${ROOT}/VERSION"

# Update pyproject.toml
sed -i "s/^version = \"${CURRENT}\"/version = \"${NEW_VERSION}\"/" "${ROOT}/pyproject.toml"

# Verify
TOML_VER=$(grep '^version = ' "${ROOT}/pyproject.toml" | head -1 | sed 's/version = "\(.*\)"/\1/')
if [[ "${TOML_VER}" != "${NEW_VERSION}" ]]; then
    echo "error: failed to update version in pyproject.toml" >&2
    echo "  expected: ${NEW_VERSION}, got: ${TOML_VER}" >&2
    exit 1
fi

# Commit
cd "${ROOT}"

if [[ -n "$(git status --porcelain)" ]]; then
    git add VERSION pyproject.toml
    git commit -m "chore: release v${NEW_VERSION}"
else
    echo "warning: nothing to commit" >&2
fi

# Tag
if git rev-parse "${TAG}" >/dev/null 2>&1; then
    echo "error: tag ${TAG} already exists" >&2
    exit 1
fi

git tag -a "${TAG}" -m "Release ${TAG}"

echo ""
echo "Version bumped to ${NEW_VERSION}"
echo "Tag ${TAG} created"
echo ""
echo "To push and trigger CI release:"
echo "  git push origin main --follow-tags"
