#!/usr/bin/env python3
"""AOS Blackboard — shared state for multi-agent team communication.

File-based JSON store with fcntl locking for concurrent agent access.
Lives outside git repo at ~/.claude/blackboard/ so worktree-isolated
agents can access it.

Usage:
    from blackboard import Blackboard

    bb = Blackboard("mission-feature-x")
    bb.write_entry(agent_name="researcher", entry_type="finding",
                   key="existing-patterns", value={"files": [...]})

    entries = bb.read()
    findings = bb.query(entry_type="finding")
    latest = bb.query(agent_name="architect")

Implementation validated by:
- Anthropic's 16-agent C compiler project (file locking at scale)
- claude-fleet (TypeScript/SQLite blackboard with typed messages)
- agent-blackboard (Python with domain-partitioned persistence)
"""

import fcntl
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Blackboard lives INSIDE the repo so sandboxed sub-agents can write to it.
# Previously at ~/.claude/blackboard/ but sandbox blocked writes there.
# Store resolution (aos-core port): env override -> project root -> cwd.
# CLAUDE_PROJECT_DIR is the real project root even in worktrees/subdirs; cwd drifts.
import os as _os
BLACKBOARD_DIR = Path(
    _os.environ.get("AOS_CORE_BLACKBOARD_DIR")
    or Path(_os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd()) / ".blackboard"
)


class Blackboard:
    """Shared state store for a team mission.

    Each mission gets a JSON file. Agents append entries. File locking
    prevents corruption from concurrent worktree agents.
    """

    def __init__(self, mission_id: str):
        # Sanitize mission_id: alphanumeric, hyphens, underscores only
        import re
        sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", mission_id)
        if not sanitized:
            sanitized = "default"
        self.mission_id = sanitized
        self.path = BLACKBOARD_DIR / f"{sanitized}.json"
        self.lock_path = BLACKBOARD_DIR / f"{sanitized}.lock"
        BLACKBOARD_DIR.mkdir(parents=True, exist_ok=True)

    def _acquire_lock(self) -> Any:
        """Acquire file lock for concurrent access safety."""
        lock_file = open(self.lock_path, "w")
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        return lock_file

    def _release_lock(self, lock_file: Any) -> None:
        """Release file lock."""
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()

    def _read_raw(self) -> dict:
        """Read the blackboard file without locking (caller must hold lock or accept stale read)."""
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except (json.JSONDecodeError, OSError) as e:
                import logging
                logging.getLogger(__name__).warning(
                    "Blackboard %s corrupted, resetting: %s", self.mission_id, e
                )
                return self._new_board()
        return self._new_board()

    def _new_board(self, metadata: dict | None = None) -> dict:
        """Create empty blackboard structure."""
        return {
            "mission_id": self.mission_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "active",
            "metadata": metadata or {"phase": "A", "task_ids": [], "description": ""},
            "entries": [],
        }

    def transition(self, phase: str, dispatcher: str = "dispatcher") -> None:
        """Advance mission phase. Writes a status entry. Dispatcher-only."""
        valid = {"A", "B", "C", "D", "E", "F"}
        if phase not in valid:
            raise ValueError(f"Invalid phase {phase!r}. Must be one of {valid}")
        lock = self._acquire_lock()
        try:
            data = self._read_raw()
            old_phase = data.get("metadata", {}).get("phase", "?")
            if "metadata" not in data:
                data["metadata"] = {}
            data["metadata"]["phase"] = phase
            # Append a status entry recording the transition
            data["entries"].append({
                "id": str(uuid.uuid4())[:8],
                "agent_name": dispatcher,
                "entry_type": "status",
                "key": "phase-transition",
                "value": {"from": old_phase, "to": phase},
                "confidence": 1.0,
                "open_loops": [],
                "priority": 5,
                "read_by": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tags": ["phase-transition"],
            })
            self._write_raw(data)
        finally:
            self._release_lock(lock)

    def _write_raw(self, data: dict) -> None:
        """Write the blackboard file atomically (caller must hold lock).

        Uses write-to-temp-then-rename pattern. rename() is atomic on POSIX,
        so a crash mid-write leaves either the old file or the new file,
        never a partial/corrupted file.
        """
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.rename(self.path)  # atomic on POSIX

    def read(self) -> dict:
        """Read the full blackboard. Safe for concurrent reads."""
        return self._read_raw()

    def write_entry(
        self,
        agent_name: str,
        entry_type: str,
        key: str,
        value: Any,
        confidence: float = 1.0,
        open_loops: list[str] | None = None,
        priority: int = 0,
        ttl_seconds: int | None = None,
    ) -> str:
        """Append an entry to the blackboard. Thread/process safe via file lock.

        Args:
            agent_name: Which agent is writing (e.g., "researcher", "architect")
            entry_type: Category — "decision", "artifact", "finding", "warning", "status"
            key: What this entry is about (e.g., "auth-module-approach")
            value: The actual data (any JSON-serializable value)
            confidence: Agent's confidence in this entry (0.0-1.0)
            open_loops: Unresolved items the next agent should address
            priority: Higher = more important. Warnings/blockers should be high. (from claude-fleet)
            ttl_seconds: Auto-expire after N seconds. None = never expire. (from claude-fleet)

        Returns:
            The entry's unique ID.
        """
        entry_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc)
        entry: dict[str, Any] = {
            "id": entry_id,
            "agent_name": agent_name,
            "entry_type": entry_type,
            "key": key,
            "value": value,
            "confidence": confidence,
            "open_loops": open_loops or [],
            "priority": priority,
            "read_by": [],
            "timestamp": now.isoformat(),
        }
        if ttl_seconds is not None:
            from datetime import timedelta
            entry["expires_at"] = (now + timedelta(seconds=ttl_seconds)).isoformat()

        lock = self._acquire_lock()
        try:
            data = self._read_raw()
            data["entries"].append(entry)
            self._write_raw(data)
        finally:
            self._release_lock(lock)

        return entry_id

    def query(
        self,
        entry_type: str | None = None,
        agent_name: str | None = None,
        key: str | None = None,
    ) -> list[dict]:
        """Query entries by type, agent, or key. Returns matching entries sorted by priority."""
        data = self._read_raw()
        results = self._filter_expired(data.get("entries", []))

        if entry_type:
            results = [e for e in results if e.get("entry_type") == entry_type]
        if agent_name:
            results = [e for e in results if e.get("agent_name") == agent_name]
        if key:
            results = [e for e in results if e.get("key") == key]

        # Sort by priority (highest first), then timestamp (newest first)
        results.sort(key=lambda e: (-e.get("priority", 0), e.get("timestamp", "")),
                     reverse=False)
        # reverse=False because priority is negated, so higher priority comes first
        # For same priority, newer timestamps sort later in natural order which is what we want
        # Actually let's just sort properly:
        results.sort(key=lambda e: (-e.get("priority", 0), e.get("timestamp", "")))

        return results

    def get_latest(self, key: str) -> dict | None:
        """Get the most recent entry for a given key."""
        matches = self.query(key=key)
        return matches[-1] if matches else None

    def get_open_loops(self) -> list[str]:
        """Collect all unresolved open loops across all entries."""
        data = self._read_raw()
        loops: list[str] = []
        for entry in self._filter_expired(data.get("entries", [])):
            loops.extend(entry.get("open_loops", []))
        return loops

    def mark_read(self, entry_id: str, agent_name: str) -> None:
        """Mark an entry as read by an agent. (Pattern from claude-fleet.)"""
        lock = self._acquire_lock()
        try:
            data = self._read_raw()
            for entry in data.get("entries", []):
                if entry.get("id") == entry_id:
                    read_by = entry.get("read_by", [])
                    if agent_name not in read_by:
                        read_by.append(agent_name)
                        entry["read_by"] = read_by
                    break
            self._write_raw(data)
        finally:
            self._release_lock(lock)

    def get_unread(self, agent_name: str) -> list[dict]:
        """Get entries not yet read by this agent. (Pattern from claude-fleet.)"""
        data = self._read_raw()
        entries = self._filter_expired(data.get("entries", []))
        return [e for e in entries if agent_name not in e.get("read_by", [])]

    def clear_expired(self) -> int:
        """Remove entries past their TTL. Returns count removed. (Pattern from claude-fleet.)"""
        lock = self._acquire_lock()
        try:
            data = self._read_raw()
            original = len(data.get("entries", []))
            data["entries"] = self._filter_expired(data.get("entries", []))
            removed = original - len(data["entries"])
            if removed > 0:
                self._write_raw(data)
            return removed
        finally:
            self._release_lock(lock)

    @staticmethod
    def _filter_expired(entries: list[dict]) -> list[dict]:
        """Remove expired entries from a list."""
        now = datetime.now(timezone.utc).isoformat()
        return [e for e in entries if not e.get("expires_at") or e["expires_at"] > now]

    def summary(self) -> str:
        """Human-readable summary of blackboard state."""
        data = self._read_raw()
        entries = data.get("entries", [])
        agents = set(e.get("agent_name", "?") for e in entries)
        types: dict[str, int] = {}
        for e in entries:
            t = e.get("entry_type", "?")
            types[t] = types.get(t, 0) + 1

        lines = [
            f"Mission: {self.mission_id}",
            f"Entries: {len(entries)}",
            f"Agents: {', '.join(sorted(agents))}",
            f"Types: {', '.join(f'{k}={v}' for k, v in sorted(types.items()))}",
        ]

        loops = self.get_open_loops()
        if loops:
            lines.append(f"Open loops: {len(loops)}")
            for loop in loops[:5]:
                lines.append(f"  - {loop}")

        return "\n".join(lines)

    def clear(self) -> None:
        """Clear the blackboard (start fresh)."""
        lock = self._acquire_lock()
        try:
            self._write_raw(self._new_board())
        finally:
            self._release_lock(lock)

    @staticmethod
    def list_missions() -> list[str]:
        """List all active mission blackboards."""
        if not BLACKBOARD_DIR.exists():
            return []
        return [
            f.stem for f in BLACKBOARD_DIR.glob("*.json")
            if not f.name.endswith(".lock")
        ]
