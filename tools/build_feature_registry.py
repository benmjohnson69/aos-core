#!/usr/bin/env python3
"""aos-core: build a search-before-you-build feature registry for a repo.

Indexes a repo's own capabilities (tools + skills) so you can search before writing anything new —
the antibody against rebuilding what already exists. Walks <repo>/tools/*.py and <repo>/skills/*/SKILL.md
(and optionally .claude/hooks/*.py), extracts each one's name + first description line, and writes a
compact summary (Markdown, for SessionStart injection) + a JSON index (for search).

Content-free + generic: no AOS-specific paths or entries baked in — it indexes whatever repo you point
it at. Re-run on commit (or by hand) to keep it fresh.

Usage: build_feature_registry.py [--repo .] [--out data/feature_registry_summary.md] [--max 60]
"""
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

DESC_RE = re.compile(r"^description:\s*[\"']?(.+?)[\"']?\s*$", re.IGNORECASE)


def py_desc(path: Path) -> str:
    """First line of the module docstring, else empty."""
    try:
        mod = ast.parse(path.read_text(errors="ignore"))
        doc = ast.get_docstring(mod) or ""
        return doc.strip().splitlines()[0][:120] if doc.strip() else ""
    except (OSError, SyntaxError, ValueError):
        return ""


def skill_desc(path: Path) -> str:
    """`description:` from SKILL.md frontmatter, else the first heading."""
    try:
        for line in path.read_text(errors="ignore").splitlines()[:20]:
            m = DESC_RE.match(line.strip())
            if m:
                return m.group(1)[:160]
    except OSError:
        pass
    return ""


def collect(repo: Path) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {"tools": [], "skills": [], "hooks": []}
    tdir = repo / "tools"
    if tdir.is_dir():
        for p in sorted(tdir.glob("*.py")):
            if p.name.startswith("_"):
                continue
            out["tools"].append({"name": p.stem, "path": str(p.relative_to(repo)), "desc": py_desc(p)})
    for sdir in (repo / "skills", repo / ".claude" / "skills"):
        if sdir.is_dir():
            for sk in sorted(sdir.glob("*/SKILL.md")):
                out["skills"].append({"name": sk.parent.name, "path": str(sk.relative_to(repo)),
                                      "desc": skill_desc(sk)})
    hdir = repo / ".claude" / "hooks"
    if hdir.is_dir():
        for p in sorted(hdir.glob("*.py")):
            out["hooks"].append({"name": p.stem, "path": str(p.relative_to(repo)), "desc": py_desc(p)})
    return out


def render_summary(reg: dict[str, list[dict]], maximum: int) -> str:
    total = sum(len(v) for v in reg.values())
    lines = [f"# Feature Registry — {total} capabilities across {len(reg)} kinds", "",
             "**Before building any new tool/skill: search here. If it exists, use it.**", ""]
    for kind, items in reg.items():
        if not items:
            continue
        lines.append(f"## {kind.capitalize()} ({len(items)})")
        for it in items[:maximum]:
            d = f" — {it['desc']}" if it["desc"] else ""
            lines.append(f"- **{it['name']}** (`{it['path']}`){d}")
        if len(items) > maximum:
            lines.append(f"- …and {len(items) - maximum} more (see feature_registry.json)")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a repo feature registry.")
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--out", type=Path, default=None, help="summary .md path (default <repo>/data/feature_registry_summary.md)")
    ap.add_argument("--max", type=int, default=60, help="max items listed per kind in the summary")
    args = ap.parse_args()

    repo = args.repo.expanduser().resolve()
    reg = collect(repo)
    out_md = (args.out or (repo / "data" / "feature_registry_summary.md")).expanduser()
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_summary(reg, args.max))
    (out_md.parent / "feature_registry.json").write_text(json.dumps(reg, indent=2))
    total = sum(len(v) for v in reg.values())
    print(f"indexed {total} capabilities → {out_md}")  # c1-ok
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
