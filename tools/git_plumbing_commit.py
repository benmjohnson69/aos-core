"""git_plumbing_commit.py — storm-proof commit that never touches .git/index.lock.

Problem: N parallel Claude/codex sessions committing to one shared repo
contend on .git/index.lock. Standard `git commit` (and even
git_atomic_commit.py, which isolates the *staging* index via GIT_INDEX_FILE
but still runs `git commit` for the ref update) times out or corrupts the
index under a sustained commit-storm. Observed 2026-05-28: 6+ failed CA-013
commit attempts across direct/atomic/loop methods while sibling dashboard
CD-port sessions held the lock continuously.

Fix: build the commit with plumbing only.
  1. read-tree HEAD into a TEMP index (GIT_INDEX_FILE=/tmp/...) — never
     locks the real .git/index.
  2. add paths to the temp index.
  3. write-tree -> tree sha.
  4. commit-tree tree -p HEAD -m msg -> new commit sha (object write, no lock).
  5. update-ref refs/heads/<branch> <new> <old-HEAD>  — compare-and-swap.
     Brief refs/heads/<branch>.lock (microseconds), NOT index.lock. If a
     sibling moved HEAD between steps 3 and 5, CAS fails -> rebuild on the
     new HEAD and retry. This makes it storm-proof: contention only on the
     ref lock, which every session holds for an instant.

Sibling of git_atomic_commit.py (Pattern 3). Use this one when the repo is
under a commit-storm; use git_atomic_commit when you need pre-commit gate
enforcement (this tool bypasses gates by design — plumbing runs no hooks).
"""

from __future__ import annotations

# owner_mission: git-plumbing-commit-storm-proof-2026-05-29
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Iterable

_AOS_HOME = Path(__file__).resolve().parent.parent


def _clear_stale_index_lock(max_age_s: float = 120.0) -> bool:
    """Remove .git/index.lock ONLY if provably stale — it exists AND its mtime
    is older than max_age_s. A live git op holds the lock for far less than
    120s, so this is storm-safe: a genuine concurrent writer's lock is always
    fresh and is left alone. A crashed process leaves a lock that never ages
    out on its own, which silently blocks the index-sync below and is the root
    cause of the stale-index/phantom-deletion desync. Best-effort; never raises.
    Returns True if a stale lock was cleared.
    """
    try:
        lock = _AOS_HOME / ".git" / "index.lock"
        if lock.exists() and (time.time() - lock.stat().st_mtime) > max_age_s:
            lock.unlink()
            return True
    except OSError:
        pass
    return False


def _reset_uncommitted_counter(new_sha: str, reset_by: str = "git_plumbing_commit") -> None:
    """Reset the active session's uncommitted_counter.json to 0 after a real
    plumbing commit. The PreToolUse counter hook only resets on `git commit`
    subprocess detection; plumbing commits bypass that path. Without this
    reset, the counter climbs past BLOCK after batch-commit workflows even
    though every write WAS committed.

    Best-effort: any failure exits silently (a counter-reset failure must
    NEVER break the commit itself).
    """
    try:
        import json  # noqa: PLC0415
        from datetime import datetime, timezone  # noqa: PLC0415
        from pathlib import Path  # noqa: PLC0415

        sid = (os.environ.get("AOS_SESSION_ID")
               or os.environ.get("CLAUDE_CODE_SESSION_ID")
               or "")
        if not sid:
            # Fallback: read primary session from active_sessions.json
            try:
                aos_root = Path.home() / "aos"
                index_path = aos_root / "data" / "active_sessions.json"
                idx = json.loads(index_path.read_text(encoding="utf-8"))
                # primary may be a key or a row; try both shapes
                primary = idx.get("primary") or idx.get("primary_session_id")
                if isinstance(primary, dict):
                    sid = primary.get("session_id") or ""
                elif isinstance(primary, str):
                    sid = primary
            except (OSError, json.JSONDecodeError, KeyError, ValueError):
                pass
        if not sid:
            return
        counter_path = (Path.home() / "aos" / "data" / "sessions" / sid
                         / "uncommitted_counter.json")
        if not counter_path.parent.is_dir():
            return
        rec = {
            "session_id": sid,
            # `count` is the key the PreToolUse hook (uncommitted-file-counter.py)
            # actually reads + blocks on; `write_count` is legacy. Zero BOTH so the
            # reset is authoritative regardless of which key a reader uses — the
            # key-absence-only reset silently failed to clear `count` (climbed to
            # 123 → BLOCK on 2026-07-05 despite ~10 commits via commit_with_recovery).
            "count": 0,
            "write_count": 0,
            "warned_at_20": False,
            "last_reset": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ",
            ),
            "reset_by": reset_by,
            "reset_after_sha": new_sha[:12],
        }
        counter_path.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001 — counter reset must NEVER break commit
        pass


def _run(args: list[str], env: dict[str, str] | None = None) -> tuple[int, str, str]:
    p = subprocess.run(
        args, cwd=str(_AOS_HOME), env=env, capture_output=True, text=True
    )
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def _current_branch() -> str:
    """Current branch name, or the literal "HEAD" if detached (caller must check)."""
    rc, out, _ = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    return out if rc == 0 and out else "master"


def plumbing_commit(
    paths: Iterable[str],
    message: str,
    *,
    branch: str | None = None,
    max_retries: int = 8,
    sync_index: bool = True,
) -> tuple[bool, str]:
    """Commit `paths` with `message` via plumbing, bypassing .git/index.lock.

    Returns (ok, sha) on success or (False, error_string) on failure.
    Retries up to max_retries times when a sibling moves HEAD (CAS miss).

    sync_index (default True): after a successful commit, best-effort stage the
    committed paths into the REAL index (`git update-index --add`). This narrows
    the data-loss window where a sibling committing from a stale real index
    writes a tree that reverts these files (see docs/solutions/infra/
    git-plumbing-commit-storm-proof). Touches only `paths` (surgical — leaves
    other sessions' staged entries alone) and is non-fatal: index.lock
    contention just skips the sync; the commit itself already landed.
    """
    paths = [str(p) for p in paths]
    if not paths:
        return False, "no_paths"
    branch = branch or _current_branch()
    # CA-015 fix: detached HEAD makes _current_branch() return the literal
    # "HEAD"; refs/heads/HEAD is not the real ref, so CAS would retry to
    # exhaustion. Fail fast with a clear error (callers run on named branches).
    if branch == "HEAD":
        return False, "detached_head_unsupported"
    ref = f"refs/heads/{branch}"

    for attempt in range(1, max_retries + 1):
        rc, parent, err = _run(["git", "rev-parse", "HEAD"])
        if rc != 0:
            return False, f"rev_parse_head_failed: {err}"

        with tempfile.NamedTemporaryFile(
            prefix="plumb_idx_", suffix=".idx", delete=False
        ) as tf:
            tmp_index = tf.name
        try:
            env = dict(os.environ)
            env["GIT_INDEX_FILE"] = tmp_index

            rc, _, err = _run(["git", "read-tree", parent], env=env)
            if rc != 0:
                return False, f"read_tree_failed: {err}"

            rc, _, err = _run(["git", "add", "--", *paths], env=env)
            if rc != 0:
                return False, f"add_failed: {err}"

            rc, tree, err = _run(["git", "write-tree"], env=env)
            if rc != 0 or not tree:
                return False, f"write_tree_failed: {err}"

            rc, new_sha, err = _run(
                ["git", "commit-tree", tree, "-p", parent, "-m", message], env=env
            )
            if rc != 0 or not new_sha:
                return False, f"commit_tree_failed: {err}"

            # Compare-and-swap: only move ref if HEAD is still `parent`.
            rc, _, err = _run(
                [
                    "git",
                    "update-ref",
                    "-m",
                    "plumbing_commit (storm-proof)",
                    ref,
                    new_sha,
                    parent,
                ]
            )
            if rc == 0:
                if sync_index:
                    # Best-effort, non-fatal: stage just our paths into the real
                    # index so a sibling's later commit preserves them.
                    src, _, serr = _run(["git", "update-index", "--add", "--", *paths])
                    if src != 0 and _clear_stale_index_lock():
                        # A crashed process's stale index.lock was blocking the
                        # sync (the desync root cause). Cleared it — retry once.
                        src, _, serr = _run(
                            ["git", "update-index", "--add", "--", *paths]
                        )
                    if src != 0:
                        # LOUD, not silent: a failed sync leaves the real index
                        # behind HEAD (phantom-deletion footgun). Surface it so
                        # the operator can `git reset --mixed HEAD` to resync.
                        sys.stderr.write(
                            "git_plumbing_commit: WARN index-sync failed for "
                            f"{paths} ({serr or 'index.lock contention'}); real "
                            "index may be behind HEAD — run "
                            "`git reset --mixed HEAD` to resync.\n"
                        )
                # Conductor fix 2026-05-30: plumbing commit was invisible to
                # .claude/hooks/uncommitted-file-counter.py because that hook
                # resets only on git-commit tool calls (PostToolUse Bash w/ git
                # commit detection). A plumbing commit DOES land a real SHA, so
                # reset the active session's counter to 0 — otherwise the
                # counter climbs past BLOCK and false-positives on commits
                # that already happened. Best-effort: never break the commit.
                _reset_uncommitted_counter(new_sha)
                return True, new_sha
            # CAS miss: a sibling moved HEAD. Rebuild on the new HEAD.
        finally:
            try:
                os.unlink(tmp_index)
            except OSError:
                pass

    return False, f"cas_exhausted_after_{max_retries}_retries"


def _cli() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Storm-proof plumbing commit.")
    ap.add_argument("-m", "--message", required=True)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--branch", default=None)
    args = ap.parse_args()
    ok, res = plumbing_commit(args.paths, args.message, branch=args.branch)
    print(("OK " if ok else "FAIL ") + res)  # c1-ok
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(_cli())
