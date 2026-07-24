#!/usr/bin/env python3
"""aos-core doctor — answers "is the whole stool green?"

Checks seven concern areas and reports PASS / FAIL / SKIP for each.
Exit 0 iff no FAILs. --json emits machine-readable JSON.

Usage:
    python3 doctor.py
    python3 doctor.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants / defaults
# ---------------------------------------------------------------------------
PLUGIN_ROOT = Path(__file__).resolve().parent.parent

# Private layer (overridable via env)
PRIVATE_DIR = Path(os.environ.get("AOS_PRIVATE_DIR", str(Path.home() / ".aos-private")))

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
def check_tooling_leg() -> list[Check]:
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
    results.append(_check_webfetch_mcp())
    return results


def _check_webfetch_mcp() -> Check:
    label = "webfetch MCP registered"
    key = "tooling_webfetch"
    claude_bin = shutil.which("claude")
    if not claude_bin:
        return skip(key, label, "claude CLI not on PATH — cannot check MCP list")
    try:
        result = subprocess.run(
            [claude_bin, "mcp", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = result.stdout + result.stderr
        if re.search(r"\bwebfetch\b", output, re.IGNORECASE):
            return ok(key, label, "webfetch found in `claude mcp list`")
        else:
            return fail(key, label, "webfetch NOT found in `claude mcp list`")
    except subprocess.TimeoutExpired:
        return skip(key, label, "claude mcp list timed out after 10s")
    except OSError as exc:
        return skip(key, label, f"could not invoke claude CLI: {exc}")


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
def run_all_checks() -> list[Check]:
    checks: list[Check] = []
    checks.extend(check_tooling_binaries())  # 1
    checks.append(check_hooks_registered())  # 2
    checks.append(check_hooks_fire())  # 3
    checks.extend(check_identity_bundle())  # 4
    checks.append(check_bundle_version())  # 5
    checks.extend(check_tooling_leg())  # 6
    return checks


def main() -> int:
    ap = argparse.ArgumentParser(description="aos-core doctor — health check for the three-legged stool")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of the human table")
    args = ap.parse_args()

    checks = run_all_checks()
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
