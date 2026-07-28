#!/usr/bin/env python3
"""aos-core doctor — answers "is the whole stool green?"

Checks ten concern areas and reports PASS / FAIL / SKIP for each.
Exit 0 iff no FAILs. --json emits machine-readable JSON.

Usage:
    python3 doctor.py
    python3 doctor.py --json
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants / defaults
# ---------------------------------------------------------------------------
PLUGIN_ROOT = Path(__file__).resolve().parent.parent

# Private layer (overridable via env)
PRIVATE_DIR = Path(os.environ.get("AOS_PRIVATE_DIR", str(Path.home() / ".aos-private")))

# Wall-clock budget for the live-session probe (Check 8) — `claude -p` round trip.
LIVE_PROBE_TIMEOUT = 90

# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------
PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"


class Check:
    def __init__(self, key: str, label: str, status: str, reason: str) -> None:
        self.key = key
        self.label = label
        self.status = status
        self.reason = reason

    def as_dict(self) -> dict:
        return {"key": self.key, "label": self.label, "status": self.status, "reason": self.reason}


def ok(key: str, label: str, reason: str) -> Check:
    return Check(key, label, PASS, reason)


def fail(key: str, label: str, reason: str) -> Check:
    return Check(key, label, FAIL, reason)


def skip(key: str, label: str, reason: str) -> Check:
    return Check(key, label, SKIP, reason)


# ---------------------------------------------------------------------------
# Check 1 — tooling binaries
# ---------------------------------------------------------------------------
def check_tooling_binaries() -> list[Check]:
    """python3/git present; ruff/mypy present (SKIP if absent — E2 degrades gracefully)."""
    results: list[Check] = []
    for binary in ("python3", "git"):
        if shutil.which(binary):
            results.append(ok(f"bin_{binary}", f"{binary} binary", f"found at {shutil.which(binary)}"))
        else:
            results.append(fail(f"bin_{binary}", f"{binary} binary", f"{binary} not on PATH — required"))

    for binary in ("ruff", "mypy"):
        if shutil.which(binary):
            results.append(ok(f"bin_{binary}", f"{binary} binary", f"found at {shutil.which(binary)}"))
        else:
            results.append(
                skip(f"bin_{binary}", f"{binary} binary", f"{binary} absent — E2 degrades to warning (not required)")
            )
    return results


# ---------------------------------------------------------------------------
# Check 2 — hooks registered
# ---------------------------------------------------------------------------
def _load_profile_manifest() -> dict:
    """Load profile-work.json if present next to this file; else return empty dict."""
    manifest_path = PLUGIN_ROOT / "profile-work.json"
    if manifest_path.is_file():
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return {}


def check_hooks_registered() -> Check:
    """Either plugin installed or direct-mode hook registrations exist for aos-core."""
    label = "hooks registered"
    key = "hooks_registered"

    # Mode A: plugin installed
    installed_plugins = Path.home() / ".claude" / "installed_plugins.json"
    if installed_plugins.is_file():
        try:
            data = json.loads(installed_plugins.read_text(encoding="utf-8"))
            for p in data.get("installed", []):
                if "aos-core" in str(p.get("name", "")) or "aos-core" in str(p.get("source", "")):
                    return ok(key, label, f"plugin-installed mode: {p.get('name', 'aos-core')} found in installed_plugins.json")
        except (OSError, ValueError):
            pass

    # Mode B: direct-mode — look for hooks.json in ~/.claude/hooks/ or settings.json entries
    # pointing to aos-core paths
    settings_path = Path.home() / ".claude" / "settings.json"
    if settings_path.is_file():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            hooks = settings.get("hooks", {})
            found_paths = []
            for _event, hook_groups in hooks.items():
                for group in hook_groups:
                    for h in group.get("hooks", [group] if "command" in group else []):
                        cmd = h.get("command", "")
                        if "aos-core" in cmd:
                            found_paths.append(cmd[:80])
            if found_paths:
                return ok(key, label, f"direct-mode: {len(found_paths)} aos-core hook(s) in settings.json")
        except (OSError, ValueError):
            pass

    # Check aos-core's own hooks.json for what WOULD be registered
    plugin_hooks_json = PLUGIN_ROOT / "hooks" / "hooks.json"
    if plugin_hooks_json.is_file():
        return fail(
            key,
            label,
            "aos-core not installed as plugin and no direct registrations in ~/.claude/settings.json "
            f"(plugin hooks.json exists at {plugin_hooks_json} — install with /plugin install aos-core)",
        )

    return fail(key, label, "aos-core not installed and no hooks.json found in plugin root")


# ---------------------------------------------------------------------------
# Check 3 — hooks fire
# ---------------------------------------------------------------------------
def check_hooks_fire() -> Check:
    label = "hooks fire (sessionstart-identity)"
    key = "hooks_fire"
    hook_path = PLUGIN_ROOT / "hooks" / "sessionstart-identity.py"
    if not hook_path.is_file():
        return fail(key, label, f"hook script missing: {hook_path}")
    try:
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        stdout = result.stdout.strip()
        if stdout:
            preview = stdout[:80].replace("\n", " ")
            return ok(key, label, f"emitted {len(stdout)} chars — preview: {preview!r}")
        else:
            stderr_preview = result.stderr[:120].replace("\n", " ")
            return fail(key, label, f"no output (exit {result.returncode}); stderr: {stderr_preview}")
    except subprocess.TimeoutExpired:
        return fail(key, label, "hook timed out after 10s")
    except OSError as exc:
        return fail(key, label, f"could not invoke hook: {exc}")


# ---------------------------------------------------------------------------
# Check 4 — identity bundle
# ---------------------------------------------------------------------------
def check_identity_bundle() -> list[Check]:
    """~/.aos-private present? anchor + banned_tokens checks."""
    results: list[Check] = []
    key_prefix = "identity"
    label_prefix = "identity bundle"

    if not PRIVATE_DIR.is_dir():
        results.append(skip(f"{key_prefix}_present", f"{label_prefix} present", "~/.aos-private absent — clean persona mode"))
        return results

    results.append(ok(f"{key_prefix}_present", f"{label_prefix} present", f"found at {PRIVATE_DIR}"))

    # anchor.md
    anchor = PRIVATE_DIR / "identity" / "anchor.md"
    if anchor.is_file() and anchor.stat().st_size > 0:
        results.append(ok(f"{key_prefix}_anchor", f"{label_prefix} anchor.md", f"present, {anchor.stat().st_size} bytes"))
    elif anchor.is_file():
        results.append(fail(f"{key_prefix}_anchor", f"{label_prefix} anchor.md", "anchor.md is empty"))
    else:
        results.append(fail(f"{key_prefix}_anchor", f"{label_prefix} anchor.md", f"missing: {anchor}"))

    # banned_tokens.txt — run grep gate
    banned_file = PRIVATE_DIR / "banned_tokens.txt"
    if not banned_file.is_file():
        results.append(skip(f"{key_prefix}_grep_gate", f"{label_prefix} grep gate", "no banned_tokens.txt — gate not applicable"))
        return results

    tokens = [t.strip() for t in banned_file.read_text(encoding="utf-8").splitlines() if t.strip()]
    if not tokens:
        results.append(skip(f"{key_prefix}_grep_gate", f"{label_prefix} grep gate", "banned_tokens.txt is empty — gate trivially clean"))
        return results

    # Scan all .md files in private dir EXCEPT banned_tokens.txt itself
    md_files = [f for f in PRIVATE_DIR.rglob("*.md")]
    violations: list[str] = []
    for md in md_files:
        try:
            content = md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for tok in tokens:
            if tok.lower() in content.lower():
                violations.append(f"{md.name}: token {tok!r}")

    if violations:
        sample = "; ".join(violations[:3])
        results.append(fail(f"{key_prefix}_grep_gate", f"{label_prefix} grep gate", f"{len(violations)} violation(s): {sample}"))
    else:
        results.append(ok(f"{key_prefix}_grep_gate", f"{label_prefix} grep gate", f"clean — {len(tokens)} token(s) checked across {len(md_files)} .md file(s)"))

    return results


# ---------------------------------------------------------------------------
# Check 5 — bundle version vs drive
# ---------------------------------------------------------------------------
def check_bundle_version() -> Check:
    label = "bundle vs drive version"
    key = "bundle_version"

    drive_dir_str = os.environ.get("AOS_CORE_DRIVE_DIR", "")
    if not drive_dir_str:
        return skip(key, label, "AOS_CORE_DRIVE_DIR not set — skipping drive version check")

    drive_dir = Path(drive_dir_str)
    if not drive_dir.is_dir():
        return skip(key, label, f"AOS_CORE_DRIVE_DIR set but not reachable: {drive_dir}")

    # Find newest aos-private-work-*.tgz on drive
    tarballs = sorted(drive_dir.glob("aos-private-work-*.tgz"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not tarballs:
        return skip(key, label, "no aos-private-work-*.tgz tarballs found on drive yet")

    newest_drive = tarballs[0]
    drive_mtime = newest_drive.stat().st_mtime

    # Compare with local bundle mtime (use identity/anchor.md as proxy for bundle age)
    anchor = PRIVATE_DIR / "identity" / "anchor.md"
    if not anchor.is_file():
        return skip(key, label, f"drive tarball exists ({newest_drive.name}) but no local bundle to compare")

    local_mtime = anchor.stat().st_mtime

    if drive_mtime > local_mtime:
        import datetime  # noqa: PLC0415  (stdlib, inside function — ok)
        drive_dt = datetime.datetime.fromtimestamp(drive_mtime).strftime("%Y-%m-%d %H:%M")
        local_dt = datetime.datetime.fromtimestamp(local_mtime).strftime("%Y-%m-%d %H:%M")
        return ok(
            key,
            label,
            f"update available — drive: {newest_drive.name} ({drive_dt}) > local anchor ({local_dt})",
        )
    else:
        return ok(key, label, f"local bundle is current vs drive ({newest_drive.name})")


# ---------------------------------------------------------------------------
# Check 6 — tooling leg
# ---------------------------------------------------------------------------
def check_tooling_leg(live: bool = False) -> list[Check]:
    """tool-route-injector.py present, tool_routes.json valid, webfetch MCP registered."""
    results: list[Check] = []

    # injector
    injector = Path.home() / ".claude" / "hooks" / "tool-route-injector.py"
    if injector.is_file():
        results.append(ok("tooling_injector", "tool-route-injector.py", f"present at {injector}"))
    else:
        results.append(fail("tooling_injector", "tool-route-injector.py", f"not found at {injector}"))

    # tool_routes.json
    routes_path = Path.home() / ".claude" / "tool_routes.json"
    if routes_path.is_file():
        try:
            json.loads(routes_path.read_text(encoding="utf-8"))
            results.append(ok("tooling_routes", "tool_routes.json", f"present + valid JSON at {routes_path}"))
        except ValueError as exc:
            results.append(fail("tooling_routes", "tool_routes.json", f"invalid JSON: {exc}"))
    else:
        results.append(fail("tooling_routes", "tool_routes.json", f"not found at {routes_path}"))

    # webfetch MCP
    results.append(_check_webfetch_mcp_live() if live else _check_webfetch_mcp_config())
    return results


def _check_webfetch_mcp_config() -> Check:
    """Primary probe: read MCP registration off disk — instant, no subprocess.

    A `claude mcp list` SKIP that never resolves (10s timeout hit daily on the
    work Mac) trains readers to ignore the row. Reading config directly is
    what the CLI itself does to build its list, so it's equally authoritative
    and doesn't depend on a live process/timeout budget. `--live` still runs
    the deeper subprocess probe on request.
    """
    label = "webfetch MCP registered"
    key = "tooling_webfetch"
    server_name = "webfetch"
    candidates: list[tuple[str, dict]] = []

    claude_json = Path.home() / ".claude.json"
    if claude_json.is_file():
        try:
            data = json.loads(claude_json.read_text(encoding="utf-8"))
        except ValueError:
            data = {}
        top_servers = data.get("mcpServers", {})
        if server_name in top_servers:
            candidates.append(("~/.claude.json (top-level mcpServers)", top_servers[server_name]))
        cwd = str(Path.cwd())
        proj_servers = data.get("projects", {}).get(cwd, {}).get("mcpServers", {})
        if server_name in proj_servers:
            candidates.append((f"~/.claude.json projects[{cwd}].mcpServers", proj_servers[server_name]))

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if project_dir:
        mcp_json = Path(project_dir) / ".mcp.json"
        if mcp_json.is_file():
            try:
                pdata = json.loads(mcp_json.read_text(encoding="utf-8"))
            except ValueError:
                pdata = {}
            pservers = pdata.get("mcpServers", {})
            if server_name in pservers:
                candidates.append((str(mcp_json), pservers[server_name]))

    if not candidates:
        return fail(
            key,
            label,
            "webfetch not found in ~/.claude.json (top-level or projects[cwd]) "
            "or $CLAUDE_PROJECT_DIR/.mcp.json [config-read mode]",
        )

    source, cfg = candidates[0]
    cmd = cfg.get("command")
    if not cmd:
        # url/sse-type transport — no local executable to validate.
        return ok(key, label, f"webfetch registered in {source} (transport={cfg.get('type', 'unknown')}) [config-read mode]")

    cmd_path = Path(cmd)
    if not cmd_path.is_file():
        return fail(key, label, f"webfetch registered in {source} but command not found: {cmd} [config-read mode]")
    if not os.access(cmd_path, os.X_OK):
        return fail(key, label, f"webfetch registered in {source} but command not executable: {cmd} [config-read mode]")
    return ok(key, label, f"webfetch registered in {source}, command executable at {cmd} [config-read mode]")


def _check_webfetch_mcp_live() -> Check:
    """Deeper probe: shell out to `claude mcp list` (subprocess, 10s budget)."""
    label = "webfetch MCP registered"
    key = "tooling_webfetch"
    claude_bin = shutil.which("claude")
    if not claude_bin:
        return skip(key, label, "claude CLI not on PATH — cannot check MCP list [live mode]")
    try:
        result = subprocess.run(
            [claude_bin, "mcp", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = result.stdout + result.stderr
        if re.search(r"\bwebfetch\b", output, re.IGNORECASE):
            return ok(key, label, "webfetch found in `claude mcp list` [live mode]")
        else:
            return fail(key, label, "webfetch NOT found in `claude mcp list` [live mode]")
    except subprocess.TimeoutExpired:
        return skip(key, label, "claude mcp list timed out after 10s [live mode]")
    except OSError as exc:
        return skip(key, label, f"could not invoke claude CLI: {exc} [live mode]")


# ---------------------------------------------------------------------------
# Check 7 — annotation compat (PEP 604 unions vs the target Python)
# ---------------------------------------------------------------------------
def _uses_pep604_union(tree: ast.AST) -> bool:
    """True if any annotation uses the `X | Y` union operator (PEP 604, 3.10+)."""
    for node in ast.walk(tree):
        ann = None
        if isinstance(node, ast.AnnAssign):
            ann = node.annotation
        elif isinstance(node, ast.arg):
            ann = node.annotation
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            ann = node.returns
        if ann is None:
            continue
        for sub in ast.walk(ann):
            if isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.BitOr):
                return True
    return False


def check_import_compat() -> list[Check]:
    """Static guard for the F1 bug class: PEP 604 unions (`dict | None`) crash at
    import time on Python < 3.10 UNLESS the file carries `from __future__ import
    annotations`. py_compile does NOT catch this — annotations are only evaluated at
    module-exec time. This runs under the *target* interpreter, so it flags exactly
    the files that would crash on THIS machine, and passes cleanly on 3.10+."""
    key, label = "import_compat", "annotation compat (PEP 604 vs this Python)"
    if sys.version_info >= (3, 10):
        return [ok(key, label, f"Python {sys.version_info.major}.{sys.version_info.minor} — PEP 604 unions native, no risk")]

    offenders: list[str] = []
    scanned = 0
    for py in PLUGIN_ROOT.rglob("*.py"):
        try:
            src = py.read_text(encoding="utf-8")
        except OSError:
            continue
        scanned += 1
        if "from __future__ import annotations" in src:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue  # a genuine syntax error belongs to a different check
        if _uses_pep604_union(tree):
            offenders.append(str(py.relative_to(PLUGIN_ROOT)))

    if offenders:
        sample = ", ".join(sorted(offenders)[:5])
        more = f" (+{len(offenders) - 5} more)" if len(offenders) > 5 else ""
        return [fail(
            key,
            label,
            f"{len(offenders)} file(s) crash on import under Python "
            f"{sys.version_info.major}.{sys.version_info.minor}: {sample}{more} "
            "— add `from __future__ import annotations`",
        )]
    return [ok(key, label, f"clean — {scanned} .py file(s) scanned, no unguarded PEP 604 unions")]


# ---------------------------------------------------------------------------
# Check 8 — live-session probe (F10)
# ---------------------------------------------------------------------------
def check_live_session() -> Check:
    """THE meta-check. Every other check tests a component in isolation; this one
    asks the only question that matters: when Claude Code actually starts, do the
    hooks fire?

    Five real defects — two of them blockers — sat behind a GREEN bar because
    nothing ever ran the real caller. F8 is the canonical case: a `statusLine`
    entry missing its `"type"` discriminator silently invalidated the ENTIRE hooks
    block. Every isolated check still passed: the files existed, the JSON parsed,
    the hooks executed fine when invoked by hand. Only a live session showed that
    Claude Code had loaded none of them.

    Spawns `claude -p` and asserts the SessionStart hook actually fired in the
    debug log. Skips (never fails) when the CLI is absent or the probe cannot run,
    so this is safe in CI and on a partial install.

    Set AOS_CORE_DOCTOR_NO_LIVE=1 to skip — also set automatically in the child's
    environment so a doctor invoked from inside a hook can never recurse.
    """
    key, label = "live_session", "live session — hooks actually load"

    if os.environ.get("AOS_CORE_DOCTOR_NO_LIVE"):
        return skip(key, label, "AOS_CORE_DOCTOR_NO_LIVE set — live probe disabled")
    if not shutil.which("claude"):
        return skip(key, label, "claude CLI not on PATH — cannot probe a live session")

    # A SessionStart hook must be registered, or the probe proves nothing.
    try:
        settings = json.loads((Path.home() / ".claude" / "settings.json").read_text())
    except (OSError, ValueError):
        return skip(key, label, "~/.claude/settings.json unreadable — nothing to probe")
    registered = [
        h.get("command", "")
        for group in settings.get("hooks", {}).get("SessionStart", [])
        for h in group.get("hooks", [])
    ]
    if not registered:
        return skip(key, label, "no SessionStart hook registered — nothing to probe")

    env = dict(os.environ)
    env["AOS_CORE_DOCTOR_NO_LIVE"] = "1"  # child must never re-enter this check

    with tempfile.TemporaryDirectory() as td:
        log = Path(td) / "probe.log"
        try:
            subprocess.run(
                ["claude", "-p", "say OK", "--no-session-persistence",
                 "--debug", "hooks", "--debug-file", str(log)],
                capture_output=True, text=True, timeout=LIVE_PROBE_TIMEOUT, check=False,
                cwd=td, env=env, stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired:
            return skip(key, label, f"probe exceeded {LIVE_PROBE_TIMEOUT}s — network or auth, not a hook defect")
        except OSError as exc:
            return skip(key, label, f"probe could not run ({type(exc).__name__}) — not a hook defect")

        try:
            text = log.read_text(errors="ignore")
        except OSError:
            return skip(key, label, "debug log unreadable — probe inconclusive")

    # The exact line Claude Code emits when a SessionStart hook returns successfully.
    if "Hook SessionStart:startup (SessionStart) success" in text:
        return ok(key, label, f"SessionStart fired in a real session ({len(registered)} hook(s) registered)")

    # Registered but did not fire. This is the F8 signature — and the whole reason
    # this check exists. Name the most likely cause rather than just reporting dead.
    hint = ""
    sl = settings.get("statusLine")
    if isinstance(sl, dict) and sl.get("type") != "command":
        hint = ' — statusLine is missing \'"type": "command"\', which silently voids the entire hooks block (F8)'
    elif not isinstance(sl, (dict, type(None))):
        hint = " — statusLine is not an object; an invalid value voids the entire hooks block (F8)"
    return fail(key, label,
               f"{len(registered)} SessionStart hook(s) registered but NONE fired in a live session{hint}")


# ---------------------------------------------------------------------------
# Check 8b — per-hook invocability (F10, complements the live-session probe)
# ---------------------------------------------------------------------------
# Tokens that precede a script path and are never part of it (interpreter /
# shell-builtin invocation words). Anything else preceding the script token
# (that isn't a `-flag`) is presumed to be part of a space-containing path
# that a naive whitespace split truncated.
_HOOK_INTERPRETERS = {"python", "python3", "python2", "sh", "bash", "zsh", "env", "source", "."}
_SCRIPT_SUFFIX_RE = re.compile(r"\.(py|sh)$", re.IGNORECASE)


def _iter_registered_hooks(settings: dict) -> list[tuple[str, str]]:
    """Yield (event_name, command_string) for every hook entry across all events."""
    out: list[tuple[str, str]] = []
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        return out
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            for h in group.get("hooks", []):
                if isinstance(h, dict) and "command" in h:
                    out.append((str(event), str(h["command"])))
    return out


def _script_token_index(tokens: list[str]) -> int | None:
    for i, tok in enumerate(tokens):
        if _SCRIPT_SUFFIX_RE.search(tok):
            return i
    return None


def _extract_script_from_segment(segment: str) -> tuple[str, str] | None:
    """Find the script token in one (non-'&&') command segment and resolve it
    to a real path. Returns (status, path) where status is:
      'found'       — resolved to an existing file
      'missing'     — a candidate (single-token, or the full literal
                       reconstruction of a space-split path) confidently does
                       not exist — report dead with the untruncated path
      'unparseable' — the command's quoting could not be parsed at all (shlex
                       failure); named, not guessed, rather than declared dead
    Returns None if the segment contains no .py/.sh-suffixed token at all."""
    try:
        tokens = shlex.split(segment, posix=True)
    except ValueError:
        # Unbalanced quotes etc — cannot trust any reconstruction from this
        # segment. Best-effort locate a script-looking token to name it, but
        # report unparseable rather than risk a false-dead verdict.
        tokens = segment.split()
        idx = _script_token_index(tokens)
        if idx is None:
            return None
        return ("unparseable", segment.strip())

    if not tokens:
        return None
    idx = _script_token_index(tokens)
    if idx is None:
        return None

    candidate = tokens[idx]
    path = Path(os.path.expanduser(candidate))
    if path.is_file():
        return ("found", str(path))

    # shlex already honors quotes, so if the true path contained spaces and was
    # quoted in the command string, `candidate` above is already the full path
    # and simply doesn't exist (missing). Ambiguity only arises when the path
    # was UNQUOTED and whitespace split it — collect the preceding tokens that
    # plausibly belong to it (not an interpreter word, not a `-flag`).
    ambiguous: list[str] = []
    j = idx - 1
    while j >= 0 and tokens[j] not in _HOOK_INTERPRETERS and not tokens[j].startswith("-"):
        ambiguous.insert(0, tokens[j])
        j -= 1

    if not ambiguous:
        return ("missing", str(path))

    # Try progressive rejoins, fullest (most literal) first, in case only part
    # of the reconstructed run is genuinely the path (e.g. trailing tokens
    # were actually flags/args, not path fragments).
    for start in range(len(ambiguous)):
        joined = " ".join([*ambiguous[start:], candidate])
        joined_path = Path(os.path.expanduser(joined))
        if joined_path.is_file():
            return ("found", str(joined_path))

    # No rejoin combination resolved to a real file. The command string still
    # only admits one literal reading — every token between the interpreter
    # and the script suffix, in order — so report that full path as missing
    # rather than downgrade to unparseable on a segment we can fully parse.
    full_guess = " ".join([*ambiguous, candidate])
    return ("missing", full_guess)


def _extract_hook_script_path(command: str) -> tuple[str, str] | None:
    """Resolve the script path from a hook command string, tolerating quoted
    and unquoted space-containing paths and '&&'-compound commands (e.g.
    'source venv/bin/activate && python3 /path/hook.py'). See
    _extract_script_from_segment for the (status, path) contract."""
    expanded = os.path.expandvars(command)
    for segment in expanded.split("&&"):
        segment = segment.strip()
        if not segment:
            continue
        result = _extract_script_from_segment(segment)
        if result is not None:
            return result
    return None


def check_hooks_invocable(settings_path: Path | None = None) -> Check:
    """check_live_session proves the harness fires SOME SessionStart hook end to
    end; it does not say WHICH hook is broken when it doesn't, and it only exercises
    one event. This check complements it: walk every wired hook command across every
    event, and for each one that resolves to a script file, confirm the file exists
    and runs cleanly on a benign payload. A wiring entry pointing at a missing or
    renamed script, or a hook that crashes on minimal input, turns this RED with the
    specific hook named — the F10 gap 'config file exists != hook actually fires',
    one hook at a time rather than only in aggregate.

    Accepts settings_path for testability (defaults to the real ~/.claude/settings.json).
    """
    key, label = "hooks_invocable", "hooks invocable (per-hook liveness)"
    path = settings_path or (Path.home() / ".claude" / "settings.json")
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return skip(key, label, f"{path} unreadable — nothing to probe ({exc})")
    except ValueError as exc:
        return fail(key, label, f"{path} is not valid JSON — the entire hooks block is void ({exc})")

    registered = _iter_registered_hooks(settings)
    if not registered:
        return skip(key, label, "no hooks registered in settings.json — nothing to probe")

    dead: list[str] = []
    unparseable: list[str] = []
    checked = 0
    for event, command in registered:
        resolved = _extract_hook_script_path(command)
        if resolved is None:
            continue  # not a recognizable script invocation (e.g. inline shell) — not this check's job
        status, path_str = resolved
        if status == "unparseable":
            unparseable.append(f"{event}:{path_str}")
            continue
        script_path = Path(path_str).expanduser()
        checked += 1
        if status == "missing":
            dead.append(f"{event}:{script_path.name} (missing: {script_path})")
            continue
        try:
            cmd = [sys.executable, str(script_path)] if script_path.suffix == ".py" else ["sh", str(script_path)]
            result = subprocess.run(
                cmd, input="{}", capture_output=True, text=True, timeout=10,
            )
        except subprocess.TimeoutExpired:
            dead.append(f"{event}:{script_path.name} (timed out after 10s)")
            continue
        except OSError as exc:
            dead.append(f"{event}:{script_path.name} (could not invoke: {exc})")
            continue
        if result.returncode != 0:
            stderr_preview = result.stderr[:100].replace("\n", " ")
            dead.append(f"{event}:{script_path.name} (exit {result.returncode}: {stderr_preview})")

    unparseable_note = ""
    if unparseable:
        sample = "; ".join(unparseable[:3])
        more = f" (+{len(unparseable) - 3} more)" if len(unparseable) > 3 else ""
        unparseable_note = f"; {len(unparseable)} unparseable (not counted, named): {sample}{more}"

    if checked == 0 and not unparseable:
        return skip(key, label, "no file-based hook commands found to probe")
    if dead:
        sample = "; ".join(dead[:3])
        more = f" (+{len(dead) - 3} more)" if len(dead) > 3 else ""
        return fail(key, label, f"{len(dead)}/{checked} hook(s) dead: {sample}{more}{unparseable_note}")
    return ok(key, label,
              f"{checked} hook(s) invoked cleanly (exit 0) across {len(registered)} registration(s){unparseable_note}")


# ---------------------------------------------------------------------------
# Check 9 — situational corpus (work-order item 16)
# ---------------------------------------------------------------------------
def check_situational_corpus() -> list[Check]:
    """The same blind spot as Check 8, one plane up: a consumer can be correctly
    wired, firing on every edit, and matching nothing — forever — because its
    corpus is empty. Mechanism-only checks call that healthy. It is not; it is a
    working mechanism with nothing to say.

    Advisory by design: an empty corpus is a legitimate state on a fresh machine.
    These SKIP (never FAIL) so they read as 'known gap, located' rather than
    'broken' — the distinction that stops a silent partial being mistaken for
    completeness.
    """
    out: list[Check] = []
    root = Path(os.environ.get("SPOS_ROOT")
                or os.environ.get("CLAUDE_PROJECT_DIR")
                or (Path.home() / "SPOS"))

    # -- solutions corpus (consumer: pretooluse-solution-surface.py) ----------
    key, label = "corpus_solutions", "situational corpus — docs/solutions"
    sdir = Path(os.environ.get("AOS_CORE_SOLUTIONS_DIR") or (root / "docs" / "solutions"))
    if not sdir.is_dir():
        out.append(skip(key, label, f"no corpus at {sdir} — prior-fix surfacing will fire and match nothing"))
    else:
        n = sum(1 for _ in sdir.rglob("*.md"))
        if n == 0:
            out.append(skip(key, label, f"{sdir} exists but is empty — hook fires, matches nothing"))
        else:
            excl = sdir.parent / "SOLUTIONS-EXCLUDED.md"
            note = ""
            if excl.is_file():
                withheld = sum(1 for ln in excl.read_text(errors="ignore").splitlines() if ln.startswith("- `"))
                if withheld:
                    note = f"; {withheld} withheld (see {excl.name})"
            out.append(ok(key, label, f"{n} entr(y/ies) at {sdir}{note}"))

    # -- CLAUDE.md (consumer: Claude Code itself) ----------------------------
    key, label = "corpus_claude_md", "situational corpus — CLAUDE.md"
    cmd_path = root / "CLAUDE.md"
    if cmd_path.is_file():
        out.append(ok(key, label, f"present at {cmd_path} ({cmd_path.stat().st_size} bytes)"))
    else:
        out.append(skip(key, label, f"absent at {cmd_path} — no stable operating rules for this root"))

    # -- handoff series (consumer: session-close skill + Stop hook) ----------
    key, label = "corpus_handoffs", "situational corpus — session handoffs"
    hdir = Path(os.environ.get("AOS_CORE_HANDOFFS_DIR") or (root / "docs" / "session-handoffs"))
    if not hdir.is_dir():
        out.append(skip(key, label, f"no handoff series at {hdir} — no lane history"))
    else:
        n = sum(1 for _ in hdir.glob("*.md"))
        out.append(ok(key, label, f"{n} handoff(s) at {hdir}") if n
                   else skip(key, label, f"{hdir} exists but is empty"))

    return out


# ---------------------------------------------------------------------------
# Check 10 — discipline pack present + current
# ---------------------------------------------------------------------------
def _discipline_version(text: str) -> int | None:
    """Extract `<!-- discipline_version: N -->` from a doc's header. None if absent/malformed."""
    m = re.search(r"discipline_version:\s*(\d+)", text)
    return int(m.group(1)) if m else None


def check_discipline_pack() -> Check:
    """OPERATING-DISCIPLINE.md must ship with the plugin. Mirrors the Check 5
    (bundle vs drive) pattern: presence is the hard requirement (FAIL if absent);
    freshness vs a reachable drive mirror is best-effort (SKIP, never FAIL, when
    the mirror isn't reachable — an unprobeable comparison is not a broken one)."""
    key, label = "discipline_pack", "operating discipline pack"
    doc_path = PLUGIN_ROOT / "OPERATING-DISCIPLINE.md"

    if not doc_path.is_file():
        return fail(key, label, f"missing: {doc_path}")

    try:
        local_text = doc_path.read_text(encoding="utf-8")
    except OSError as exc:
        return fail(key, label, f"present but unreadable: {exc}")

    local_version = _discipline_version(local_text)
    if local_version is None:
        return fail(key, label, f"present at {doc_path} but missing/malformed `discipline_version` header")

    drive_dir_str = os.environ.get("AOS_CORE_DRIVE_DIR", "")
    if not drive_dir_str:
        return ok(key, label, f"present at {doc_path} (discipline_version={local_version}); "
                                "AOS_CORE_DRIVE_DIR not set — freshness vs mirror not probed")

    drive_dir = Path(drive_dir_str)
    if not drive_dir.is_dir():
        return ok(key, label, f"present at {doc_path} (discipline_version={local_version}); "
                                f"AOS_CORE_DRIVE_DIR set but not reachable: {drive_dir} — freshness not probed")

    mirror_path = drive_dir / "OPERATING-DISCIPLINE.md"
    if not mirror_path.is_file():
        return ok(key, label, f"present at {doc_path} (discipline_version={local_version}); "
                                f"no mirror copy found at {mirror_path} to compare against")

    try:
        mirror_text = mirror_path.read_text(encoding="utf-8")
    except OSError:
        return ok(key, label, f"present at {doc_path} (discipline_version={local_version}); "
                                f"mirror at {mirror_path} unreadable — freshness not probed")

    mirror_version = _discipline_version(mirror_text)
    if mirror_version is None:
        return ok(key, label, f"present at {doc_path} (discipline_version={local_version}); "
                                f"mirror at {mirror_path} has no discipline_version header — treating local as current")

    if mirror_version > local_version:
        return fail(key, label, f"stale — installed discipline_version={local_version}, "
                                  f"mirror at {mirror_path} has discipline_version={mirror_version}")

    return ok(key, label, f"current — installed discipline_version={local_version} "
                            f"(mirror at {mirror_path}: {mirror_version})")


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------
_STATUS_WIDTH = 4  # PASS/FAIL/SKIP


def render_table(checks: list[Check]) -> str:
    """Aligned PASS/FAIL/SKIP table."""
    max_label = max((len(c.label) for c in checks), default=20)
    lines = []
    for c in checks:
        lines.append(f"  {c.status:<{_STATUS_WIDTH}}  {c.label:<{max_label}}  {c.reason}")
    return "\n".join(lines)


def render_summary(checks: list[Check]) -> str:
    passes = sum(1 for c in checks if c.status == PASS)
    fails = sum(1 for c in checks if c.status == FAIL)
    skips = sum(1 for c in checks if c.status == SKIP)
    verdict = "GREEN" if fails == 0 else "RED"
    return f"{verdict} — {passes} PASS  {fails} FAIL  {skips} SKIP"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run_all_checks(live: bool = False) -> list[Check]:
    checks: list[Check] = []
    checks.extend(check_tooling_binaries())  # 1
    checks.append(check_hooks_registered())  # 2
    checks.append(check_hooks_fire())  # 3
    checks.extend(check_identity_bundle())  # 4
    checks.append(check_bundle_version())  # 5
    checks.extend(check_tooling_leg(live=live))  # 6
    checks.extend(check_import_compat())  # 7
    checks.append(check_live_session())  # 8  (F10)
    checks.append(check_hooks_invocable())  # 8b (F10)
    checks.extend(check_situational_corpus())  # 9 (item 16)
    checks.append(check_discipline_pack())  # 10
    return checks


def main() -> int:
    ap = argparse.ArgumentParser(description="aos-core doctor — health check for the three-legged stool")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of the human table")
    ap.add_argument(
        "--live",
        action="store_true",
        help="use the deeper `claude mcp list` subprocess probe for MCP registration "
        "instead of the default instant on-disk config read",
    )
    args = ap.parse_args()

    checks = run_all_checks(live=args.live)
    fails = [c for c in checks if c.status == FAIL]

    if args.json:
        out = {
            "summary": render_summary(checks),
            "exit_code": 1 if fails else 0,
            "checks": [c.as_dict() for c in checks],
        }
        print(json.dumps(out, indent=2))  # c1-ok
    else:
        print(f"\naos-core doctor  (plugin root: {PLUGIN_ROOT})\n")  # c1-ok
        print(render_table(checks))  # c1-ok
        print()  # c1-ok
        print(render_summary(checks))  # c1-ok
        print()  # c1-ok

    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
