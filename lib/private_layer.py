#!/usr/bin/env python3
"""aos-core private-layer loader — the safety-by-construction boundary.

AOS Core ships CONTENT-FREE: no identity text, no personal facts, no memory. All of that lives in a
separate directory (default ~/.aos-private/) that the user owns and never commits to the plugin.
Every hook that needs personal content calls into this module, which loads it ONLY IF PRESENT and
degrades to a clean, work-appropriate default when absent.

Consequence: the plugin artifact cannot leak confidential data because it does not contain any. On a
corporate work Mac with no ~/.aos-private/, Core runs a clean generic persona. On a personal Mac with
~/.aos-private/ present, the same plugin lights up the full identity. Same artifact, two faces.

Override the location with AOS_PRIVATE_DIR.
"""
from __future__ import annotations

import os
from pathlib import Path


def private_dir() -> Path:
    return Path(os.environ.get("AOS_PRIVATE_DIR", str(Path.home() / ".aos-private")))


def has_private() -> bool:
    return private_dir().is_dir()


def read_private(relpath: str, default: str = "", max_chars: int | None = None) -> str:
    """Read a file under the private layer if present; else return `default`.

    relpath is relative to the private dir (e.g. 'identity/anchor.md'). Never raises — a missing or
    unreadable private layer must degrade to the clean default, not break the session.
    """
    try:
        p = private_dir() / relpath
        if not p.is_file():
            return default
        text = p.read_text(encoding="utf-8")
        return text[:max_chars] if max_chars else text
    except OSError:
        return default


def read_private_lines(relpath: str) -> list[str]:
    """Read a newline-delimited private file (e.g. banned_tokens.txt) → stripped non-empty lines."""
    raw = read_private(relpath, default="")
    return [ln.strip() for ln in raw.splitlines() if ln.strip()]
