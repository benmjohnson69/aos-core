---
name: session-close
description: Use at the end of a work session (or on "save session", "wrapping up", "done for now") to write a resumable handoff so the next session picks up without reconstruction.
---

# session-close — persist continuity before context evaporates

## Root principle
> A session that closes without a resumable handoff has failed its continuity contract — the next
> session pays the reconstruction tax. The handoff is a **resumption artifact**, not a retrospective.

## When to run
- The user says "save session", "wrapping up", "done for now", "close out", "end session".
- The user signals completion ("that's all for today").
- You are about to stop after a substantive unit of work.

## What to write
Write one Markdown file to `docs/session-handoffs/<YYYY-MM-DD>-<short-slug>.md` with a **RESUME
PROTOCOL** header, so the next session can act from facts, not memory:

```markdown
# Handoff — <slug> — <YYYY-MM-DD>

## RESUME PROTOCOL
1. Read this file first.
2. <the single most important thing to do next>
3. <second, third next steps>

## State
- Branch: <git branch>
- Modified/committed: <key files or commit shas>
- Mode: BUILDER | ANALYST | ...

## What happened
- <decisions made, with the *why*>
- <what was verified, and how>

## Open loops / blockers
- <anything unfinished, with enough context to resume cold>

## Do NOT
- <traps to avoid — things already tried that didn't work>
```

## Quality bar
- **Resumable cold.** Ask yourself: "could a fresh session continue from this file alone?" If no, add detail.
- **Decisions carry their why.** "Chose X over Y because Z" — not just "chose X".
- **Name the next action first.** The RESUME PROTOCOL's step 2 is the single highest-value next move.
- **Link the artifacts.** Reference commit shas / file paths so nothing has to be re-found.

## Note
The companion `stop-session-close.py` hook advises (never blocks) when a session ends with no fresh
handoff in `docs/session-handoffs/`. It is a reminder, not a gate — this skill is the real work.
