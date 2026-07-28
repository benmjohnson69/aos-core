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


# ── PII/PHI category detectors — SHARED with the bundle builder (U1 fix) ───────
# The bundle builder got shape-based detectors; this one did not, and shipped Ben's
# actual drug-interaction analysis into a corpus that `pretooluse-solution-surface`
# rglobs and injects into context on EVERY edit. The bundle's PHI merely sat at rest;
# this was on a live path into context, on 875 files instead of 8.
#
# Imported rather than copied ON PURPOSE. Two gates that can drift apart is the defect
# itself — the whole bug was that one got fixed and the other didn't. One definition,
# both consumers; a fix to either is a fix to both.
_CATEGORY_DETECTORS: list[tuple[str, "re.Pattern[str]"]] = []
try:
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location("_bpb", Path(__file__).parent / "build_private_bundle.py")
    if _spec and _spec.loader:
        _bpb = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_bpb)
        _CATEGORY_DETECTORS = list(_bpb.CATEGORY_DETECTORS)
except Exception:  # noqa: BLE001 — see fail-closed check below
    _CATEGORY_DETECTORS = []

# Medication stems, used for the co-occurrence rule below.
_MED_STEM = re.compile(r"\b\w{2,}(?:cillin|mycin|cycline|statin|prazole|sartan|olol|opril|"
                       r"azepam|tidine|dronate|glutide|afinil|thyroxine)\b", re.I)
_DOSE = re.compile(r"\b\d+\s?(?:mg|mcg|ml|iu)\b", re.I)


def category_hits(text: str) -> list[str]:
    """Shape-based PII/PHI detection. Returns list of category labels found.

    Precision tuning (work-Mac U1 note): a bare `\\d+ ?mg` fires on business writing
    (a Pax8 GTM brief, a card-heading doc). A noisy gate gets bypassed, and a bypassed
    gate protects nothing — so `dosage` alone is not a hit unless a medication stem
    appears nearby. Recall is preserved because the medication detector still fires on
    the stem by itself.
    """
    out: list[str] = []
    for label, rx in _CATEGORY_DETECTORS:
        if not rx.search(text):
            continue
        # NOTE the label is "dosage-schedule", not "dosage" — matching the wrong string
        # here silently disables the co-occurrence guard, which is how "500 mg card
        # heading" kept flagging a Pax8 brief as PHI.
        if label == "dosage-schedule" and not _MED_STEM.search(text):
            continue          # a dose with no drug name is business prose, not PHI
        out.append(label)
    if "medication" not in out and _MED_STEM.search(text) and _DOSE.search(text):
        out.append("medication")
    return out


# ── Additional slices (2026-07-27) ──────────────────────────────────────────────
# The work Mac measured 365/370 corpus entries as infrastructure and concluded the
# compound loop had never been pointed at the actual job. It hadn't — but the cause
# wasn't a missing corpus, it was a corpus builder that only ever read one directory.
# The business material was on a shelf nobody looked at. These slices add the other
# shelves, each with its own filter because the shelves differ in kind.
#
# INTEL is mostly ephemeral: 46 morning briefs and ~60 Notion snapshots are daily
# digests and raw dumps, not learnings. Shipping them would dilute match precision
# for no gain (the work Mac already flagged precision decay as the risk at 370
# entries). Only the analysis documents travel — and because intel is ABOUT people,
# it gets folio treatment: comp figures stripped, verdict language gated.
#
# HANDOFFS are the lane history the work Mac explicitly asked for (S4). Only the
# SP-relevant ones; the infra handoffs are already covered by docs/solutions.
EPHEMERAL_INTEL = re.compile(r"morning-brief|notion-snapshot|^daily-|-snapshot-", re.I)
SP_RELEVANT = re.compile(r"sourcepass|liberty|chuck|marcus|ctro|qbr|client|pax8|"
                         r"acquisition|integration|reorg|board", re.I)
# Currency adjacent to compensation context — third-party pay on employer hardware.
MONEY_RE = re.compile(r"[~≈]?\$\s?\d[\d,.]*\s?(?:[KMB]\b|million|billion)?", re.I)
COMP_CTX = re.compile(r"retention|earnout|salary|comp\b|package|bonus|equity|car\b", re.I)
SHARP = ["political-risk", "blind spot", "resistance point", "under-resourced",
         "overloaded", "ally under strain", "threatened", "incompetent", "liability"]


def folio_clean(text: str) -> tuple[str, list[str]]:
    """Strip third-party figures; report verdict-language lines. Same contract as the
    bundle builder's folio_normalize — figures are mechanical, phrasing is judgment."""
    out, sharp = [], []
    for i, line in enumerate(text.splitlines(), 1):
        if COMP_CTX.search(line) and MONEY_RE.search(line):
            line = MONEY_RE.sub("[figure withheld]", line)
        low = line.lower()
        for term in SHARP:
            if term in low:
                sharp.append(f"L{i}: {term}")
                break
        out.append(line)
    return "\n".join(out), sharp


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
    # Fail closed. A silent import failure here would restore exactly the blindness
    # this fix exists to remove, and it would look like a clean build.
    if not _CATEGORY_DETECTORS:
        print("ERROR: PII/PHI category detectors failed to load from "  # c1-ok
              "build_private_bundle.py — refusing to build with denylist only.", file=sys.stderr)
        return 1
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
        cat = category_hits(p.read_text(errors="ignore"))
        if cat:
            excluded.append((rel, [f"category:{c}" for c in cat]))
            continue
        shipped.append(rel)

    if not shipped:
        print("ERROR: every candidate was excluded — nothing to ship.", file=sys.stderr)  # c1-ok
        return 2

    # ── extra slices: intel (folio-treated) + SP-relevant handoffs ──────────────
    extra: list[tuple[str, Path, Path]] = []   # (label, src_file, dest_rel)
    sharp_flagged: list[str] = []
    home = Path.home() / "aos"
    for label, root, keep in (
        ("intel", home / "data" / "intel", lambda r: not EPHEMERAL_INTEL.search(r)),
        ("handoffs", home / "docs" / "session-handoffs", lambda r: bool(SP_RELEVANT.search(r))),
    ):
        if not root.is_dir():
            continue
        for f in sorted(root.rglob("*.md")):
            rel_s = str(f.relative_to(root))
            try:
                text = f.read_text(errors="ignore")
            except OSError:
                continue
            # handoffs match on CONTENT (filenames are mission slugs); intel on name.
            probe: str = rel_s if label == "intel" else rel_s + "\n" + text[:4000]
            if not keep(probe):
                continue
            if scan(text, banned):
                excluded.append((Path(label) / rel_s, ["denylist"]))
                continue
            cat_e = category_hits(text)
            if cat_e:
                excluded.append((Path(label) / rel_s, [f"category:{c}" for c in cat_e]))
                continue
            # Intel carrying bare currency is held: these are third-party deal/revenue
            # figures from meetings, not obviously comp, and folio_clean only strips
            # currency ADJACENT to comp context. Whether a counterparty's deal size
            # travels to employer hardware is Ben's call, not a regex's — so hold and
            # report rather than guess in either direction.
            if label == "intel" and re.search(r"\$\s?\d", text):
                excluded.append((Path(label) / rel_s, ["unclassified-currency"]))
                continue
            extra.append((label, f, Path(label) / rel_s))

    if not shipped and not extra:
        print("ERROR: every candidate was excluded — nothing to ship.", file=sys.stderr)  # c1-ok
        return 2

    if not args.dry_run:
        if dest.exists():
            shutil.rmtree(dest)
        for rel in shipped:
            tgt = dest / rel
            tgt.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src / rel, tgt)
        for label, f, rel in extra:
            body = f.read_text(errors="ignore")
            if label == "intel":       # intel is ABOUT people — folio rules apply
                body, sharp = folio_clean(body)
                if sharp:
                    sharp_flagged.append(f"{rel}: {', '.join(sharp[:2])}")
            tgt_path = out / rel
            tgt_path.parent.mkdir(parents=True, exist_ok=True)
            tgt_path.write_text(body, encoding="utf-8")
        if sharp_flagged:
            # Named, not silently shipped and not silently dropped — same contract as
            # the bundle's folio gate. These need a human reword in the SOURCE.
            print(f"  folio: {len(sharp_flagged)} intel line(s) carry verdict language:", file=sys.stderr)  # c1-ok
            for s in sharp_flagged[:8]:
                print(f"    {s}", file=sys.stderr)  # c1-ok
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
