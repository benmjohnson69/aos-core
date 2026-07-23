#!/usr/bin/env python3
"""aos-core: PreCompact — snapshot lossless session state before compaction.

Claude Code silently compacts its own context mid-work, discarding which branch/files/decisions you
were on. This hook writes a structured JSON snapshot + a marker just before that happens, so the
PostCompact hook can re-inject it. Content-free: it captures git + the tail of THIS session's
transcript; it holds no personal data of its own. State goes to a per-user dir OUTSIDE the plugin
(AOS_CORE_STATE_DIR, default ~/.claude/aos-core-state), never into the installed artifact.

Lesson baked in (from AOS): the snapshot must be lossless JSON, not prose — prose rendering drops fields.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def state_dir() -> Path:
    d = Path(os.environ.get("AOS_CORE_STATE_DIR", str(Path.home() / ".claude" / "aos-core-state")))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _last_exchanges(transcript_path: str, n: int = 10) -> list[dict]:
    """Extract the last n role+text snippets from the session transcript (jsonl). Bounded + tolerant."""
    out: list[dict] = []
    try:
        p = Path(transcript_path)
        if not p.is_file():
            return out
        lines = p.read_text(errors="ignore").splitlines()[-120:]
        for ln in lines:
            try:
                o = json.loads(ln)
            except ValueError:
                continue
            msg = o.get("message", o)
            role = msg.get("role")
            if role not in ("user", "assistant"):
                continue
            c = msg.get("content")
            if isinstance(c, list):
                txt = " ".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
            else:
                txt = c if isinstance(c, str) else ""
            if txt.strip():
                out.append({"role": role, "text": txt.strip()[:500]})
    except OSError:
        return out
    return out[-n:]


def main() -> int:
    try:
        try:
            payload = json.loads(sys.stdin.read() or "{}")
        except ValueError:
            payload = {}
        sid = payload.get("session_id") or "unknown"
        snap = {
            "schema": 1,
            "session_id": sid,
            "written_at": datetime.now(timezone.utc).isoformat(),
            "cwd": payload.get("cwd") or os.getcwd(),
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "modified_files": [ln[3:] for ln in _git("status", "--porcelain").splitlines()][:40],
            "recent_exchanges": _last_exchanges(payload.get("transcript_path", "")),
        }
        d = state_dir()
        (d / f"{sid}.json").write_text(json.dumps(snap, indent=2))
        (d / "marker.json").write_text(json.dumps({"session_id": sid, "written_at": snap["written_at"]}))
    except Exception:  # noqa: BLE001 — a flush must never break compaction
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
