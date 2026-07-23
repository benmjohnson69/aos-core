#!/usr/bin/env python3
"""aos-core: UserPromptSubmit backstop for compaction recovery.

The suspender to PostCompact's belt (AOS shipped this hook but left it UNWIRED — the mistake this
plugin fixes by wiring it). If PostCompact fired, it consumed the marker and this is a no-op. If
PostCompact silently failed, the marker survives — on the next prompt this re-injects the snapshot so
context still isn't lost. Freshness-gated (5 min) + consumes the marker. Content-free. Never blocks.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

WINDOW_SEC = 300


def state_dir() -> Path:
    return Path(os.environ.get("AOS_CORE_STATE_DIR", str(Path.home() / ".claude" / "aos-core-state")))


def _fresh(iso: str) -> bool:
    try:
        return 0 <= (datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds() <= WINDOW_SEC
    except (ValueError, TypeError):
        return False


def main() -> int:
    try:
        sys.stdin.read()  # drain payload (unused)
        d = state_dir()
        marker = d / "marker.json"
        if not marker.is_file():
            return 0
        try:
            mk = json.loads(marker.read_text())
        except (OSError, ValueError):
            return 0
        if not _fresh(mk.get("written_at", "")):
            return 0
        snap_path = d / f"{mk.get('session_id', 'unknown')}.json"
        snap = snap_path.read_text() if snap_path.is_file() else "{}"
        ctx = ("# aos-core: compaction recovery (backstop — PostCompact did not fire)\n"
               "Resume mid-work; do not restart.\n## Pre-compaction state (lossless JSON)\n```json\n"
               + snap + "\n```")
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                                 "additionalContext": ctx}}))  # c1-ok
        try:
            marker.unlink()
        except OSError:
            pass
    except Exception:  # noqa: BLE001 — a backstop must never break prompt submission
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
