#!/usr/bin/env python3
"""aos-core: build a profile-scoped ~/.aos-private bundle from a personal corpus.

THE SAFETY SPINE for the content layer. The plugin is content-free; personal content lives in
~/.aos-private/. This tool assembles that bundle from your source corpus, applying a PROFILE
allowlist so a work machine only ever receives explicitly-marked work-safe content.

Two mechanisms, belt + suspender:
  1. Allowlist parse (belt) — the corpus is split into segments by markdown headers and by
     `[SCOPE: work-safe]` / `[SCOPE: personal-only]` markers. Each segment inherits the most
     recent scope; UNMARKED defaults to `personal-only`. The `work` profile keeps ONLY work-safe
     segments. An allowlist can only ever under-include — it cannot leak by omission.
  2. Grep gate (suspender) — after building, the output is scanned for a banned-token list. Any
     hit FAILS the build and deletes the partial bundle (fail-closed). Even if the parse is
     imperfect, a leaked token cannot reach disk.

Content-free by construction: this tool hardcodes NO names/facts (unlike the legacy
build_personal_fresh_state.py). It reads scope markers + a manifest; all personal data comes from
--source at runtime. Safe to ship inside the portable plugin.

Usage:
    build_private_bundle.py --source ~/aos/PERSONAL --profile work --out ~/.aos-private
    build_private_bundle.py --source ~/aos/PERSONAL --profile personal --out ~/.aos-private \\
        --memory-source ~/.claude/projects/<proj>/memory --dry-run

Exit codes: 0 = built + verified; 2 = grep gate caught a leak (bundle deleted); 1 = usage/IO error.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

# Scope model: unmarked content is personal-only (fail-safe). Each profile lists the scopes it admits.
#
# `folio-safe` (2026-07-26) — counterpart profiles: Ben's own working assessments of
# colleagues. These are the highest-value unshipped asset ("knows the people I work
# with"), and there is no ownership question — he wrote them. The risk is not the
# CONCLUSION, it is the PROVENANCE: "tends to re-litigate in writing, get it in email"
# is a working note; "on the 3/14 call he said «...»" is a recording derivative, and it
# reads very differently if the file is ever read by someone other than Ben on
# company-issued hardware. So folio-safe content ships, but goes through
# strip_provenance() first — conclusions travel, sourcing does not.
PROFILE_SCOPES: dict[str, set[str]] = {
    "work": {"work-safe", "folio-safe"},
    "personal": {"work-safe", "folio-safe", "personal-only"},
}
DEFAULT_SCOPE = "personal-only"

# Lines that attribute a claim to a recording/meeting/private channel. The claim may
# travel; the sourcing may not. Applied ONLY to folio-safe segments.
PROVENANCE_RE = re.compile(
    r"(on the .{0,30}\bcall\b|in the .{0,30}\b(meeting|1:1|one-on-one)\b"
    r"|per the (transcript|recording|tape)|\btranscript\b|\brecording\b"
    r"|\bplaud\b|said (that )?[\"“«]|\bquote[ds]?\b[:,]|\[\d{2}:\d{2}(:\d{2})?\])",
    re.IGNORECASE,
)


# FOLIO NORMALIZATION — Ben's ruling, work-Mac's rule, encoded.
#
#   "Would Ben be comfortable if this line were read aloud by the person it
#    describes? If no, REWORD to carry the same operating meaning — don't delete
#    the insight."
#
# Deletion loses the value; rewording keeps it and survives disclosure. Two halves,
# and only one can be automated honestly:
#   FIGURES  — mechanical. Third-party compensation on an employer-owned machine is
#              the sharpest edge here and it is pure pattern. Replaced, not deleted,
#              so "retention package in place" still tells you how to act.
#   PHRASING — judgment. A gate NAMES the line and fails closed rather than pretending
#              a regex can reword "political-risk relationship" into something that
#              keeps the meaning. Automating that would quietly destroy the insight.
_MONEY_RE = re.compile(r"[~≈]?\$\s?\d[\d,.]*\s?(?:[KMB]\b|million|billion)?", re.I)
_COMP_CONTEXT_RE = re.compile(r"retention|earnout|salary|comp\b|package|bonus|equity|car\b", re.I)
# Language that reads as a verdict on a person rather than a note on how to work with them.
SHARP_LANGUAGE = [
    "political-risk", "blind spot", "resistance point", "resistant", "overloaded",
    "under-resourced", "ally under strain", "weak", "liability", "problem child",
    "empire", "threatened", "insecure", "incompetent",
]


def folio_normalize(text: str) -> tuple[str, list[str]]:
    """Strip third-party figures; return (text, sharp_lines_needing_manual_reword)."""
    out, sharp = [], []
    for i, line in enumerate(text.splitlines(), 1):
        if _COMP_CONTEXT_RE.search(line) and _MONEY_RE.search(line):
            line = _MONEY_RE.sub("[figure withheld]", line)
        low = line.lower()
        for term in SHARP_LANGUAGE:
            if term in low:
                sharp.append(f"L{i}: '{term}' — {line.strip()[:66]}")
                break
        out.append(line)
    return "\n".join(out), sharp


def strip_provenance(text: str) -> tuple[str, int]:
    """Drop lines that source a claim to a recording/meeting. Returns (text, n_dropped).

    Deliberately line-granular and conservative: a folio line that cites how Ben knows
    something is removed whole rather than partially redacted, because a half-scrubbed
    quote still reproduces the sensitive part.
    """
    kept, dropped = [], 0
    for line in text.splitlines():
        if PROVENANCE_RE.search(line):
            dropped += 1
            continue
        kept.append(line)
    return "\n".join(kept), dropped
SCOPE_RE = re.compile(r"\[SCOPE:\s*([a-z-]+)\s*\]", re.IGNORECASE)
HEADER_RE = re.compile(r"^#{1,6}\s")
UPDATED_RE = re.compile(r"\[Updated\s+(\d{4}-\d{2}-\d{2})")


def load_manifest(source: Path) -> dict:
    """Manifest declares banned_tokens (grep gate) + anchor_file. Absent → conservative defaults."""
    mpath = source / "bundle.manifest.json"
    if mpath.is_file():
        try:
            return json.loads(mpath.read_text())
        except (OSError, ValueError):
            pass
    return {"banned_tokens": [], "anchor_file": "IDENTITY.md"}


def segment_scopes(text: str, profile_scopes: set[str]) -> str:
    """Return only the lines whose active scope is admitted by the profile.

    A header line resets scope to DEFAULT_SCOPE (so a new section can't inherit a prior work-safe
    marker by accident). A `[SCOPE: x]` line sets the active scope for subsequent lines.
    """
    kept: list[str] = []
    active = DEFAULT_SCOPE
    for line in text.splitlines():
        if HEADER_RE.match(line):
            active = DEFAULT_SCOPE  # headers reset — fail-safe
        m = SCOPE_RE.search(line)
        if m:
            active = m.group(1).lower()
            continue  # the marker line itself is not emitted
        if active in profile_scopes:
            kept.append(line)
    return "\n".join(kept).strip()


def build_fresh_state(source: Path, profile_scopes: set[str]) -> str:
    """Collect scope-admitted `[Updated YYYY-MM-DD: ...]` blocks, newest-first (drift-proof)."""
    rows: list[tuple[str, str, str]] = []  # (date, file, snippet)
    for path in sorted(source.glob("*.md")):
        admitted = segment_scopes(path.read_text(errors="ignore"), profile_scopes)
        for m in UPDATED_RE.finditer(admitted):
            start = m.start()
            snippet = admitted[start:start + 240].replace("\n", " ").strip()
            rows.append((m.group(1), path.stem, snippet))
    rows.sort(key=lambda r: r[0], reverse=True)
    if not rows:
        return "# FRESH STATE\n\n(no scope-admitted temporal markers for this profile)\n"
    out = ["# FRESH STATE — profile-scoped, newest-first", ""]
    for date, stem, snip in rows:
        out.append(f"## {date} · {stem}\n{snip}\n")
    return "\n".join(out)


def build_memory(memory_source: Path | None, profile: str) -> tuple[str, dict[str, str]]:
    """Filter memory/*.md by frontmatter `scope:` (unmarked → personal-only). Returns (MEMORY.md, files)."""
    if not memory_source or not memory_source.is_dir():
        return "", {}
    admitted = PROFILE_SCOPES[profile]
    kept: dict[str, str] = {}
    index_lines = ["# MEMORY (profile-scoped)", ""]
    for path in sorted(memory_source.glob("*.md")):
        if path.name == "MEMORY.md":
            continue
        body = path.read_text(errors="ignore")
        m = re.search(r"^\s*scope:\s*([a-z-]+)\s*$", body, re.MULTILINE)
        scope = (m.group(1).lower() if m else DEFAULT_SCOPE)
        if scope in admitted:
            kept[path.name] = body
            first = next((ln for ln in body.splitlines() if ln.strip() and not ln.startswith("-")), path.stem)
            index_lines.append(f"- [{path.stem}]({path.name}) — {first.strip()[:80]}")
    return "\n".join(index_lines) + "\n", kept


# CATEGORY DETECTORS — the denylist's structural blind spot.
#
# An enumerated denylist reports 0 hits for everything it was never told about, and
# "0 hits" reads as "verified safe" rather than "verified against 15 strings". v8
# shipped Ben's DOB, personal email, mobile, a full medication schedule and a genotype
# with a clean 0-hit sweep, because none of those words were on the list — and they
# never would have been. Prior sweeps only caught health terms because someone had
# happened to enumerate those specific drug names.
#
# These match on SHAPE, not on membership, so they catch the un-enumerated case.
# Note: the genotype pattern is deliberately case-SENSITIVE — [ACGT] under re.I
# matches ordinary lowercase words ("CSO at" → "at"), which is a false-positive mill.
CATEGORY_DETECTORS: list[tuple[str, "re.Pattern[str]"]] = [
    ("personal-email", re.compile(r"[\w.+-]+@(?:gmail|icloud|me|yahoo|outlook|hotmail|proton)\.\w+", re.I)),
    ("phone-number", re.compile(r"\(?\b\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b")),
    ("date-of-birth", re.compile(r"\bDOB\b|\bdate of birth\b|\bborn (?:in |on )?(?:19|20)\d\d", re.I)),
    # Deliberately GENERIC. An earlier version enumerated the principal's actual
    # prescriptions — which meant this very file, once published, contained the drug
    # names it exists to keep out, and the gate correctly blocked its own detector.
    # Specific names belong in the private manifest; the shipped detector matches on
    # pharmaceutical SHAPE (common stems/suffixes) plus dose adjacency, so it needs no
    # knowledge of any individual's regimen.
    ("medication", re.compile(
        # NOTE: `-opril`, not `-pril` — the looser form matches "April" and blocked a
        # bundle on an employment-history line. Drug-name stems must be long enough to
        # be pharmaceutical: every real ACE inhibitor is -opril (lisin-, enal-, rami-).
        r"\b\w{2,}(?:cillin|mycin|cycline|statin|prazole|sartan|olol|opril|azepam|"
        r"tidine|dronate|glutide|afinil|thyroxine)\b"
        r"|\b(?:hormone|testosterone|estrogen|insulin)\s+(?:injection|therapy|replacement)\w*"
        r"|\b(?:mg|mcg)\s+(?:daily|twice|nightly|fasted|AM|PM)\b", re.I)),
    ("dosage-schedule", re.compile(r"\b\d+\s?(?:mg|mcg|ml|iu)\b", re.I)),
    ("genotype", re.compile(r"\b[A-Z]{2,5}\d?\s+[ACGT]{2}\b|\bgenotype\b|\brs\d{4,}\b")),
    ("home-address", re.compile(r"\b\d{1,5}\s+\w+\s+(?:Drive|Dr|Street|St|Road|Rd|Lane|Ln|Ave|Avenue|Court|Ct)\b", re.I)),
]


def category_scan(out_dir: Path) -> list[str]:
    """Shape-based scan for PII/PHI the denylist can't enumerate. Returns 'file: category — line'."""
    hits: list[str] = []
    for path in sorted(out_dir.rglob("*")):
        if not path.is_file() or path.name == "banned_tokens.txt":
            continue
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        lines = text.splitlines()
        for label, rx in CATEGORY_DETECTORS:
            for m in rx.finditer(text):
                ln = text[: m.start()].count("\n")
                hits.append(f"{path.name}:{ln + 1}: {label} — {lines[ln].strip()[:70]}")
    return hits


def grep_gate(out_dir: Path, banned: list[str]) -> list[str]:
    """Scan every file in the built bundle for banned tokens. Returns list of 'file: token' hits."""
    hits: list[str] = []
    lowered = [(b, b.lower()) for b in banned if b.strip()]
    for path in out_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.name == "banned_tokens.txt":
            continue  # the scrub-list legitimately CONTAINS the tokens — never a leak
        text = path.read_text(errors="ignore").lower()
        for original, low in lowered:
            if low in text:
                hits.append(f"{path.relative_to(out_dir)}: {original!r}")
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a profile-scoped ~/.aos-private bundle.")
    ap.add_argument("--source", required=True, type=Path, help="PERSONAL corpus dir (source of truth)")
    ap.add_argument("--profile", required=True, choices=sorted(PROFILE_SCOPES), help="work | personal")
    ap.add_argument("--out", required=True, type=Path, help="bundle output dir (e.g. ~/.aos-private)")
    ap.add_argument("--memory-source", type=Path, default=None, help="optional memory/*.md dir")
    ap.add_argument("--dry-run", action="store_true", help="build to a temp dir + verify; do not write --out")
    args = ap.parse_args()

    source: Path = args.source.expanduser()
    if not source.is_dir():
        print(f"ERROR: --source not a dir: {source}", file=sys.stderr)  # c1-ok
        return 1
    manifest = load_manifest(source)
    banned: list[str] = manifest.get("banned_tokens", [])
    scopes = PROFILE_SCOPES[args.profile]

    out: Path = (args.out.expanduser() if not args.dry_run
                 else args.out.expanduser().parent / (".aos-private-build-" + args.profile))
    if out.exists():
        shutil.rmtree(out)
    (out / "identity").mkdir(parents=True, exist_ok=True)
    (out / "PERSONAL").mkdir(parents=True, exist_ok=True)

    # identity anchor — scope-filtered from the designated identity file
    anchor_src = source / manifest.get("anchor_file", "IDENTITY.md")
    anchor = segment_scopes(anchor_src.read_text(errors="ignore"), scopes) if anchor_src.is_file() else ""
    (out / "identity" / "anchor.md").write_text(anchor + "\n")

    (out / "PERSONAL" / "FRESH_STATE.md").write_text(build_fresh_state(source, scopes))

    # Per-file scope-filtered copies — the fuller work-safe corpus for on-demand reading. Only
    # files with at least one admitted segment are emitted; unmarked content never lands here.
    sharp_findings: list[str] = []
    for src in sorted(source.glob("*.md")):
        if src.name in ("FRESH_STATE.md",):
            continue
        raw = src.read_text(errors="ignore")
        admitted = segment_scopes(raw, scopes)
        if not admitted.strip():
            continue
        # Folio content carries third-party assessments. For the WORK profile it must
        # be normalized on the way out — otherwise every bundle bump silently
        # reintroduces colleagues' compensation onto an employer-owned machine, and it
        # only gets caught if a human happens to look. Doing it here (build time) rather
        # than by hand means it cannot regress.
        if args.profile == "work" and "folio-safe" in raw.lower():
            admitted, sharp = folio_normalize(admitted)
            sharp_findings += [f"{src.name} {s}" for s in sharp]
            # Provenance ("on the 3/14 call he said...") is sourcing, not conclusion.
            admitted, dropped = strip_provenance(admitted)
            if dropped:
                print(f"  folio: {src.name} — dropped {dropped} provenance line(s)", file=sys.stderr)  # c1-ok
        (out / "PERSONAL" / src.name).write_text(admitted + "\n")

    mem_index, mem_files = build_memory(args.memory_source, args.profile)
    if mem_index:
        (out / "MEMORY.md").write_text(mem_index)
        mdir = out / "memory"
        mdir.mkdir(exist_ok=True)
        for name, body in mem_files.items():
            (mdir / name).write_text(body)

    # carry banned_tokens.txt for the plugin's runtime scrub
    if banned:
        (out / "banned_tokens.txt").write_text("\n".join(banned) + "\n")

    # GREP GATE — only the work profile must be provably clean; personal admits everything.
    if args.profile == "work":
        hits = grep_gate(out, banned)
        if hits:
            shutil.rmtree(out)  # fail-closed: never leave a leaky bundle on disk
            print("GREP GATE FAILED — banned tokens found; bundle DELETED:", file=sys.stderr)  # c1-ok
            for h in hits[:20]:
                print(f"  {h}", file=sys.stderr)  # c1-ok
            return 2
        # CATEGORY GATE — fail-closed, same as the denylist. This is the layer that
        # would have stopped v8 shipping a DOB, a personal mobile, a medication
        # schedule and a genotype under a clean 0-hit denylist sweep.
        cat_hits = category_scan(out)
        if cat_hits:
            shutil.rmtree(out)
            print("CATEGORY GATE FAILED — PII/PHI shape detected; bundle DELETED:", file=sys.stderr)  # c1-ok
            for h in cat_hits[:20]:
                print(f"  {h}", file=sys.stderr)  # c1-ok
            print("  (mark these lines [SCOPE: personal-only] — they are shape-detected,", file=sys.stderr)  # c1-ok
            print("   so adding them to banned_tokens will NOT help.)", file=sys.stderr)  # c1-ok
            return 2
        # SHARP-LANGUAGE gate — the half of Ben's rule that CANNOT be automated.
        # A regex can strip a salary; it cannot reword "political-risk relationship"
        # into something that keeps the operating meaning. So this names the lines and
        # fails closed, rather than silently shipping a verdict on a colleague or
        # silently deleting the insight. Reword in PERSONAL/, then rebuild.
        if sharp_findings:
            shutil.rmtree(out)
            print("FOLIO GATE — sharp language needs rewording; bundle DELETED:", file=sys.stderr)  # c1-ok
            for s in sharp_findings[:20]:
                print(f"  {s}", file=sys.stderr)  # c1-ok
            print("  Rule: would Ben be comfortable if this were read aloud by the person", file=sys.stderr)  # c1-ok
            print("  it describes? If no, REWORD to keep the operating meaning — don't delete.", file=sys.stderr)  # c1-ok
            return 2

        # Report the COVERAGE, not just the count: "0 hits" reads as "verified safe"
        # when it only ever meant "verified against N strings". Naming both the token
        # count and the category count makes the boundary of the check visible.
        n_files = sum(1 for _ in out.rglob("*") if _.is_file())
        print(f"gate: 0 hits — {len(banned)} denylist tokens + "  # c1-ok
              f"{len(CATEGORY_DETECTORS)} PII/PHI category detectors "
              f"across {n_files} files ✓")

    files = sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file())
    print(f"built {args.profile} bundle → {out}  ({len(files)} files)")  # c1-ok
    for f in files:
        print(f"  {f}")  # c1-ok
    if args.dry_run:
        shutil.rmtree(out)
        print("(dry-run: build verified, temp bundle removed)")  # c1-ok
    return 0


if __name__ == "__main__":
    sys.exit(main())
