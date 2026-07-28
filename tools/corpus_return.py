#!/usr/bin/env python3
# owner_mission: sp-mac-corpus-return-2026-07-28
"""corpus_return.py — bring work-authored corpus entries HOME. The missing return lane.

WHY THIS IS LOAD-BEARING, NOT NICE-TO-HAVE
    The corpus flows one way: personal Mac -> NAS -> work Mac. Anything the work Mac
    AUTHORS exists in exactly one place, on the machine least likely to be backed up.
    It proved it the hard way: it moved the tree aside to test the installer, ran the
    installer, confirmed the counts, deleted the backup — and lost both of its own
    entries, because the installer faithfully restores the NAS payload and those were
    never on the NAS. The additive-never-delete guarantee was intact; it just cannot
    protect content the sender never had.

    Two entries in an 875-document corpus were authored work-side. Both were nearly
    lost. Without a return lane, every local wipe is permanent.

CONTRACT
    - Gated identically to the outbound path: denylist + PII/PHI category detectors.
      Content coming FROM the work Mac gets the same scrutiny as content going to it —
      it may quote logs, paths, or counterpart names.
    - Additive. Never deletes on either side; the NAS copy stays as the work Mac's own
      backup until it prunes.
    - Idempotent by content hash: re-running merges nothing new, so it is safe on a
      loop.
    - Idempotent ACROSS PATHS, not just within this lane's own destination. An entry
      whose content already exists anywhere under docs/solutions/ is reported as
      already-canonical and NOT placed a second time. A byte-identical twin at a
      second path is not free: surfacing runs on a fixed-size budget, so the duplicate
      spends a slot returning the same answer twice.
    - Conflicts never overwrite. A same-named entry with different content lands as
      `<name>.from-work-<hash>.md` and is reported — losing an entry to a silent
      overwrite is the exact failure this tool exists to prevent.

Usage:
    python3 corpus_return.py --check     # what would merge
    python3 corpus_return.py --merge

Env overrides (testing / alternate trees; unset = the real paths above):
    CORPUS_RETURN_ROOT      corpus root scanned for existing content
    CORPUS_RETURN_DEST      where returned entries land
    CORPUS_RETURN_INBOUND   os.pathsep-separated inbound dirs
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
from pathlib import Path

AOS = Path.home() / "aos"
# Where the work Mac stages entries. Both are read: `inbound/` is the intended lane,
# the attachments dir is where it staged before the lane existed.
INBOUND = [
    Path(p)
    for p in (
        os.environ["CORPUS_RETURN_INBOUND"].split(os.pathsep)
        if os.environ.get("CORPUS_RETURN_INBOUND")
        else [
            "/Volumes/tests/sp-mac-v1/sp-context/inbound",
            "/Volumes/tests/sp-mac-v1/blackboard/attachments/work-mac-authored-solutions",
        ]
    )
]
# CORPUS_ROOT is the dedupe scope: an entry already living ANYWHERE under it is not
# placed again. DEST is only where genuinely-new entries land.
CORPUS_ROOT = Path(os.environ.get("CORPUS_RETURN_ROOT") or AOS / "docs" / "solutions")
DEST = Path(os.environ.get("CORPUS_RETURN_DEST") or CORPUS_ROOT / "work-authored")
MANIFEST = AOS / "PERSONAL" / "bundle.manifest.json"
SKIP_NAMES = {"README.md", "INDEX.md"}


def _load_gate() -> tuple[list[str], object]:
    """Banned tokens + the shared category detector. Fail-closed on either."""
    if not MANIFEST.is_file():
        raise SystemExit(f"ERROR: manifest missing ({MANIFEST}) — refusing to merge ungated.")
    banned = [t.strip() for t in json.loads(MANIFEST.read_text()).get("banned_tokens", []) if t.strip()]
    if not banned:
        raise SystemExit("ERROR: banned_tokens empty — refusing to merge ungated.")
    spec = importlib.util.spec_from_file_location("_bsc", Path(__file__).parent / "build_sp_context.py")
    if not spec or not spec.loader:
        raise SystemExit("ERROR: cannot load category detectors — refusing to merge ungated.")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not getattr(mod, "_CATEGORY_DETECTORS", None):
        raise SystemExit("ERROR: category detectors empty — refusing to merge ungated.")
    return banned, mod


def _sha_full(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()


def _sha(text: str) -> str:
    """Short form — only ever used to name a conflict file, never to compare content."""
    return _sha_full(text)[:12]


def _corpus_index(root: Path) -> dict[str, list[Path]]:
    """{content_hash: [paths]} for every .md under `root`. One pass, ~900 files.

    This is the whole point of the cross-path check: the lane used to compare only
    against its own destination directory, so an entry that already existed at the
    corpus flat root landed a second time under work-authored/ and then burned a slot
    in the fixed-size surfacing budget returning itself twice.
    """
    index: dict[str, list[Path]] = {}
    if not root.is_dir():
        return index
    for p in sorted(root.rglob("*.md")):
        if not p.is_file() or p.name in SKIP_NAMES:
            continue
        try:
            index.setdefault(_sha_full(p.read_text(errors="ignore")), []).append(p)
        except OSError:
            continue
    return index


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(CORPUS_ROOT))
    except ValueError:
        return str(p)


def main() -> int:
    ap = argparse.ArgumentParser(description="Merge work-authored corpus entries home.")
    ap.add_argument("--merge", action="store_true", help="write; default is check-only")
    args = ap.parse_args()

    banned, gate = _load_gate()
    sources = [d for d in INBOUND if d.is_dir()]
    if not sources:
        print("  no inbound dir reachable (NAS mounted?) — nothing to do")  # c1-ok
        return 0

    existing = {p.name: _sha_full(p.read_text(errors="ignore")) for p in DEST.glob("*.md")} if DEST.is_dir() else {}
    corpus = _corpus_index(CORPUS_ROOT)
    merged = skipped = blocked = conflicts = canonical = collisions = 0

    for src in sources:
        for f in sorted(src.glob("*.md")):
            if f.name in SKIP_NAMES:
                continue
            try:
                text = f.read_text(errors="ignore")
            except OSError:
                continue

            hits = [t for t in banned if re.search(re.escape(t), text, re.I)]
            cats = gate.category_hits(text)  # type: ignore[attr-defined]
            if hits or cats:
                blocked += 1
                print(f"  BLOCKED {f.name}  denylist={hits} category={cats}")  # c1-ok
                continue

            h = _sha_full(text)
            target = DEST / f.name

            # Cross-path content check comes BEFORE the same-name check: identical
            # content already in the corpus is identical content, whatever it is called
            # or wherever it sits.
            twins = corpus.get(h, [])
            elsewhere = [p for p in twins if p != target]
            if target in twins and elsewhere:
                # Both. Do not silently pick a survivor — name the collision and let a
                # human decide which path is canonical.
                collisions += 1
                print(  # c1-ok
                    f"  COLLISION {f.name} — identical content at {_rel(target)} "
                    f"AND {', '.join(_rel(p) for p in elsewhere)}; placed nothing"
                )
                continue
            if elsewhere:
                canonical += 1
                print(f"  ALREADY CANONICAL {f.name} at {_rel(elsewhere[0])} — placed nothing")  # c1-ok
                continue
            if existing.get(f.name) == h:
                skipped += 1
                continue
            if f.name in existing:
                # Same name, different content. Never overwrite — that is how a
                # work-authored entry disappears without anyone noticing.
                target = DEST / f"{f.stem}.from-work-{h[:12]}.md"
                conflicts += 1
                print(f"  CONFLICT {f.name} differs — landing as {target.name}")  # c1-ok
            if args.merge:
                DEST.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, target)
            # Register it either way: two inbound dirs staging the same content under
            # different names must not both land in a single run.
            corpus.setdefault(h, []).append(target)
            merged += 1
            print(f"  {'MERGED ' if args.merge else 'WOULD MERGE'} {target.name}")  # c1-ok

    verb = "merged" if args.merge else "would merge"
    print(  # c1-ok
        f"\n  {verb}={merged}  unchanged={skipped}  already_canonical={canonical}  "
        f"collisions={collisions}  blocked={blocked}  conflicts={conflicts}"
    )
    if not args.merge and merged:
        print("  (re-run with --merge to write)")  # c1-ok
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
