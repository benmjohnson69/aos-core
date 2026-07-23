#!/usr/bin/env python3
"""aos-core: PreToolUse — inject E2 discipline into every dispatched sub-agent.

When you spawn a sub-agent (Agent/Task), the coding-hygiene standard should survive delegation. This
hook inspects the agent prompt; if it doesn't already require ruff + mypy + py_compile, it injects an
advisory reminding the dispatcher to run E2 on the agent's output. Advisory only — never blocks a spawn.

Content-free + decoupled: no aos_logging import (unlike the source hook). An optional dispatch log goes
to AOS_CORE_STATE_DIR (never into the plugin artifact); disabled if the dir can't be written.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def _log_dispatch(description: str, prompt: str, has_e2: bool) -> None:
    base = os.environ.get("AOS_CORE_STATE_DIR")
    if not base:
        return
    try:
        p = Path(base)
        p.mkdir(parents=True, exist_ok=True)
        with (p / "agent-dispatches.jsonl").open("a") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(),
                "description": description[:200],
                "prompt_length": len(prompt),
                "has_e2": has_e2,
            }) + "\n")
    except OSError:
        pass


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (OSError, ValueError):
        return 0
    if payload.get("tool_name", "") not in ("Agent", "Task"):
        return 0

    tool_input = payload.get("tool_input", {}) or {}
    prompt = str(tool_input.get("prompt", ""))
    pl = prompt.lower()
    missing = [t for t in ("ruff", "mypy", "py_compile") if t not in pl]
    _log_dispatch(str(tool_input.get("description", "")), prompt, not missing)
    if not missing:
        return 0

    ctx = (f"⚠️ aos-core E2: the sub-agent prompt is missing E2 checks ({', '.join(missing)}). "
           "After the agent completes, YOU must run full E2 (ruff + mypy + py_compile) on every "
           "changed .py file before marking the work done — rigor must survive delegation.")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": ctx}}))  # c1-ok
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
