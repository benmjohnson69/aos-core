<!-- discipline_version: 1 -->
# Operating Discipline

*Advisory checklist, content-free by construction. This document names contracts
that aos-core hooks already enforce (or advise on) — it does not add a new gate.
Nothing here blocks a tool call; it is a per-tick reference for a human or an
agent who wants the discipline the mechanism layer was built to support.*

## Per-tick checklist

Run this at the start of every substantive work block, not just once per session.

1. **Declare a mode** — BUILDER (shipping code), ANALYST (research/diagnosis),
   SYSTEMS_THINKING (architecture/design), or EVALUATOR (reviewing someone
   else's work). If you can't name the mode, you're free-forming — stop and
   name it before the first tool call.
2. **Research before you build (R1-R4).** Before writing new code: search the
   local corpus (`docs/solutions/`, existing tools/skills) for prior art, check
   whether a registry or capability list already covers the deliverable, and
   confirm the gap is real. Cap research at ~20% of the task's time — once you
   have enough to build, build. Research that never produces code is not a
   deliverable.
3. **Build.**
4. **Verify with real tools, not the diff.** `ruff check <file>`,
   `mypy --ignore-missing-imports <file>`, `python3 -m py_compile <file>` after
   every `.py` write — this is the contract `posttooluse-e2.py` checks for you;
   the discipline is treating its output as load-bearing, not decorative. Then
   run the actual code against real data or a real caller. Reading your own
   diff and pattern-matching "this looks right" is not verification.
5. **Prove acceptance at the artifact level.** "The function exists" is not
   done. "I ran it through its real caller and the output changed as expected"
   is done. If there is no real caller yet, wire one before claiming done.
6. **Adversarial self-review for anything nontrivial.** A change over ~50 lines
   or touching more than a few files gets a second, independent pass — ideally
   a separate agent/session with no stake in the first pass's self-assessment.
   Fix what it finds; don't argue with a review you commissioned.
7. **Write the after-action note from measurement, not memory.** If you're
   recording what changed or what improved, pull the numbers from a rerun —
   before/after — never from what you recall writing.

## Standing rules

**Every check ships with its fail-oracle named.** A predicate, test, or gate
that always passes has proven nothing. When you add a check, also show it
failing against a state where the answer is genuinely "no" (an empty
directory, a reverted commit, a missing file). A check that passes both the
real repo and an empty tree is not discriminating between done and not-done —
it's decoration. This has caught real bugs: predicates that exit non-zero for
the wrong reason (e.g. a test selector matching zero tests) read as "not a
failure" and slip through count-based gates that only check "something ran."

**Two overrides of the same gate = stop and fix the gate, not the third
override.** If you find yourself bypassing, disabling, or arguing past the
same check twice, the check is either wrong or the workflow around it is —
either way, patching around it a third time compounds the debt instead of
resolving it.

**Repeat-fire self-explanation is the bar for a future gate.** Before hard-
coding a new blocking rule, ask whether a clear explanation at the moment of
the mistake — offered consistently, every time the pattern recurs — would
have been enough. If a soft explanation reliably prevents the repeat, that's
cheaper than a hard gate and should be tried first. Promote to a mechanical
gate only after the soft version demonstrably fails to hold.

**Mutual critique, every tick, both directions.** When two agents or sessions
are collaborating on the same deliverable, each side reviews the other's
output — not just the human reviewing the agent. Check for: did this actually
get simpler or did complexity just move somewhere else (paradigm-shift check);
is there a genuine insight here worth capturing (eureka check); would a
motivated skeptic accept this as done. Skipping the reverse direction (agent
critiquing human-authored scope, not just vice versa) is the common failure.

## Membrane invariants (do not weaken these)

These are structural properties of the mechanism layer, not preferences:

- **Advisory-only.** Hooks that check code quality, capability coverage, or
  process discipline warn and inform; they do not silently rewrite content or
  block work outright, unless a rule explicitly says "hard-block" and ships
  with its own fail-oracle proof.
- **No personal data in the mechanism layer.** The plugin and its checklists
  hold no names, employer specifics, transcripts, or identity content. That
  content lives in a separate, gitignored, user-owned directory the mechanism
  loads only if present and degrades cleanly without.
- **Fail-closed outbound gate.** Anything that assembles content for
  distribution outside the local machine (a bundle, a release artifact, a
  shared doc) must fail the build rather than ship partial or unscanned
  content when its scan step errors or its denylist can't be loaded. Silent
  partial success on an outbound path is the one failure mode this layer
  cannot tolerate.

## Why this exists

None of this replaces judgment. It exists because the failure modes it guards
against are cheap to fall into and expensive to notice later: skipping
verification because the code "looks right," shipping a check that can never
fail, overriding the same gate until it's meaningless, or writing a status
note from what you remember instead of what you just measured. The checklist
is the fast path back to the discipline that was already working.
