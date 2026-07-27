#!/usr/bin/env python3
"""build_sp_context.py — build the 5th leg: SITUATIONAL context (the missing corpus).

WHY THIS EXISTS
    sp-mac-v1 shipped mechanism (aos-core) + identity (private bundle) and had no
    leg for *content*. Nine consumers — prior-fix surfacing, feature registry,
    handoff resume, memory recall — install correctly and then fire against empty
    corpora forever. They work; they just have nothing to say. Doctor reports GREEN
    because every mechanism is healthy: the blind spot is one plane up.

DIFFERENCE FROM build_private_bundle.py
    That builds IDENTITY (who Ben is) and is all-or-nothing fail-closed: one banned
    token deletes the bundle, because an identity bundle is small and a leak there is
    categorical. This builds SITUATIONAL knowledge (what we've learned) from a 371-file
    corpus where a handful of entries incidentally name family. All-or-nothing would
    throw away 368 good entries to avoid 3 bad ones, so the gate here is PER-FILE:
    a hit excludes that file and is REPORTED — never silently dropped, never fatal.

Usage:
    python3 build_sp_context.py --out <dir> [--manifest PATH] [--source PATH] [--dry-run]

Exit: 0 built, 1 bad input, 2 nothing shippable (every candidate was excluded).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

# Strip embedded base64/data-URI blobs before matching so binary payloads can't
# produce phantom substring hits (an image's bytes are not a leak).
B64 = re.compile(r'data:[^"\')\s]+|[A-Za-z0-9+/]{40,}={0,2}')


def load_banned(manifest: Path) -> list[str]:
    """Banned tokens from the canonical manifest. Fail-closed: no list = no build."""
    if not manifest.is_file():
        raise SystemExit(f"ERROR: manifest not found: {manifest} — refusing to build ungated.")
    toks = [t.strip() for t in json.loads(manifest.read_text()).get("banned_tokens", []) if t.strip()]
    if not toks:
        raise SystemExit(f"ERROR: banned_tokens empty in {manifest} — refusing to build ungated.")
    return toks


def scan(text: str, banned: list[str]) -> list[str]:
    clean = B64.sub("", text)
    return [t for t in banned if re.search(re.escape(t), clean, re.I)]


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the situational-context leg (gated per file).")
    ap.add_argument("--out", required=True, type=Path, help="output dir (e.g. releases/sp-mac-v1/sp-context)")
    ap.add_argument("--source", type=Path, default=Path.home() / "aos" / "docs" / "solutions",
                    help="solutions corpus root")
    ap.add_argument("--manifest", type=Path, default=Path.home() / "aos" / "PERSONAL" / "bundle.manifest.json")
    ap.add_argument("--dry-run", action="store_true", help="report what would ship; write nothing")
    args = ap.parse_args()

    src: Path = args.source.expanduser()
    if not src.is_dir():
        print(f"ERROR: --source not a dir: {src}", file=sys.stderr)  # c1-ok
        return 1

    banned = load_banned(args.manifest.expanduser())
    out: Path = args.out.expanduser()
    dest = out / "solutions"

    shipped: list[Path] = []
    excluded: list[tuple[Path, list[str]]] = []
    for p in sorted(src.rglob("*.md")):
        rel = p.relative_to(src)
        try:
            hits = scan(p.read_text(errors="ignore"), banned)
        except OSError:
            continue
        if hits:
            excluded.append((rel, hits))
            continue
        shipped.append(rel)

    if not shipped:
        print("ERROR: every candidate was excluded — nothing to ship.", file=sys.stderr)  # c1-ok
        return 2

    if not args.dry_run:
        if dest.exists():
            shutil.rmtree(dest)
        for rel in shipped:
            tgt = dest / rel
            tgt.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src / rel, tgt)
        # Ship the exclusion list WITH the corpus. The receiving machine must know
        # its knowledge has holes and where they are — a silently-truncated corpus
        # reads as "this is everything we know", which is worse than a known gap.
        (out / "EXCLUDED.md").write_text(
            "# Excluded from the situational corpus\n\n"
            f"{len(excluded)} of {len(shipped) + len(excluded)} entries were withheld because they\n"
            "contain personal-identifier tokens from the canonical banned list. They are\n"
            "NOT lost — they live on the personal Mac. If one is needed work-side, it must\n"
            "be scrubbed and re-sent deliberately.\n\n"
            # Deliberately does NOT print which token matched. This file ships, and
            # echoing the banned value into a shipped artifact reproduces the very
            # thing the gate exists to keep out (and self-trips the next scan). The
            # operator sees the tokens on stdout at build time; the receiver only
            # needs to know WHICH entries are missing.
            + "".join(f"- `{f}` — {len(h)} personal-token match(es)\n" for f, h in excluded)
            + "\nRegenerate: `python3 aos-core/tools/build_sp_context.py --out <pkg>/sp-context`\n",
            encoding="utf-8",
        )

    verb = "would ship" if args.dry_run else "shipped"
    print(f"sp-context: {verb} {len(shipped)} entries, excluded {len(excluded)} → {dest}")  # c1-ok
    for f, h in excluded:
        print(f"  EXCLUDED {f} [{', '.join(h)}]")  # c1-ok
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
