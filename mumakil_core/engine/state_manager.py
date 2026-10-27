"""Thread-safe In-Memory & SQLite State Manager for Mumakil 2.0.

Eliminates legacy Concurrency Hazards (Finding #4) where raw un-locked JSON files
were written simultaneously in storage/last_inserts/*.json.

Features:
- Fine-grained asyncio.Lock per action to prevent race conditions
- Primary key extraction for duplicate insert detection (AC03, AC04, AC12)
- Optional SQLite persistence with WAL mode for fast, ACID-compliant persistence
- Atomic file serialization fallback for legacy tooling compatibility
"""

import asyncio
from datetime import datetime
import json
import logging
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

from mumakil_core.config import Settings, get_settings

logger = logging.getLogger("mumakil.state_manager")


class StateManager:
    """Thread-safe state manager for tracking insert records and preventing race conditions."""

    # Primary key group as defined in legacy qc_engine.php
    PRIMARY_GROUP: List[str] = [
        "nip",
        "nama",
        "kodejabatan",
        "rek_bank",
        "rek_nomor",
        "rek_kdbank",
        "KDBANK",
        "NAMABANK",
    ]

    def __init__(self, settings: Optional[Settings] = None, use_sqlite: bool = True):
        self.settings = settings or get_settings()
        self.use_sqlite = use_sqlite

        # In-memory storage: action -> primary subset dictionary
        self._memory_store: Dict[str, Dict[str, Optional[str]]] = {}

        # Granular locks per action to maximize concurrency throughput
        self._action_locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

        # Database initialization
        self.db_path = self.settings.sqlite_db_path
        if self.use_sqlite:
            self._init_sqlite()

    def _init_sqlite(self) -> None:
        """Initialize SQLite database with WAL mode and schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS last_inserts (
                    action TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            conn.commit()

    async def _get_lock(self, action: str) -> asyncio.Lock:
        """Retrieve or create an asyncio.Lock for a specific action key."""
        async with self._global_lock:
            if action not in self._action_locks:
                self._action_locks[action] = asyncio.Lock()
            return self._action_locks[action]

    def extract_primary_subset(self, candidate: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """Extract canonical primary fields for duplicate comparison."""
        subset: Dict[str, Optional[str]] = {}
        # Case-insensitive mapping lookup
        lower_keys = {k.lower(): k for k in candidate.keys()}

        for field in self.PRIMARY_GROUP:
            val = None
            if field in candidate:
                val = candidate[field]
            elif field.lower() in lower_keys:
                orig_key = lower_keys[field.lower()]
                val = candidate[orig_key]

            subset[field] = str(val) if val is not None else None

        return subset

    def is_primary_identical(
        self,
        candidate_subset: Dict[str, Optional[str]],
        existing_subset: Dict[str, Optional[str]],
    ) -> bool:
        """Compare two primary subsets for equality across non-null keys."""
        # Must match all defined fields
        for field in self.PRIMARY_GROUP:
            val_a = candidate_subset.get(field) or ""
            val_b = existing_subset.get(field) or ""
            if val_a != val_b:
                return False
        return True

    async def record_insert(self, action: str, candidate_data: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """Atomically record an insert entity into in-memory store and SQLite."""
        lock = await self._get_lock(action)
        async with lock:
            subset = self.extract_primary_subset(candidate_data)
            self._memory_store[action] = subset

            # Persist to SQLite
            if self.use_sqlite:
                now_str = datetime.now().isoformat()
                serialized = json.dumps(subset)
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        INSERT INTO last_inserts (action, payload_json, updated_at)
                        VALUES (?, ?, ?)
                        ON CONFLICT(action) DO UPDATE SET
                            payload_json = excluded.payload_json,
                            updated_at = excluded.updated_at;
                    """, (action, serialized, now_str))
                    conn.commit()

            # Atomic legacy file sync for compatibility
            self._write_legacy_file(action, subset)
            return subset

    async def is_duplicate_insert(self, action: str, candidate_data: Dict[str, Any]) -> bool:
        """Atomically verify if the candidate insert is identical to the last recorded insert."""
        lock = await self._get_lock(action)
        async with lock:
            last_record = await self._get_last_insert_unlocked(action)
            if not last_record:
                return False

            candidate_subset = self.extract_primary_subset(candidate_data)
            return self.is_primary_identical(candidate_subset, last_record)

    async def get_last_insert(self, action: str) -> Optional[Dict[str, Optional[str]]]:
        """Thread-safe retrieval of last recorded insert for an action."""
        lock = await self._get_lock(action)
        async with lock:
            return await self._get_last_insert_unlocked(action)

    async def _get_last_insert_unlocked(self, action: str) -> Optional[Dict[str, Optional[str]]]:
        """Internal unlocked lookup from memory, SQLite, or file."""
        if action in self._memory_store:
            return self._memory_store[action]

        if self.use_sqlite:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT payload_json FROM last_inserts WHERE action = ?", (action,))
                row = cursor.fetchone()
                if row:
                    data = json.loads(row[0])
                    self._memory_store[action] = data
                    return data

        # Check legacy file if exists
        legacy_data = self._read_legacy_file(action)
        if legacy_data:
            self._memory_store[action] = legacy_data
            return legacy_data

        return None

    def _write_legacy_file(self, action: str, data: Dict[str, Optional[str]]) -> None:
        """Atomic write to legacy storage/last_inserts/<action>.json via temporary file."""
        try:
            legacy_dir = self.settings.storage_dir / "last_inserts"
            legacy_dir.mkdir(parents=True, exist_ok=True)
            safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in action)
            target_path = legacy_dir / f"{safe_name}.json"
            temp_path = legacy_dir / f"{safe_name}.tmp"

            content = json.dumps(data, indent=4, ensure_ascii=False)
            temp_path.write_text(content, encoding="utf-8")
            temp_path.replace(target_path)
        except Exception as e:
            logger.warning("Could not write legacy last_insert file for %s: %s", action, e)

    def _read_legacy_file(self, action: str) -> Optional[Dict[str, Optional[str]]]:
        """Read legacy JSON file if present."""
        try:
            legacy_dir = self.settings.storage_dir / "last_inserts"
            safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in action)
            target_path = legacy_dir / f"{safe_name}.json"
            if target_path.is_file():
                return json.loads(target_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return None

    async def clear(self, action: Optional[str] = None) -> None:
        """Clear state for a single action or all actions."""
        async with self._global_lock:
            if action:
                self._memory_store.pop(action, None)
                if self.use_sqlite:
                    with sqlite3.connect(self.db_path) as conn:
                        conn.execute("DELETE FROM last_inserts WHERE action = ?", (action,))
                        conn.commit()
                legacy_file = self.settings.storage_dir / "last_inserts" / f"{action}.json"
                if legacy_file.is_file():
                    try:
                        legacy_file.unlink()
                    except Exception:
                        pass
            else:
                self._memory_store.clear()
                if self.use_sqlite:
                    with sqlite3.connect(self.db_path) as conn:
                        conn.execute("DELETE FROM last_inserts;")
                        conn.commit()
                legacy_dir = self.settings.storage_dir / "last_inserts"
                if legacy_dir.is_dir():
                    for f in legacy_dir.glob("*.json"):
                        try:
                            f.unlink()
                        except Exception:
                            pass


_global_state_manager: Optional[StateManager] = None


def get_state_manager() -> StateManager:
    """Singleton provider for the StateManager."""
    global _global_state_manager
    if _global_state_manager is None:
        _global_state_manager = StateManager()
    return _global_state_manager
