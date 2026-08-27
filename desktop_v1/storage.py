"""Durable local storage for MNLT Derby Manager v43 Desktop."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

APP_NAME = "MNLT Derby Manager"
SCHEMA_VERSION = 1


def default_data_dir() -> Path:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "MNLT Derby Manager"


def fresh_state() -> dict[str, Any]:
    return {
        "schema": SCHEMA_VERSION,
        "raceType": "Traditional",
        "registrations": [],
        "racers": [],
        "heats": [],
        "current": 0,
        "tieBreaks": {},
        "runoff": None,
        "modified": {
            "racers": [],
            "raceRacers": [],
            "heats": [],
            "current": 0,
            "tieBreaks": {},
            "runoff": None,
            "exhibition": {"active": False},
        },
        "updatedAt": int(time.time() * 1000),
    }


def ensure_state(state: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(state, dict):
        state = fresh_state()
    state.setdefault("schema", SCHEMA_VERSION)
    state.setdefault("raceType", "Traditional")
    for key in ("registrations", "racers", "heats"):
        if not isinstance(state.get(key), list):
            state[key] = []
    state.setdefault("current", 0)
    if not isinstance(state.get("tieBreaks"), dict):
        state["tieBreaks"] = {}
    state.setdefault("runoff", None)
    modified = state.setdefault("modified", {})
    if not isinstance(modified, dict):
        modified = state["modified"] = {}
    for key in ("racers", "raceRacers", "heats"):
        if not isinstance(modified.get(key), list):
            modified[key] = []
    modified.setdefault("current", 0)
    if not isinstance(modified.get("tieBreaks"), dict):
        modified["tieBreaks"] = {}
    modified.setdefault("runoff", None)
    modified.setdefault("exhibition", {"active": False})
    for reg in state["registrations"]:
        reg.setdefault("status", "Registered")
        reg.setdefault("tradCheckIn", "waiting")
        reg.setdefault("modCheckIn", "waiting")
    return state


class DerbyStore:
    """SQLite-backed state store.

    SQLite runs in WAL mode with synchronous=FULL. Each state save is an
    explicit transaction. A rolling snapshot table provides undo/recovery.
    Photos live as real files under data_dir/photos and are therefore not
    coupled to browser storage or the executable.
    """

    def __init__(self, data_dir: Path | str | None = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else default_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.photos_dir = self.data_dir / "Photos"
        self.photos_dir.mkdir(exist_ok=True)
        self.backups_dir = self.data_dir / "Backups"
        self.backups_dir.mkdir(exist_ok=True)
        self.db_path = self.data_dir / "derby.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=FULL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_state (
                    id INTEGER PRIMARY KEY CHECK(id=1),
                    json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reason TEXT NOT NULL,
                    json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            self.conn.execute(
                "INSERT OR IGNORE INTO app_state(id,json) VALUES(1,?)",
                (json.dumps(fresh_state(), separators=(",", ":")),),
            )

    def close(self) -> None:
        self.conn.close()

    def load_state(self) -> dict[str, Any]:
        row = self.conn.execute("SELECT json FROM app_state WHERE id=1").fetchone()
        if not row:
            return fresh_state()
        try:
            return ensure_state(json.loads(row["json"]))
        except Exception:
            latest = self.latest_snapshot()
            if latest:
                return ensure_state(latest["state"])
            return fresh_state()

    def save_state(self, state: dict[str, Any], reason: str = "autosave", snapshot: bool = True) -> None:
        state = ensure_state(state)
        state["updatedAt"] = int(time.time() * 1000)
        payload = json.dumps(state, separators=(",", ":"), ensure_ascii=False)
        with self.conn:
            if snapshot:
                current = self.conn.execute("SELECT json FROM app_state WHERE id=1").fetchone()
                if current:
                    self.conn.execute("INSERT INTO snapshots(reason,json) VALUES(?,?)", (reason, current["json"]))
            self.conn.execute("UPDATE app_state SET json=?, updated_at=CURRENT_TIMESTAMP WHERE id=1", (payload,))
        self.prune_snapshots(50)

    def prune_snapshots(self, keep: int = 50) -> None:
        with self.conn:
            self.conn.execute(
                "DELETE FROM snapshots WHERE id NOT IN (SELECT id FROM snapshots ORDER BY id DESC LIMIT ?)",
                (keep,),
            )

    def list_snapshots(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT id,reason,json,created_at FROM snapshots ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        out = []
        for row in rows:
            try:
                state = ensure_state(json.loads(row["json"]))
            except Exception:
                continue
            out.append({"id": row["id"], "reason": row["reason"], "created_at": row["created_at"], "state": state})
        return out

    def latest_snapshot(self) -> dict[str, Any] | None:
        snaps = self.list_snapshots(1)
        return snaps[0] if snaps else None

    def restore_snapshot(self, snapshot_id: int) -> dict[str, Any]:
        row = self.conn.execute("SELECT json FROM snapshots WHERE id=?", (snapshot_id,)).fetchone()
        if not row:
            raise KeyError(f"Snapshot {snapshot_id} does not exist")
        state = ensure_state(json.loads(row["json"]))
        self.save_state(state, reason="before-snapshot-restore", snapshot=True)
        return state

    def checkpoint(self) -> None:
        self.conn.execute("PRAGMA wal_checkpoint(FULL)")

    def copy_database(self, destination: Path | str) -> Path:
        """Create a consistent SQLite backup while the app is running."""
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        target = sqlite3.connect(destination)
        try:
            self.conn.backup(target)
            target.execute("PRAGMA integrity_check")
        finally:
            target.close()
        return destination

    def save_photo(self, registration_id: Any, division: str, source: Path | str) -> Path:
        source = Path(source)
        ext = source.suffix.lower() if source.suffix else ".jpg"
        prefix = "trad" if division.lower().startswith("trad") else "mod"
        destination = self.photos_dir / f"{prefix}_{registration_id}{ext}"
        temp = destination.with_suffix(destination.suffix + ".tmp")
        shutil.copy2(source, temp)
        os.replace(temp, destination)
        return destination

    def find_photo(self, registration_id: Any, division: str) -> Path | None:
        prefix = "trad" if division.lower().startswith("trad") else "mod"
        matches = sorted(self.photos_dir.glob(f"{prefix}_{registration_id}.*"))
        return matches[0] if matches else None

    def setting(self, key: str, default: str = "") -> str:
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
