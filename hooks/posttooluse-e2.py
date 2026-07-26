#!/usr/bin/env python3
"""aos-core: PostToolUse E2 enforcer — write-time coding hygiene, content-free.

After any Write/Edit/MultiEdit to a .py file, run ruff + mypy + py_compile and surface failures the
same turn (alert-only — signals, never blocks). Catches lint/type/compile errors when the context that
caused them is still live, instead of at commit. Uses whatever `ruff`/`mypy`/`python` are on PATH (or a
venv via AOS_CORE_PY); skips vendored/ephemeral dirs. Zero personal data, zero AOS coupling.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PY = os.environ.get("AOS_CORE_PY", sys.executable or "python3")
SKIP = ("/.venv/", "/node_modules/", "/dist/", "/__pycache__/", "/tmp/", "/site-packages/")
TIMEOUT = 8

# bootstrap.sh installs ruff/mypy into an isolated venv that is NOT on PATH. A bare
# `ruff`/`mypy` lookup would then fail and _run() would treat the tool as absent —
# so E2 silently no-ops. Resolve from that venv as a fallback so "installed" always
# means "findable", regardless of PATH. Override the dir with AOS_CORE_E2_BIN.
E2_VENV_BIN = Path(os.environ.get("AOS_CORE_E2_BIN", str(Path.home() / ".venvs" / "e2" / "bin")))


def _resolve(tool: str) -> str | None:
    """tool path from PATH, else the E2 venv; None only when genuinely absent everywhere."""
    on_path = shutil.which(tool)
    if on_path:
        return on_path
    cand = E2_VENV_BIN / tool
    if cand.is_file() and os.access(cand, os.X_OK):
        return str(cand)
    return None


def _read_payload() -> dict:
    try:
        return json.loads(sys.stdin.read() or "{}")
    except (ValueError, OSError):
        return {}


def _target(payload: dict) -> str | None:
    ti = payload.get("tool_input") or payload.get("input") or {}
    if not isinstance(ti, dict):
        return None
    fp = ti.get("file_path") or ti.get("path") or ""
    if not fp.endswith(".py"):
        return None
    if any(s in fp for s in SKIP):
        return None
    return fp if Path(fp).is_file() else None


def _run(cmd: list[str]) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
        return r.returncode == 0, (r.stdout + r.stderr)[-400:]
    except (OSError, subprocess.SubprocessError) as exc:
        return True, f"(skipped: {type(exc).__name__})"  # tool absent → don't nag


def main() -> int:
    try:
        fp = _target(_read_payload())
        if not fp:
            return 0
        ruff, mypy = _resolve("ruff"), _resolve("mypy")
        checks: list[tuple[str, list[str]]] = []
        if ruff:
            checks.append(("ruff", [ruff, "check", fp]))
        if mypy:
            checks.append(("mypy", [mypy, "--ignore-missing-imports", fp]))
        checks.append(("py_compile", [PY, "-m", "py_compile", fp]))  # PY always available
        fails = []
        for name, cmd in checks:
            ok, tail = _run(cmd)
            if not ok:
                fails.append(f"{name}: {tail.strip()[:200]}")
        if fails:
            msg = f"⚠️ E2 on {Path(fp).name}: " + " | ".join(fails)
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                                      "additionalContext": msg}}))  # c1-ok
    except Exception:  # noqa: BLE001 — never break a tool call
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
