#!/usr/bin/env python3
"""aos-core: SessionStart — inject the repo feature-registry summary so you search before you build.

Reads the summary written by build_feature_registry.py and surfaces it (bounded) at session start, so
"what do I already have?" is answered before you write anything new. Silent if no summary exists —
the mechanism ports empty; each repo generates its own registry.

Content-free: the summary describes the repo's own tools/skills, not personal data. Resolves from
AOS_CORE_REGISTRY_SUMMARY, else <cwd>/data/feature_registry_summary.md. Never blocks.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

MAX_CHARS = 4000


def summary_path() -> Path:
    env = os.environ.get("AOS_CORE_REGISTRY_SUMMARY")
    if env:
        return Path(env).expanduser()
    root = os.environ.get("CLAUDE_PROJECT_DIR") or str(Path.cwd())  # real root even in worktrees
    return Path(root) / "data" / "feature_registry_summary.md"


def main() -> int:
    try:
        sys.stdin.read()  # drain
        p = summary_path()
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
