#!/usr/bin/env python3
"""aos-core: Stop — advise (never block) when a session ends with no fresh handoff.

Continuity backstop for the session-close skill. On Stop, if no handoff in docs/session-handoffs/ has
been touched within a freshness window, emit a reminder to run session-close. ADVISORY ONLY — it does
not block the stop (a hard gate here would trap the user); the skill is the real work, this is the nudge.

Content-free. Resolves handoff dir from AOS_CORE_HANDOFFS_DIR else <cwd>/docs/session-handoffs.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

FRESH_SECONDS = 2 * 60 * 60  # a handoff within 2h counts as "this session"


def handoffs_dir() -> Path:
    env = os.environ.get("AOS_CORE_HANDOFFS_DIR")
    if env:
        return Path(env).expanduser()
    root = os.environ.get("CLAUDE_PROJECT_DIR") or str(Path.cwd())  # real root even in worktrees
    return Path(root) / "docs" / "session-handoffs"


def _has_fresh_handoff(d: Path) -> bool:
    if not d.is_dir():
        return False
    cutoff = time.time() - FRESH_SECONDS
    for p in d.glob("*.md"):
        try:
            if p.stat().st_mtime >= cutoff:
                return True
        except OSError:
            continue
    return False


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (OSError, ValueError):
        return 0
    # Avoid nagging in an infinite loop if a stop-hook already fired.
    if payload.get("stop_hook_active"):
        return 0
    try:
        d = handoffs_dir()
        # No handoffs dir = this repo doesn't use the convention. Absence of the
        # convention is not a stale handoff — nagging here fires in every unrelated
        # project. Only advise where the convention actually exists.
        if not d.is_dir():
            return 0
        if _has_fresh_handoff(d):
            return 0
        msg = ("aos-core: no fresh session handoff found. Before stopping, consider running the "
               "session-close skill to write a resumable handoff to docs/session-handoffs/ so the "
               "next session picks up without reconstruction. (Advisory — not blocking.)")
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": msg}}))  # c1-ok
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
