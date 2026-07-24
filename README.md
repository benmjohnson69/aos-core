# AOS Core

*MIT licensed — © 2026 Benjamin Johnson. A personal project; see [NOTICE.md](NOTICE.md) for
authorship and provenance.*

A **persistent-teammate substrate** for Claude Code, extracted from AOS as a clean, installable plugin.
It gives any Claude session three things — **turn-0 identity**, **compaction survival**, and **write-time
coding hygiene** — and it is **content-free by construction**: the plugin holds no personal data, ever.

## Why this exists
AOS is ~1,000 tools, but its genuine value is ~11 content-free *mechanisms*. This plugin is those
mechanisms, decoupled from AOS internals (only `aos_logging` needed replacing) so they install identically
on any Mac — personal or corporate — with **zero risk of leaking confidential data**, because the artifact
contains none.

## The safety model — content-free by construction
- The plugin ships **no identity text, no facts, no memory, no transcripts.**
- All personal content lives in a separate directory you own: **`~/.aos-private/`** (override with `AOS_PRIVATE_DIR`).
- Every hook loads private content **only if present** and degrades to a clean, generic work persona when absent.
- Result: on a **corporate work Mac** with no `~/.aos-private/`, Core runs a clean professional persona. On your
  **personal Mac** with `~/.aos-private/` present, the *same plugin* lights up your full identity. Same artifact, two faces.
- Verify the property: `grep -ri <your-name> aos-core/` returns nothing. You cannot leak what isn't there.

### `~/.aos-private/` layout (you create this, never commit it)
```
~/.aos-private/
  identity/anchor.md        # your identity + voice anchor (kept <2KB; oversized anchors get truncated at turn-0)
  PERSONAL/FRESH_STATE.md   # optional: latest-state digest (generate with build_personal_fresh_state.py)
  banned_tokens.txt         # optional: one hallucination-token per line, scrubbed from the anchor
```

## What's in the plugin (v0.1.0)
| Mechanism | Hook | Content-free? |
|---|---|---|
| Turn-0 identity anchor | `hooks/sessionstart-identity.py` | yes (loads `~/.aos-private/identity/anchor.md` or a clean default) |
| Write-time E2 (ruff+mypy+py_compile, alert-only) | `hooks/posttooluse-e2.py` | yes (uses PATH tools or `AOS_CORE_PY`) |
| Compaction survival — snapshot before, restore after | `hooks/precompact-flush.py` → `postcompact-restore.py`, backstopped by `compaction-check.py` | yes (lossless JSON snapshot to `AOS_CORE_STATE_DIR`, default `~/.claude/aos-core-state`; optional `~/.aos-private/floor.md` re-injected) |
| Prior-fix surfacing — matching solution pushed into context before you edit | `hooks/pretooluse-solution-surface.py` | yes (greps `AOS_CORE_SOLUTIONS_DIR`, default `<cwd>/docs/solutions`; plugin ships none — each repo accumulates its own) |
| Delegation hygiene — E2 injected into every sub-agent spawn | `hooks/pretooluse-agent-e2.py` (Agent\|Task) | yes (advisory; optional dispatch log to `AOS_CORE_STATE_DIR`) |
| Search-before-you-build — repo capability registry surfaced at turn-0 | `tools/build_feature_registry.py` → `hooks/sessionstart-feature-registry.py` | yes (indexes `<repo>/tools` + `skills`; summary at `<cwd>/data/feature_registry_summary.md`) |
| Session continuity — resumable handoff at session close | `skills/session-close/` + advisory `hooks/stop-session-close.py` | yes (handoffs to `<cwd>/docs/session-handoffs/`) |
| Storm-proof commit — CAS plumbing commit that never touches `.git/index.lock` | `tools/git_plumbing_commit.py` | yes (generic git; zero config) |

### Behavior skills (v0.2) — a keyword control language
| Skill | Trigger phrases | What it does |
|---|---|---|
| `skills/rvr/` | "RVR", "research first", "benchmark this", "rvr-loop", "converge on" | research→verify→remediate loop; R1-R4 read-only research before build; disk-verify-before-accept; rounds until convergence |
| `skills/eureka/` | "eureka", "too complex", "overengineered", "collapse this" | 7-step exhaustion-before-collapse insight capture; simplification only after exhausting the current frame |
| `skills/paradigm-shift/` | "paradigm shift", "reframe the question", "wrong question", "curve jump" | attack the frame, not the plan — TRIZ/Bateson/Meadows-validated reframing |
| `skills/compound/` | "compound this", "write the lesson", "capture this fix" | producer half of the compound loop: writes the docs/solutions entry the prior-fix hook surfaces later |
| `skills/session-close/` | "save session", "wrapping up", "done for now" | resumable handoff before context evaporates |

**How compaction survival works:** PreCompact writes a lossless JSON snapshot (branch, modified files,
last exchanges) + a marker; PostCompact re-injects it within a 10-min window and **consumes** the marker
so it can't double-inject; `compaction-check` (UserPromptSubmit) is the **backstop** — if PostCompact
silently failed, the surviving marker triggers a re-inject on the next prompt. (AOS shipped this backstop
but left it unwired — here it's wired.)

The mechanism layer is complete: identity · compaction survival · write-time E2 · prior-fix surfacing ·
delegation hygiene · search-before-you-build · session continuity · storm-proof commit. Content (identity,
memory, handoffs) accumulates per-machine in `~/.aos-private/` and the working repo — never in the plugin.

## Install (local marketplace)
```bash
# from a clean Claude Code profile
/plugin marketplace add /path/to/aos-core                       # local clone, or the git URL
/plugin install aos-core
# optional, personal Mac only:
mkdir -p ~/.aos-private/identity && $EDITOR ~/.aos-private/identity/anchor.md
```

## Acknowledgments

aos-core stands on patterns learned from others — hat tips:
- **[Claude Code](https://docs.anthropic.com/en/docs/claude-code)** (Anthropic) — the hooks, plugins,
  and skills substrate all of this rides on.
- **[superpowers](https://github.com/obra/superpowers)** (Jesse Vincent) — the skills-first working
  discipline, and the plugin/marketplace structure this repo's packaging was learned from.
- **compound-engineering** (Kieran Klaassen / [Every](https://every.to)) — the compound-learning loop:
  every solved bug becomes a searchable lesson that resurfaces at edit time. The prior-fix surfacing
  hook here descends directly from that pattern.
- **[Ralph](https://ghuntley.com/ralph/)** (Geoffrey Huntley) — the autonomous build-verify-continue
  loop pattern used to develop much of this plugin.

## Verify it works
- Fresh session → the identity anchor appears at turn-0 (clean persona if no private layer).
- Edit a `.py` with a type error → an `⚠️ E2` note surfaces the same turn.
- `AOS_PRIVATE_DIR=/tmp/none python3 hooks/sessionstart-identity.py </dev/null` → prints the clean default (no personal data).

## Doctor & releases (v0.2)

### Doctor — `tools/doctor.py`
One command that answers "is the whole stool green?" Checks all three legs and exits 0 only if no
checks fail. Runs with stdlib only (no third-party dependencies).

```bash
python3 tools/doctor.py           # human-readable aligned table
python3 tools/doctor.py --json    # machine-readable JSON for scripting
```

Checks performed:
1. **Tooling binaries** — `python3` + `git` required (FAIL if absent); `ruff` + `mypy` optional (SKIP if absent — E2 degrades gracefully).
2. **Hooks registered** — detects plugin-installed mode (`installed_plugins.json`) OR direct-mode registrations in `~/.claude/settings.json`. Reports which mode, FAILs if neither.
3. **Hooks fire** — actually invokes `sessionstart-identity.py` with empty stdin; non-empty stdout = PASS.
4. **Identity bundle** — if `~/.aos-private/` is present: checks `identity/anchor.md` non-empty, then runs the banned-token grep gate. If absent: SKIP ("clean persona mode").
5. **Bundle version vs drive** — if `AOS_CORE_DRIVE_DIR` env var is set and reachable, compares local bundle mtime against the newest `aos-private-work-*.tgz` on the drive; notes "update available" if drive is newer. SKIP if env unset.
6. **Tooling leg** — checks `~/.claude/hooks/tool-route-injector.py` present, `~/.claude/tool_routes.json` valid JSON, and `webfetch` registered in `claude mcp list`.

### Work profile manifest — `profile-work.json`
Declarative manifest naming all three legs (mechanisms, identity, tooling). `doctor.py` reads it
at runtime to know what to check; falls back to built-in defaults if the file is absent.

### Release pipeline — `tools/release.sh` (personal Mac side)
Builds, gates, stamps, and publishes the work-profile bundle + plugin mirror to the network drive.
The drive is the release channel; only gate-verified artifacts reach it.

```bash
# defaults: source=~/aos/PERSONAL, drive=/Volumes/tests/sp-mac-v1
bash tools/release.sh

# explicit paths:
bash tools/release.sh ~/aos/PERSONAL /Volumes/NetworkDrive/sp-mac-v1
```

Steps: (a) `build_private_bundle.py --profile work` — grep gate runs inside; any hit aborts.
(b) stamp `version.json` with auto-incremented version and `built_at`. (c) tar to
`aos-private-work-vN.tgz`. (d) copy tarball to drive dir. (e) rsync plugin tree (minus `.git`,
`__pycache__`, `.mypy_cache`) to `<drive>/aos-core-mirror/` for offline installs.

Fail-closed: `set -euo pipefail`; any step failure aborts. Idempotent: safe to run repeatedly;
version auto-increments each run. An unverified byte cannot reach the drive.
