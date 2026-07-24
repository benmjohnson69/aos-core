#!/usr/bin/env bash
# aos-core/tools/release.sh — personal-Mac side release pipeline
#
# Build → gate → stamp → publish the work-profile identity bundle + plugin mirror.
#
# Usage:
#   release.sh [PERSONAL_SOURCE_DIR] [DRIVE_DIR]
#
# Defaults:
#   PERSONAL_SOURCE_DIR = ~/aos/PERSONAL
#   DRIVE_DIR           = /Volumes/tests/sp-mac-v1
#
# Steps:
#   (a) build_private_bundle.py --profile work (grep gate runs inside; fail-closed)
#   (b) stamp version.json into the bundle (auto-increment from existing tarballs at dest)
#   (c) tar to aos-private-work-vN.tgz in a temp dir
#   (d) copy tarball to DRIVE_DIR
#   (e) rsync aos-core tree (minus .git/__pycache__/.mypy_cache) to DRIVE_DIR/aos-core-mirror/
#
# Fail-closed: any step failure aborts immediately (set -euo pipefail).
# Idempotent: safe to run repeatedly; version number auto-increments on each run.

set -euo pipefail

# ---------------------------------------------------------------------------
# Arguments / defaults
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PERSONAL_SOURCE="${1:-${HOME}/aos/PERSONAL}"
DRIVE_DIR="${2:-/Volumes/tests/sp-mac-v1}"

# ---------------------------------------------------------------------------
# Resolve python3
# ---------------------------------------------------------------------------
PYTHON="${PYTHON3:-python3}"
if ! command -v "${PYTHON}" &>/dev/null; then
    echo "ERROR: python3 not found on PATH" >&2
    exit 1
fi

echo "=== aos-core release pipeline ===" >&2  # c1-ok (stderr diagnostic)
echo "  plugin root : ${PLUGIN_ROOT}" >&2
echo "  source      : ${PERSONAL_SOURCE}" >&2
echo "  drive dir   : ${DRIVE_DIR}" >&2
echo "" >&2

# ---------------------------------------------------------------------------
# Pre-flight: source + drive dirs
# ---------------------------------------------------------------------------
if [[ ! -d "${PERSONAL_SOURCE}" ]]; then
    echo "ERROR: PERSONAL source dir not found: ${PERSONAL_SOURCE}" >&2
    exit 1
fi

if [[ ! -d "${DRIVE_DIR}" ]]; then
    echo "ERROR: drive dir not found or not mounted: ${DRIVE_DIR}" >&2
    echo "  Mount the drive or pass a different path as \$2." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# (a) Build work-profile bundle into a temp dir (grep gate runs inside)
# ---------------------------------------------------------------------------
BUILD_SCRIPT="${PLUGIN_ROOT}/tools/build_private_bundle.py"
if [[ ! -f "${BUILD_SCRIPT}" ]]; then
    echo "ERROR: build_private_bundle.py not found at ${BUILD_SCRIPT}" >&2
    exit 1
fi

BUNDLE_TMP="$(mktemp -d)"
trap 'rm -rf "${BUNDLE_TMP}"' EXIT

echo "[1/5] Building work-profile bundle (grep gate runs inside build script)..." >&2
"${PYTHON}" "${BUILD_SCRIPT}" \
    --source "${PERSONAL_SOURCE}" \
    --profile work \
    --out "${BUNDLE_TMP}/bundle"

# build_private_bundle.py exits non-zero on gate failure — set -e catches it.
# If we reach here, the bundle passed the grep gate.
echo "      Bundle built + gate passed: ${BUNDLE_TMP}/bundle" >&2

# ---------------------------------------------------------------------------
# (b) Auto-increment version number from existing tarballs at DRIVE_DIR
# ---------------------------------------------------------------------------
echo "[2/5] Determining next version number..." >&2

NEXT_VERSION=1
for f in "${DRIVE_DIR}"/aos-private-work-v*.tgz; do
    [[ -f "${f}" ]] || continue
    fname="$(basename "${f}")"
    # Extract N from aos-private-work-vN.tgz
    if [[ "${fname}" =~ ^aos-private-work-v([0-9]+)\.tgz$ ]]; then
        num="${BASH_REMATCH[1]}"
        if (( num >= NEXT_VERSION )); then
            NEXT_VERSION=$(( num + 1 ))
        fi
    fi
done

echo "      Next version: v${NEXT_VERSION}" >&2

# Write version.json into the bundle
GIT_SHA=""
if command -v git &>/dev/null && git -C "${PLUGIN_ROOT}" rev-parse HEAD &>/dev/null 2>&1; then
    GIT_SHA="$(git -C "${PLUGIN_ROOT}" rev-parse --short HEAD 2>/dev/null || true)"
fi
BUILT_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

cat > "${BUNDLE_TMP}/bundle/version.json" <<EOF
{
  "version": "v${NEXT_VERSION}",
  "built_at": "${BUILT_AT}",
  "git_sha": "${GIT_SHA}",
  "profile": "work",
  "schema": "aos-private-bundle.v1"
}
EOF
echo "      Stamped version.json: v${NEXT_VERSION} (built_at=${BUILT_AT})" >&2

# ---------------------------------------------------------------------------
# (c) Tar to aos-private-work-vN.tgz
# ---------------------------------------------------------------------------
TARBALL_NAME="aos-private-work-v${NEXT_VERSION}.tgz"
TARBALL_PATH="${BUNDLE_TMP}/${TARBALL_NAME}"

echo "[3/5] Creating tarball: ${TARBALL_NAME}..." >&2
tar -czf "${TARBALL_PATH}" -C "${BUNDLE_TMP}" bundle
echo "      Tarball size: $(du -sh "${TARBALL_PATH}" | cut -f1)" >&2

# ---------------------------------------------------------------------------
# (d) Copy tarball to DRIVE_DIR
# ---------------------------------------------------------------------------
echo "[4/5] Copying tarball to drive: ${DRIVE_DIR}/${TARBALL_NAME}..." >&2
cp "${TARBALL_PATH}" "${DRIVE_DIR}/${TARBALL_NAME}"
echo "      Copied." >&2

# ---------------------------------------------------------------------------
# (e) Rsync plugin tree to DRIVE_DIR/aos-core-mirror/
# ---------------------------------------------------------------------------
MIRROR_DEST="${DRIVE_DIR}/aos-core-mirror/"
echo "[5/5] Rsyncing aos-core plugin to ${MIRROR_DEST}..." >&2
rsync -a --delete \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='.mypy_cache' \
    --exclude='*.pyc' \
    "${PLUGIN_ROOT}/" "${MIRROR_DEST}"
echo "      Mirror updated." >&2

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo "" >&2
echo "=== Release complete ===" >&2
echo "  tarball : ${DRIVE_DIR}/${TARBALL_NAME}" >&2
echo "  mirror  : ${MIRROR_DEST}" >&2
echo "  version : v${NEXT_VERSION}" >&2
echo "" >&2
