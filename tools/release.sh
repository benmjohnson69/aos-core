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

# Content hash of the bundle payload, computed BEFORE version.json is written
# so version.json (build metadata, not content) is naturally excluded. Same
# payload bytes -> same hash across rebuilds, regardless of version number.
CONTENT_HASH="$("${PYTHON}" - "${BUNDLE_TMP}/bundle" <<'PYH'
import hashlib
import sys
from pathlib import Path

root = Path(sys.argv[1])
lines = []
for p in sorted(root.rglob("*")):
    if p.is_file():
        relpath = p.relative_to(root).as_posix()
        filehash = hashlib.sha256(p.read_bytes()).hexdigest()
        lines.append(f"{relpath}:{filehash}")
combined = "\n".join(lines).encode()
print(hashlib.sha256(combined).hexdigest())
PYH
)"

cat > "${BUNDLE_TMP}/bundle/version.json" <<EOF
{
  "version": "v${NEXT_VERSION}",
  "built_at": "${BUILT_AT}",
  "git_sha": "${GIT_SHA}",
  "profile": "work",
  "schema": "aos-private-bundle.v1",
  "content_hash": "${CONTENT_HASH}"
}
EOF
echo "      Stamped version.json: v${NEXT_VERSION} (built_at=${BUILT_AT}, content_hash=${CONTENT_HASH:0:12}...)" >&2

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
# (f) OPTIONAL — publish the plugin tree to the PUBLIC aos-core repo
#     Closes the staging->public drift gap: (a)-(e) publish to the NAS only, so
#     the public repo that bootstrap.sh git-clones could silently fall behind the
#     mirror. Gated behind AOS_CORE_PUBLISH=1 — a public push is NEVER a silent
#     side effect of a NAS release. Fail-closed: refuses to push without a
#     banned-token gate; a publish failure never fails the (done) NAS release.
# ---------------------------------------------------------------------------
if [[ "${AOS_CORE_PUBLISH:-0}" == "1" ]]; then
    PUBLIC_REPO="${AOS_CORE_PUBLIC_REPO:-git@github.com:benmjohnson69/aos-core.git}"
    echo "[publish] Publishing plugin tree to public repo: ${PUBLIC_REPO}" >&2
    set +e
    (
        set -e
        PUB_TMP="$(mktemp -d)"
        trap 'rm -rf "${PUB_TMP}"' EXIT
        git clone --depth 1 "${PUBLIC_REPO}" "${PUB_TMP}/repo" >/dev/null 2>&1
        # sync the plugin tree over the clone; preserve the repo's own .git
        rsync -a --delete \
            --exclude='.git' --exclude='__pycache__' --exclude='.mypy_cache' --exclude='*.pyc' \
            "${PLUGIN_ROOT}/" "${PUB_TMP}/repo/"
        # fail-closed banned-token gate BEFORE any public push (canonical manifest list)
        "${PYTHON}" - "${PUB_TMP}/repo" "${PERSONAL_SOURCE}/bundle.manifest.json" <<'PYG'
import json, re, sys
from pathlib import Path
root, manifest_path = Path(sys.argv[1]), Path(sys.argv[2])
if not manifest_path.is_file():
    print("  [publish] ABORT: no bundle.manifest.json — refusing to push to PUBLIC without a gate", file=sys.stderr)
    sys.exit(3)
banned = [t for t in json.loads(manifest_path.read_text()).get("banned_tokens", []) if t.strip()]
if not banned:
    print("  [publish] ABORT: banned-token list empty — refusing to push to PUBLIC without a gate", file=sys.stderr)
    sys.exit(3)
B64 = re.compile(r'data:[^"\')\s]+|[A-Za-z0-9+/]{40,}={0,2}')  # strip embedded images before matching
SKIP_SUFFIX = {".tgz", ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".pyc", ".woff", ".woff2", ".ttf"}
hits = 0
for p in root.rglob("*"):
    if not p.is_file() or "/.git/" in str(p) or p.name == "banned_tokens.txt":
        continue
    if p.suffix.lower() in SKIP_SUFFIX:
        continue
    try:
        clean = B64.sub("", p.read_text(errors="ignore"))
    except (OSError, ValueError):
        continue
    for tok in banned:
        if re.search(re.escape(tok), clean, re.I):
            print(f"  [publish] LEAK '{tok}' in {p.relative_to(root)}", file=sys.stderr)
            hits += 1
if hits:
    print(f"  [publish] ABORT: {hits} banned-token hit(s) — NOT pushing to public.", file=sys.stderr)
    sys.exit(2)
print(f"  [publish] gate: 0 banned-token hits ({len(banned)} tokens) — safe to push ✓", file=sys.stderr)
PYG
        cd "${PUB_TMP}/repo"
        if [[ -z "$(git status --porcelain)" ]]; then
            echo "  [publish] public repo already current — no drift, nothing to push" >&2
        else
            git add -A
            git -c user.name="aos-core release" -c user.email="noreply@anthropic.com" \
                commit -q -m "chore(release): sync plugin tree from staging (bundle v${NEXT_VERSION})"
            git push origin HEAD >/dev/null 2>&1
            echo "  [publish] pushed plugin tree to public ($(git rev-parse --short HEAD))" >&2
        fi
    )
    PUB_RC=$?
    set -e
    if [[ "${PUB_RC}" -ne 0 ]]; then
        echo "  [publish] WARNING: publish failed (rc=${PUB_RC}); NAS release stands. Fix + re-run with AOS_CORE_PUBLISH=1." >&2
    fi
else
    echo "[publish] skipped (set AOS_CORE_PUBLISH=1 to also push the plugin tree to the public aos-core repo)" >&2
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo "" >&2
echo "=== Release complete ===" >&2
echo "  tarball : ${DRIVE_DIR}/${TARBALL_NAME}" >&2
echo "  mirror  : ${MIRROR_DEST}" >&2
echo "  version : v${NEXT_VERSION}" >&2
echo "  publish : ${AOS_CORE_PUBLISH:-0} (1 = pushed plugin tree to public aos-core)" >&2
echo "" >&2
