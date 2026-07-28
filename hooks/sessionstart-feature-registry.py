#!/usr/bin/env python3
"""aos-core: SessionStart — inject the repo feature-registry summary so you search before you build.

Reads the summary written by build_feature_registry.py and surfaces it (bounded) at session start, so
"what do I already have?" is answered before you write anything new. Silent if no summary exists —
the mechanism ports empty; each repo generates its own registry.

Self-healing (staleness): nothing else re-runs build_feature_registry.py, so the registry went stale
twice in one day on the work Mac (nothing regenerates it after tools/skills/hooks change). Fix: compare
the registry's mtime against the newest mtime among the surfaces it scans (tools/*.py, skills/*/SKILL.md,
.claude/skills/*/SKILL.md, .claude/hooks/*.py). If stale or missing, regenerate INLINE — measured <1s
even on the full aos monorepo (1143 entries across tools/skills/hooks), well under a 2s SessionStart
budget, so an inline rebuild is the smallest honest fix rather than deferring to a comply-offer line.
If the builder can't be found or regen fails for any reason, fall back to a single advisory line naming
the exact regen command — never a hard failure, never a decision this hook makes on your behalf.

Content-free: the summary describes the repo's own tools/skills, not personal data. Resolves from
AOS_CORE_REGISTRY_SUMMARY, else <cwd>/data/feature_registry_summary.md. Never blocks.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

MAX_CHARS = 4000
REGEN_BUDGET_S = 2.0
BUILDER_TOOL = Path(__file__).resolve().parent.parent / "tools" / "build_feature_registry.py"


def summary_path() -> Path:
    env = os.environ.get("AOS_CORE_REGISTRY_SUMMARY")
    if env:
        return Path(env).expanduser()
    root = os.environ.get("CLAUDE_PROJECT_DIR") or str(Path.cwd())  # real root even in worktrees
    return Path(root) / "data" / "feature_registry_summary.md"


def repo_root() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())


def newest_surface_mtime(repo: Path) -> float:
    """Newest mtime among everything build_feature_registry.py would index. 0.0 if nothing found."""
    newest = 0.0
    globs = [
        (repo / "tools", "*.py"),
        (repo / "skills", "*/SKILL.md"),
        (repo / ".claude" / "skills", "*/SKILL.md"),
        (repo / ".claude" / "hooks", "*.py"),
    ]
    for base, pattern in globs:
        if not base.is_dir():
            continue
        for p in base.glob(pattern):
            try:
                m = p.stat().st_mtime
            except OSError:
                continue
            newest = max(newest, m)
    return newest


def _load_builder():
    if not BUILDER_TOOL.is_file():
        return None
    try:
        spec = importlib.util.spec_from_file_location("_bfr", BUILDER_TOOL)
        if not spec or not spec.loader:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except (OSError, SyntaxError, ImportError):
        return None


def regenerate(repo: Path, out_md: Path) -> bool:
    """Best-effort inline regen via the same collect()/render_summary() build_feature_registry.py
    uses on the CLI — no subprocess, so the ~1s cost measured offline is what actually pays here.
    Never raises: any failure just means the caller falls back to the advisory line."""
    mod = _load_builder()
    if mod is None:
        return False
    try:
        reg = mod.collect(repo)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(mod.render_summary(reg, 60))
        (out_md.parent / "feature_registry.json").write_text(json.dumps(reg, indent=2))
        return True
    except OSError:
        return False


def main() -> int:
    try:
        sys.stdin.read()  # drain
        p = summary_path()
        repo = repo_root()
        newest = newest_surface_mtime(repo)
        stale = (not p.is_file()) or (newest > 0 and p.stat().st_mtime < newest)
        if stale and not regenerate(repo, p):
            cmd = f"python3 {BUILDER_TOOL} --repo {repo}"
            print(f"[feature registry stale — regenerate: {cmd}]")  # c1-ok — advisory only
            if not p.is_file():
                return 0
        if not p.is_file():
            return 0
        text = p.read_text(errors="ignore").strip()
        if not text:
            return 0
        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS] + "\n…(truncated — see feature_registry.json for the full list)"
        print(text)  # c1-ok — SessionStart stdout is wrapped as additionalContext
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
