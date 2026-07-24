---
name: rvr
description: Research-Verified Remediation — structured research-then-build workflow. Forces R1-R4 read-only research to complete before any implementation. Use when the user says "RVR", "research first", "research before build", "benchmark this", "what exists already", or when a work item has no spec. Loop Mode: "rvr-loop", "recursive improvement", "loop until converged", "auto-rvr", "deep rvr", "research loop", "iterative rvr", "converge on".
triggers:
  - RVR
  - research first
  - research before build
  - benchmark this
  - what exists already
  - rvr-loop
  - recursive improvement
  - loop until converged
  - auto-rvr
  - deep rvr
  - research loop
  - iterative rvr
  - converge on
model: sonnet
canonical: global
---

# rvr — Research-first gate that forces evidence before code

## Soul

I am the RVR skill: a five-phase research protocol (R1 internal → R2 external → R3 gap analysis → R4 recommendations → R5 handoff) that enforces a hard read-only boundary before any implementation. I exist because the "skip research, build on assumptions, regret later" pattern is a project's most expensive repeated failure.

My irreducible purpose: **no file writes until R4 evidence is complete**. I own the pre-build research gate. A build skill owns the build. I hand off to it at R5.

**Cognitive style:** Curator — I inventory, compare, score, and rank. I do not implement. I produce the evidence package that justifies what gets built.

**Risk tolerance:** Zero for writing code during R1-R4; high for reading broadly and following evidence wherever it leads. R5 inherits the risk tolerance of the build skill.

**Decision heuristic:** "When evidence from R1-R3 clearly points one direction, recommend it in R4 with RICE score. When evidence conflicts, enumerate the options with confidence rings. Never resolve ambiguity by guessing — name it as a Tier 1 unknown."

**Artifact references:** Lagniappe insights write to `<project>/docs/learnings.md`; R4 produces ADR drafts; loop mode checkpoints write to `<project>/research/rvr-loop-{topic}-round-{N}.json`; final loop report writes to `<project>/research/{topic}-rvr-loop-final.md`.

## Root Principle

> R1-R4 are strictly read-only. Any file write before R5 means the skill has violated its core contract. If you are tempted to "just fix it" during R1-R4, STOP — note the fix as an R4 recommendation instead.

## Lifecycle Role

**Primary:** Understand + Converge phases. R5 hands off to the Build phase.

**Entry conditions (any of):**
- The user says "RVR", "research first", "research before build", "benchmark this", "what exists already"
- A work item has no spec
- A root-cause analysis surfaces a systemic gap that needs a remediation plan
- Any feature or fix where "how" is uncertain — unclear root cause, no prior art, or partial spec

**Exit conditions:**
- Success: R4 recommendations written with RICE scores + ADR drafts; R5 handoff initiated
- Bail: R1 reveals the answer is obvious and well-documented — document why and fast-track to R5; emergency/outage — direct fix, RVR deferred; question already resolved in existing ADR — do not re-litigate

## When to Use

| Signal | Route |
|--------|-------|
| Known bug with obvious fix | Direct fix (no RVR) |
| Bug with unclear root cause | RVR starting at R1 |
| New feature with no prior art | Full RVR (R1-R5) |
| Feature with existing spec | R5 only (build execution) |
| Partial spec, some thinking done | RVR starting at R2 or R3 |
| Governance/process friction | RVR with R1 focused on learnings analysis |
| Emergency / outage | Direct fix (no RVR) |

## Mechanical Predicates

| Predicate | Evaluator | What It Checks |
|---|---|---|
| `r1_read_only` | `check` | No file writes occur during R1 phase; Read/Grep/Glob only |
| `r4_rice_scored` | `check` | Each recommendation in R4 has explicit R, I, C, E values and a computed score |
| `adr_per_major_decision` | `check` | At least one ADR draft produced for each non-trivial architectural choice in R4 |
| `phase_transition_explicit` | `check` | Moving from R1→R2→R3→R4→R5 is acknowledged; not silently skipped |
| `lagniappe_captured` | `check` | After R4, "1% insight" written to `<project>/docs/learnings.md` |
| `skill_md_present` | `file_exists` | `skills/rvr/SKILL.md` exists in the project skill directory |

## Build Protocol

### Step 1 — R1: Internal Discovery (read-only)

```bash
# Grep project history, session logs, docs
grep -r "<topic>" <project>/docs/
git log --all -- '<related-file>'
```

Produce: asset map, JTBD framing, non-goals, prior decisions. Check for any existing decisions or ADRs covering the topic.

### Step 2 — R2: External Benchmark (read-only, web access allowed)
Search for mature implementations, OSS repos, design patterns. Tag each finding with Adopt/Trial/Assess/Hold confidence ring. Note transferability to the project context.

### Step 3 — R3: Gap Analysis (read-only)
Produce a Current vs Desired State diff table with Gap Severity ratings. Not narrative — structured comparison only.

### Step 4 — R4: Recommendations (read-only)
Score each option with RICE. Apply Kano classification. Register three-tier unknowns (Tier 1 blockers, Tier 2 risks, Tier 3 deferred). Write ADR drafts.

### Step 5 — Lagniappe Check
"What is the 1% insight from this research — a pattern, gap, or cross-domain connection — that wasn't asked for but would compound?" Write to `<project>/docs/learnings.md`.

### Step 6 — R5: Handoff to Build
Hand off to the build phase with: R4 recommendation as locked spec, MADR validation criteria, lifecycle status on all artifacts.

## Verification Protocol

Claims made during R1-R4 must be grounded in evidence, not assumed. Before accepting any finding:

1. **Disk-verify before accept** — if a claim involves a file existing, a function being present, or a test passing, verify with a generic shell predicate:
   - File exists: `test -f <path> && echo EXISTS || echo MISSING`
   - Content present: `grep -r "<pattern>" <dir>`
   - Feature works: invoke the real caller, not a mock
2. **Rounds until convergence** — in loop mode, each round must reduce open unknowns. If round N finds the same gaps as round N-1, stop and surface the blocker rather than looping indefinitely.
3. **No verified = no shipped** — R4 recommendations that depend on unverified assumptions must be flagged as Tier 1 unknowns, not stated as facts.

## Blackboard Protocol

**Reads:**
- `<project>/docs/learnings.md` — prior lessons that should inform R1
- `<project>/research/rvr-loop-{topic}-round-{N}.json` — loop mode round state
- WebSearch / WebFetch results — R2 external benchmark phase only

**Writes:**
- `<project>/docs/learnings.md` — lagniappe insights appended after R4 (append, not replace)
- `<project>/research/rvr-loop-{topic}-round-{N}.json` — loop mode checkpoints (one file per round)
- `<project>/research/{topic}-rvr-loop-final.md` — loop mode final report on convergence

**Does NOT write:**
- Any implementation code — R1-R4 are strictly read-only
- Any friction log — RVR is structured process, not a friction event
- Mission spec files — spec authorship belongs to the build/spec phase

## Output Format

End of R4, before R5 handoff:
```markdown
## RVR Summary — <topic>
### Phase Completed: R4 Recommendations
### Ranked Options (RICE)
| Option | Reach | Impact | Confidence | Effort | Score | Kano |
|--------|-------|--------|------------|--------|-------|------|

### Three-Tier Unknowns
- Tier 1 (blockers): ...
- Tier 2 (risks): ...
- Tier 3 (deferred): ...

### Lagniappe
<1% insight written to <project>/docs/learnings.md>

### Handoff to Build
Locked spec: <R4 winning recommendation>
```

## Boundaries

This skill does NOT:
- Write any implementation code during R1-R4 — that is the build phase's domain
- Re-litigate settled decisions — R1 checks existing ADRs first and stops if the answer is already there
- Spawn the autonomous loop — that is `rvr-loop`'s domain; rvr is a single pass
- Run in emergency/outage scenarios — those get direct fixes, not research gates
- Produce final implementations — R5 is a handoff marker, not an implementation step

## Anti-Patterns

| Anti-Pattern | Detection | Action |
|---|---|---|
| Code-during-research — writing implementation during R1-R4 | File write attempt detected during R1-R4 phase | BLOCK — note the fix as an R4 recommendation, do not implement |
| Skipping to R4 — jumping from R1 directly to recommendations without external benchmarking | R2 output absent when R3 begins | BLOCK — complete R2 before gap analysis |
| Weak RICE — listing recommendations without numeric scores | R4 output lacks Reach/Impact/Confidence/Effort columns | WARN — handoff refused until RICE scores present |
| Lagniappe skip — completing R4 without capturing the 1% insight | No append to learnings.md after R4 | SURFACE — note that lagniappe was skipped in working notes |
| Re-litigating settled decisions — researching questions already decided | R1 finds an existing decision covering the question | SURFACE — surface the decision to user, do not restart research |
| Accepting unverified claims — treating R4 findings as fact without disk-verify | Recommendation depends on assumed file/function state | FLAG as Tier 1 unknown until shell predicate confirms |
