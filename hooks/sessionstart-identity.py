#!/usr/bin/env python3
"""aos-core: SessionStart identity anchor — content-free.

Emits a compact (<2KB) identity anchor at turn-0 so a fresh session isn't a stranger. The IDENTITY
TEXT is NOT in this file — it is loaded from the private layer (~/.aos-private/identity/anchor.md) if
present, else a clean generic work persona. A banned-token scrub (list from the private layer, empty by
default) strips known hallucination tokens. FRESH_STATE head is loaded from the private layer if present.

Keep it small: an oversized anchor gets silently truncated at turn-0 (the original AOS anchor learned
this the hard way — a 16KB version delivered only ~30%). Cap ~1.8KB.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from private_layer import read_private, read_private_lines  # noqa: E402

MAX_CHARS = 1800

# Clean default persona used when NO private layer is present (e.g. a fresh corporate work Mac).
DEFAULT_ANCHOR = """# Working anchor (aos-core, no private layer)
Senior-engineer register: synthesis first, direct, numeric confidence when uncertain, action over
instruction, honest about gaps ("unable to verify" + next step). Verify output before presenting
(hostile-reviewer pass). Declare mode (ANALYST | BUILDER | EVALUATOR | SYSTEMS_THINKING) before work.
No personal context is loaded — drop an ~/.aos-private/ layer to enable a full identity."""


def _scrub(text: str, banned: list[str]) -> str:
    if not banned:
        return text
    keep = [ln for ln in text.splitlines() if not any(b.lower() in ln.lower() for b in banned)]
    return "\n".join(keep)


def build_anchor() -> str:
    anchor = read_private("identity/anchor.md", default=DEFAULT_ANCHOR)
    banned = read_private_lines("banned_tokens.txt")
    fresh = read_private("PERSONAL/FRESH_STATE.md", default="", max_chars=400)
    parts = [_scrub(anchor, banned).strip()]
    if fresh.strip():
        parts.append("## FRESH STATE\n" + _scrub(fresh, banned).strip())
    out = "\n\n".join(parts)
    return out[:MAX_CHARS]


def main() -> int:
    try:
        line = build_anchor()
        if line:
            print(line)  # injected as SessionStart additionalContext  # c1-ok: hook stdout contract
    except Exception:  # noqa: BLE001 — an identity surfacer must never break session start
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
