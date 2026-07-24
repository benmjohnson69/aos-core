---
name: compound
description: Use when a bug is fixed, a gotcha survived, or a pattern proven — or when the user says "compound this", "write the lesson", "capture this fix". Writes a durable docs/solutions/ entry so the prior-fix surfacing hook can push it back into context the next time the same class of problem appears. The producer half of the compound-learning loop.
---

# compound — turn a solved problem into a self-surfacing lesson

## Root principle
> A fix that lives only in chat history is a fix you will pay for again. Every solved problem worth
> more than 10 minutes becomes a `docs/solutions/` entry — because the prior-fix hook greps that
> directory *before every edit* and pushes the matching lesson back into context at decision time.
> Writing the entry is what closes the loop; the hook only consumes what exists.

## When to run
- A non-obvious bug got fixed (root cause found, not just symptom patched).
- A tool/library gotcha cost real time and has a durable workaround.
- A pattern was proven that future work should reuse (or an anti-pattern to avoid).
- The user says "compound this" / "write the lesson" / "capture this fix".
- NOT for: trivial typos, one-off facts, anything with no recurrence risk.

## What to write
One Markdown file: `docs/solutions/<topic-slug>-<YYYY-MM-DD>.md` (create the dir if absent).
YAML frontmatter first — **the surfacing hook matches on these fields**, so fill them with the terms
a future session would plausibly have in its file path or command:

```markdown
---
title: <one-line: symptom → fix>
module: <file(s) or subsystem this applies to — path fragments help matching>
tags: [<tech>, <problem-class>, <tool>]
problem_type: <bug | gotcha | best-practice | anti-pattern>
---

## Problem
<the symptom as a future person would first see it — error text verbatim if any>

## Root cause
<why it actually happened — not the first theory, the verified one>

## Fix
<what resolved it, concretely — commands/diff fragments, and how it was VERIFIED>

## How to avoid / detect early
<the tell-tale sign + the check that catches it in seconds next time>
```

## Quality bar
- **Symptom-first title.** Future-you searches by symptom, not by solution.
- **Verbatim error text** in Problem — that's what gets grepped.
- **Verified root cause only.** If the cause is a guess, say so explicitly.
- **≤60 lines.** An entry nobody reads compounds nothing.

## The loop this completes
`compound` (producer) → `docs/solutions/*.md` → `pretooluse-solution-surface` hook (consumer) →
lesson re-injected before the next related edit. Both halves ship in this plugin; the knowledge
base starts empty and grows from *your* repo's real history.
