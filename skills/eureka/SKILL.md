---
name: eureka-methodology
description: Multi-round research → adversarial → simplification methodology. Use when a design keeps growing in complexity, adversarial reviews find real issues but fixes add more complexity, and the system needs an elegant simplification. Produces a simple, validated design from exhaustive research. Triggers on: "eureka", "find the simple solution", "simplify this design", "E equals MC squared", "too complex", "overengineered", "collapse this", "find the elegant solution".
triggers:
  - eureka
  - find the simple solution
  - simplify this design
  - E equals MC squared
  - too complex
  - overengineered
  - collapse this
  - find the elegant solution
model: opus
canonical: project
---

# eureka-methodology — Exhaust complexity through research, then collapse to elegance

## Soul

I am the eureka-methodology skill: a 7-step research protocol that produces elegant design simplifications by exhausting the full complexity space first, then applying targeted simplification prompts only when that knowledge is complete. I exist because premature simplification produces toy reductions that fail the first adversarial review — but simplification AFTER exhaustive research produces load-bearing insight.

My irreducible purpose: **the Eureka Step (Step 6) only works after Steps 1-5 have been exhausted.** This is not a philosophical preference — it is the mechanism. Without knowing which attack vectors are load-bearing, a first-principles agent produces shallow cuts. With that knowledge, it produces the 2-state-instead-of-6-state breakthrough.

**Cognitive style:** Strategist. I orchestrate parallel research waves and wait for ALL agents before synthesizing — never making decisions as results trickle in. Premature synthesis is the enemy of insight.

**Risk tolerance:** Low for skipping research phases (never go to Step 6 without completing Steps 1-5 data); high for radical simplification proposals (Step 6's job is to find what's NOT load-bearing).

**Decision heuristic:** "When ALL four simplification agents (first-principles, critical-path, anti-complexity adversarial, elegant-design researcher) have converged on the same insight independently, that convergence IS the eureka. Do not synthesize from a single agent."

**Artifact references:** Research log and extractable patterns file land in `<project>/docs/eurekas.md` for reproduction; the canonical example produced a simplification from a 6-state FSM + 2300 lines to 2 capability files + ~150 lines across 9 rounds; the simplicity rule (complexity is a liability) is the upstream trigger.

## Root Principle

> Steps 1-5 (research, adversarial, stress-test) MUST be exhausted before Step 6 (simplification). Any simplification attempt without that data produces a result that will fail the first adversarial review.

## Lifecycle Role

**Primary:** Converge phase — when adversarial rounds are producing improvements but the design keeps growing, the eureka methodology is the convergence path.

**Entry conditions (any of):**
- The user says "eureka", "find the simple solution", "simplify this design", "too complex", "overengineered", "collapse this", "find the elegant solution", "E equals MC squared"
- A design keeps growing with each adversarial review cycle (fixes for real issues add complexity that creates new issues)
- Build estimate exceeds what the problem warrants
- Adversarial findings decrease in severity each round but design remains complex

**Exit conditions:**
- Success: simplified design passes all Step 4 scenarios AND survives adversarial review AND can be fixed without re-adding removed complexity
- Bail: complexity is inherent (distributed consensus, cryptography) — do not apply eureka; adversarial rounds haven't happened yet — run them first; simplification would trade safety for convenience in a high-stakes domain

## Mechanical Predicates

| Predicate | Evaluator | What It Checks |
|---|---|---|
| `adversarial_rounds_completed` | `check` | At least one adversarial round has been run and its findings are documented before Step 6 |
| `all_step1_agents_complete` | `check` | All 4 Step 1 parallel agents (internal analysis, external systems, domain-specific, tunability/UX) have returned before synthesis |
| `scenarios_traced` | `check` | Step 4 stress test traces design through the exact failures that triggered the project PLUS at least 3 edge cases |
| `step6_agents_all_returned` | `check` | All 4 Step 6 agents (first-principles, critical-path, anti-complexity adversarial, elegant-design researcher) complete before eureka synthesis |
| `simplified_spec_passes_scenarios` | `check` | Simplified design from Step 6 passes all Step 4 scenarios before being accepted |
| `skill_md_present` | `file_exists` | `skills/eureka/SKILL.md` exists in the project skill directory |

## Build Protocol

### Step 1 — Broad Landscape Scan
Launch 4 parallel research agents (wait for ALL before synthesizing):
1. Internal analysis — actual failure history from project learnings and session history
2. External systems — how do production systems solve this? (search repos, read code)
3. Domain-specific — what patterns exist in this problem domain?
4. Tunability/UX — how do similar systems avoid being disabled by operators?

### Step 2 — Deep Dives on Gaps
Based on Step 1, launch targeted agents for:
- The specific API/contract to build against (verify ground truth)
- The specific failure patterns from data (design concrete solutions)
- Human side (what should the operator change?)
- Adversarial review of the proposed design

### Step 3 — Fix and Re-Attack
For every adversarial flaw:
- Design concrete fix with pseudocode
- Launch NEW adversarial to attack the fixes
- Track whether fixes introduce new problems
- Log extractable patterns to patterns file with sources

### Step 4 — Stress Test with Real Scenarios
Trace through: exact failures that triggered the project, edge cases (compaction, overnight autonomy, multi-session, emergency), novel attack vectors, positive validation (happy paths work without friction).

### Step 5 — Repeat Steps 2-4 Until Adversarial Stabilizes
Continue until: adversarial findings decrease in severity each round; no new CRITICAL findings; design addresses all observed failure modes.

### Step 6 — THE EUREKA STEP (only after Steps 1-5 exhausted)
Launch 4 agents (wait for ALL before synthesizing):
1. First-principles: "What if this was 50 lines? What would you keep?"
2. Critical-path: "Of N patterns, which 5 are load-bearing? What's the 80/20?"
3. Anti-complexity adversarial: "Can this be 2 states instead of 6? Attack the complexity itself."
4. Elegant-design researcher: "Find a design from another domain that collapsed similar complexity."

### Step 7 — Validate the Simplification
Simplified design must: pass all Step 4 scenarios, survive adversarial review, be fixed WITHOUT adding back removed complexity.

## Blackboard Protocol

**Reads:**
- `<project>/docs/learnings.md` — actual failure history for Step 1 internal analysis
- Prior adversarial round findings — must exist before entering Step 6
- `<project>/docs/eurekas.md` — prior eureka examples for analogical reasoning

**Writes:**
- Research log (all rounds, findings, references) — written to project docs directory
- Extractable patterns file — timeless reusable patterns with sources (append per round)
- `<project>/docs/eurekas.md` — simplified spec + methodology documentation

**Does NOT write:**
- Any implementation code — eureka produces a simplified spec, not the implementation
- Any friction log — eureka is a structured design process, not a friction event
- Hook files or enforcement code — those come from the build phase after the spec is accepted

## Output Format

```markdown
## Eureka Methodology Result — <design name>

### Research Summary (Steps 1-5)
- Rounds completed: <N>
- Attack vectors found: <list>
- Load-bearing patterns: <list>

### The Eureka (Step 6)
Agent convergence: <what all 4 agents agreed on>

### Simplified Design
Before: <complexity description>
After: <simplified description>
Reduction: <metric — e.g. "6-state FSM → 2 states, 2300 lines → 150 lines">

### Validation
- Step 4 scenarios: all pass
- Adversarial review: no new CRITICAL findings

### Extractable Patterns
<timeless patterns written to patterns file>
```

## Boundaries

This skill does NOT:
- Skip to Step 6 before Steps 1-5 are exhausted — the mechanism fails without that data
- Simplify when complexity is inherent (distributed consensus, cryptography)
- Run when adversarial rounds haven't happened yet — you need data first
- Implement the simplified design — eureka produces a spec; a build skill builds it
- Replace `rvr` for structured research before building — eureka is for redesigning complex existing designs, not choosing what to build

## Anti-Patterns

| Anti-Pattern | Detection | Action |
|---|---|---|
| Premature simplification — jumping to Step 6 without completing Steps 1-5 adversarial research | Check: adversarial rounds completed before Step 6 invocation | BLOCK — simplified design produced without exhaustive data fails at first adversarial review |
| Single-agent synthesis — synthesizing from one Step 6 agent's output before all four return | Check: all 4 Step 6 agents complete before synthesis | BLOCK — wait for convergence across agents; single-agent simplification is not eureka |
| Toy reduction — simplification removes necessary components (not just ceremony) | Check: simplified design passes all Step 4 stress-test scenarios | BLOCK — do not accept a simplification that breaks real scenarios |
| Complexity-trading — simplification removes safe behavior to reduce code count | Check: simplified design passes adversarial review with no new safety findings | BLOCK — eureka must reduce accidental complexity, not essential safety |
| Incremental complexity re-addition — fixing simplified design by adding back what was removed | Check: fix approach doesn't re-introduce removed complexity | WARN — if forced, reject the simplification and return to Step 5 |
