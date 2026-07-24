# Coding Team Personas

5-scout IHSD coding team for T0/T1/T2 code reviews.

| Scout | File | Tier | Primary Concern |
|---|---|---|---|
| Implementer | implementer.md | T0,T1,T2 | Spec compliance, completeness |
| Security Auditor | security_auditor.md | T0,T1 | Injection, trust boundaries, secrets |
| Test Engineer | test_engineer.md | T0,T1,T2 | Test coverage, feature verification |
| Integration Checker | integration_checker.md | T0,T1,T2 | E7 wiring, callers, entry points |
| Adversarial Reviewer | adversarial_code_reviewer.md | T0,T1,T2 | Bugs, edge cases, regressions |

## Fan-out by Tier
- T0 (critical): All 5 scouts + Opus referee
- T1 (important): Implementer + Security + Test + Integration + Adversarial (5 scouts) + Sonnet referee
- T2 (standard): Implementer + Integration + Adversarial (3 scouts) + Sonnet referee
- T3 (low): Adversarial only (1 scout, no referee)

**Fan-out table correctness note:** T1 now includes all 5 scouts (Implementer + Security + Test + Integration + Adversarial). T2 drops Security Auditor and Test Engineer — "standard" reviews still check spec compliance, wiring, and regressions. 2026-04-24: fixed T1 to include Implementer and Integration Checker; prior T1 silently skipped spec compliance and wiring checks.

## Coverage Gaps

Identified by adversarial review 2026-04-24. No existing persona owns these categories:

### 1. String constant / magic value correctness (HIGH PRIORITY)
**Description:** Wrong string literals, event names, tool identifiers, enum values, or config keys in filter conditions, comparisons, or dispatch routing. Code looks syntactically correct, passes linters and type checkers, but gates on the wrong value.
**Real example:** `cost-governor-precall.py` checked `tool_name != "Task"` when Claude Code dispatches Agent() calls as tool `"Agent"`. Hook ran silently for weeks, zero entries in router_decisions.jsonl.
**Nearest owner:** Adversarial Code Reviewer (most appropriate) + Integration Checker (for wiring-layer constants). Both have revision notes adding checklist items for this.
**Status:** Partially covered via revision notes. Not fully owned by any single persona.

### 2. Performance regression detection
**Description:** No persona evaluates whether a change degrades throughput, latency, or memory consumption. Relevant for changes to hot paths, loops, or database queries.
**Nearest owner:** None. Would require a new "Performance Scout" persona or explicit addition to Adversarial Reviewer scope.
**Status:** Unowned gap. Accept as out-of-scope for this team OR add a T0-only Performance Scout.

### 3. API contract / payload semantics at wiring layer
**Description:** Integration Checker verifies structural wiring (A calls B) but not whether A sends B the expected payload shape, field names, or types. Silent drift between caller and callee contract.
**Nearest owner:** Integration Checker (revision notes added). Not fully covered by any single checklist item.
**Status:** Partially addressed in Integration Checker revision notes.

### 4. Observability completeness
**Description:** No persona checks that the right structured events are emitted to the right sink with the right schema. "Output is observable" (Integration Checker) checks the path exists; it does not check the event schema, field names, or that the sink is actually receiving data.
**Nearest owner:** Integration Checker (partial). Test Engineer should verify sink is non-empty after triggering call (revision notes added).
**Status:** Partially addressed via revision notes to both Integration Checker and Test Engineer.

### 5. Backwards compatibility / caller contract preservation
**Description:** No persona explicitly owns "does this change break existing callers that weren't updated?" Adversarial Reviewer has a regression risk item but it's framed around test suite coverage, not semantic contract preservation.
**Nearest owner:** Integration Checker (E7 wiring is adjacent). Adversarial Reviewer (regression risk item).
**Status:** Weak coverage. The two personas' items together may be sufficient for most cases.
