#!/usr/bin/env python3
"""aos-core: PostCompact — re-inject the pre-compaction snapshot so the session picks up mid-work.

Reads the JSON snapshot written by precompact-flush IF it is fresh (within a window), prints it as
additionalContext, and consumes the marker so it is not re-injected. Optionally prepends a "floor"
doc from the private layer (~/.aos-private/floor.md) — the standards/context you want restated after a
wipe. Content-free: the floor doc, if any, lives outside the plugin. Never blocks (always exit 0).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from private_layer import read_private  # noqa: E402

WINDOW_SEC = 600  # 10-minute freshness gate


def state_dir() -> Path:
    return Path(os.environ.get("AOS_CORE_STATE_DIR", str(Path.home() / ".claude" / "aos-core-state")))


def _fresh(iso: str) -> bool:
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds()
        return 0 <= age <= WINDOW_SEC
    except (ValueError, TypeError):
        return False


def build_context() -> str:
    d = state_dir()
    marker = d / "marker.json"
    if not marker.is_file():
        return ""
    try:
        mk = json.loads(marker.read_text())
    except (OSError, ValueError):
        return ""
    if not _fresh(mk.get("written_at", "")):
        return ""
    snap_path = d / f"{mk.get('session_id', 'unknown')}.json"
    snap = snap_path.read_text() if snap_path.is_file() else "{}"
    parts = ["# aos-core: recovered from compaction — resume mid-work, do not restart"]
    floor = read_private("floor.md", default="")
    if floor.strip():
        parts.append(floor.strip())
    parts.append("## Pre-compaction state (lossless JSON)\n```json\n" + snap + "\n```")
    try:
        marker.unlink()  # consume so it does not re-inject
    except OSError:
        pass
    return "\n\n".join(parts)


def main() -> int:
    try:
        ctx = build_context()
        if ctx:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostCompact",
                                                     "additionalContext": ctx}}))  # c1-ok
    except Exception:  # noqa: BLE001 — restore must never break the session
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
