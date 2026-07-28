#!/usr/bin/env python3
"""aos-core: PreToolUse — surface the matching prior fix BEFORE you edit.

The consumer side of a compounding-knowledge loop: a `docs/solutions/` directory holds durable bug
fixes / patterns (YAML frontmatter: module, tags, problem_type); this hook reads them back into
context the moment you start editing a related file, so you don't rediscover a known fix.

Strategy: extract a path (Edit/Write/MultiEdit/NotebookEdit) or keywords (Bash) → frontmatter-aware
grep of the solutions dir → emit <=3 matches (<=300 chars each) as additionalContext → idempotent via
a 60-min TTL cache so the same match isn't re-surfaced every turn. Advisory only; never denies.

Content-free + decoupled: no AOS-internal imports (unlike the source hook). The solutions dir resolves
from AOS_CORE_SOLUTIONS_DIR, else <cwd>/docs/solutions — the working repo's knowledge base, never the
plugin (which ships empty). Bring the mechanism; let each repo accumulate its own solutions.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

CACHE_DIR = Path.home() / ".claude" / "cache"
CACHE_FILE = CACHE_DIR / "aos-core-solution-surfaces.jsonl"
TTL_SECONDS = 3600
MAX_MATCHES = 3
MAX_SNIPPET_CHARS = 300

# Terms that appear in EVERY absolute path, or in nearly every entry, and therefore
# carry no signal. Without this, a path like /Users/<name>/aos/docs/solutions/x.md
# contributes `users`, `<name>`, `docs` and `solutions` as needles — which match most
# of the corpus and drown the one entry that is actually about the file being edited.
# Precision matters more than recall here: a hook that mostly injects noise trains the
# reader to skip it, and a skipped hook protects nothing.
STOP_TERMS = {
    "users", "home", "aos", "spos", "docs", "solutions", "data", "tools", "src",
    "main", "test", "tests", "temp", "tmp", "file", "files", "index", "readme",
    "json", "yaml", "yml", "python", "script", "scripts", "utils", "lib", "common",
    "claude", "project", "projects", "work", "notes", "draft", "final", "copy",
}
# Every component of the home path is in EVERY absolute path on this machine — the
# username above all. Derived rather than hardcoded: it must not carry a personal
# identifier in a content-free plugin, and it has to work on any machine/user.
STOP_TERMS |= {p.lower() for p in Path.home().parts if len(p) >= 4 and p != "/"}


def solutions_dir() -> Path:
    env = os.environ.get("AOS_CORE_SOLUTIONS_DIR")
    if env:
        return Path(env).expanduser()
    # CLAUDE_PROJECT_DIR is the real project root even in worktrees/subdirs; cwd drifts.
    root = os.environ.get("CLAUDE_PROJECT_DIR") or str(Path.cwd())
    return Path(root) / "docs" / "solutions"


def _extract_signal(tool_name: str, tool_input: dict) -> tuple[str | None, list[str]]:
    keywords: list[str] = []
    path = None
    if tool_name in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        path = tool_input.get("file_path") or tool_input.get("notebook_path")
        if path:
            parts = re.split(r"[/_\-.]", str(path))
            keywords = [p for p in parts if len(p) >= 4 and not p.isdigit()]
    elif tool_name == "Bash":
        cmd = tool_input.get("command", "")
        for m in re.findall(r"[A-Za-z0-9_./-]{4,}", cmd):
            if "/" in m or m.endswith((".py", ".sh", ".md", ".json")):
                keywords.append(m)
                if path is None and "/" in m:
                    path = m
        verb = cmd.strip().split()[0] if cmd.strip() else ""
        if verb and len(verb) >= 3:
            keywords.append(verb)
    return path, keywords[:12]


def _grep(path: str | None, keywords: list[str]) -> list[dict]:
    sdir = solutions_dir()
    if not sdir.is_dir():
        return []
    needles: set[str] = set()
    stem = ""
    if path:
        stem = os.path.basename(path).lower().rsplit(".", 1)[0]
        if stem and stem not in STOP_TERMS:
            needles.add(stem)
        for p in [p for p in path.replace("\\", "/").split("/") if p][-3:]:
            if len(p) >= 4 and p.lower() not in STOP_TERMS:
                needles.add(p.lower())
    for k in keywords:
        if len(k) >= 4 and k.lower() not in STOP_TERMS:
            needles.add(k.lower())
    if not needles:
        return []

    results: list[dict] = []
    for md in sdir.rglob("*.md"):
        try:
            text = md.read_text(errors="ignore")
        except OSError:
            continue
        lower = text.lower()
        head = lower[:2000]  # frontmatter slice — weighted heavier
        md_stem = md.stem.lower()
        score = 0
        hit_terms: list[str] = []
        for n in needles:
            # A needle appearing in the ENTRY'S OWN FILENAME is the strongest signal
            # there is — it means the entry is literally about this thing. Weighted
            # above frontmatter, which is weighted above body.
            if n in md_stem:
                score += 6
                hit_terms.append(n)
            elif n in head:
                score += 3
                hit_terms.append(n)
            elif n in lower:
                score += 1
                hit_terms.append(n)
        # PRECISION FLOOR: a single weak body hit is noise, and noise trains people to
        # ignore the hook — at which point it protects nothing. Require either two
        # DISTINCT matching terms, or one strong hit (filename/frontmatter). Measured
        # failure this replaced: editing `tom-ednie-meeting-prep.md` returned a corpus
        # bootstrap handoff as top match on `benmjohnson, meeting, prep, users`, burying
        # an entry literally named `...tom-ednie-meeting-followups.md`.
        if score <= 0 or (len(set(hit_terms)) < 2 and score < 3):
            continue
        snippet = ""
        for n in hit_terms:
            idx = lower.find(n)
            if idx >= 0:
                snippet = re.sub(r"\s+", " ", text[max(0, idx - 80):idx - 80 + MAX_SNIPPET_CHARS]).strip()
                break
        if not snippet:
            snippet = re.sub(r"\s+", " ", text[:MAX_SNIPPET_CHARS]).strip()
        try:
            rel = str(md.relative_to(sdir.parent))
        except ValueError:
            rel = md.name
        results.append({
            "file": rel,
            "score": score,
            "snippet": snippet[:MAX_SNIPPET_CHARS],
            "matched_terms": sorted(set(hit_terms))[:5],
        })
    results.sort(key=lambda r: -r["score"])
    return results[:MAX_MATCHES]


def _surface_key(matches: list[dict]) -> str:
    sig = "|".join(sorted(m.get("file", "") for m in matches))
    return hashlib.sha256(sig.encode()).hexdigest()[:16]


def _recently_surfaced(key: str) -> bool:
    if not CACHE_FILE.exists():
        return False
    cutoff = time.time() - TTL_SECONDS
    try:
        for line in CACHE_FILE.read_text().splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("key") == key and float(row.get("ts", 0)) >= cutoff:
                return True
    except OSError:
        return False
    return False


def _record_surface(key: str, matches: list[dict]) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cutoff = time.time() - TTL_SECONDS
        keep: list[str] = []
        if CACHE_FILE.exists():
            for line in CACHE_FILE.read_text().splitlines():
                try:
                    if float(json.loads(line).get("ts", 0)) >= cutoff:
                        keep.append(line)
                except ValueError:
                    continue
        keep.append(json.dumps({"key": key, "ts": time.time(), "files": [m.get("file") for m in matches]}))
        CACHE_FILE.write_text("\n".join(keep) + "\n")
    except OSError:
        pass


def _format_context(matches: list[dict], path: str | None) -> str:
    lines = [f"Prior fixes matched ({len(matches)}) for {path or 'this action'}:"]
    for i, m in enumerate(matches, 1):
        terms = ",".join(m.get("matched_terms", []))
        lines.append(f"  [{i}] {m['file']} (terms: {terms})\n      {m['snippet'][:MAX_SNIPPET_CHARS]}")
    lines.append("Check before reimplementing. Override: include 'solution-surface-skip' in the command.")
    return "\n".join(lines)


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (OSError, ValueError):
        return 0
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    if tool_name not in ("Write", "Edit", "MultiEdit", "NotebookEdit", "Bash"):
        return 0
    if "solution-surface-skip" in " ".join(str(v) for v in tool_input.values()).lower():
        return 0

    path, keywords = _extract_signal(tool_name, tool_input)
    if not path and not keywords:
        return 0
    matches = _grep(path, keywords)
    if not matches:
        return 0
    key = _surface_key(matches)
    if _recently_surfaced(key):
        return 0
    _record_surface(key, matches)

    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                  "additionalContext": _format_context(matches, path)}}
    print(json.dumps(out))  # c1-ok
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
