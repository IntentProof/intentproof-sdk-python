"""SQLite WAL outbox for signed execution events."""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Callable
from typing import Any

from intentproof.signing import SENTINEL_PREV_HASH


class Outbox:
    def __init__(self, db_path: str) -> None:
        # Allow use from worker threads (e.g. Flask/gunicorn) after configure().
        self._db = sqlite3.connect(db_path, check_same_thread=False)
        self._lock = threading.Lock()
        self._db.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._db.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    body JSON NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chains (
                    correlation_id TEXT PRIMARY KEY,
                    last_position INTEGER NOT NULL,
                    last_hash TEXT NOT NULL
                );
                """
            )
            self._db.commit()

    def append(self, event_id: str, body: dict[str, Any]) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO events (event_id, body) VALUES (?, ?)",
                (event_id, json.dumps(body)),
            )
            self._db.commit()

    def _next_chain_link(self, correlation_id: str) -> tuple[int, str]:
        row = self._db.execute(
            "SELECT last_position, last_hash FROM chains WHERE correlation_id = ?",
            (correlation_id,),
        ).fetchone()
        if row is None:
            return 1, SENTINEL_PREV_HASH
        return row[0] + 1, row[1]

    def _persist_chain_event(
        self,
        event_id: str,
        body: dict[str, Any],
        correlation_id: str,
        position: int,
        event_hash: str,
    ) -> None:
        self._db.execute(
            "INSERT INTO events (event_id, body) VALUES (?, ?)",
            (event_id, json.dumps(body)),
        )
        self._db.execute(
            """
            INSERT INTO chains (correlation_id, last_position, last_hash)
            VALUES (?, ?, ?)
            ON CONFLICT(correlation_id) DO UPDATE SET
                last_position = excluded.last_position,
                last_hash = excluded.last_hash
            """,
            (correlation_id, position, event_hash),
        )

    def record_chained_event(
        self,
        correlation_id: str,
        event_id: str,
        build_signed: Callable[[int, str], tuple[dict[str, Any], str]],
    ) -> dict[str, Any]:
        """Reserve chain slot, sign, and persist under one lock."""
        with self._lock:
            chain_pos, prev_hash = self._next_chain_link(correlation_id)
            signed, event_hash = build_signed(chain_pos, prev_hash)
            try:
                self._persist_chain_event(
                    event_id, signed, correlation_id, chain_pos, event_hash
                )
                self._db.commit()
            except Exception:
                self._db.rollback()
                raise
            return signed

    def append_with_chain_state(
        self,
        event_id: str,
        body: dict[str, Any],
        correlation_id: str,
        position: int,
        event_hash: str,
    ) -> None:
        """Persist event and chain head in one transaction."""
        with self._lock:
            try:
                self._persist_chain_event(
                    event_id, body, correlation_id, position, event_hash
                )
                self._db.commit()
            except Exception:
                self._db.rollback()
                raise

    def get_events(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute("SELECT body FROM events").fetchall()
        return [json.loads(row[0]) for row in rows]

    def get_chain_state(self, correlation_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._db.execute(
                "SELECT last_position, last_hash FROM chains WHERE correlation_id = ?",
                (correlation_id,),
            ).fetchone()
        if row is None:
            return None
        return {"position": row[0], "hash": row[1]}

    def set_chain_state(
        self, correlation_id: str, position: int, event_hash: str
    ) -> None:
        with self._lock:
            self._db.execute(
                """
                INSERT INTO chains (correlation_id, last_position, last_hash)
                VALUES (?, ?, ?)
                ON CONFLICT(correlation_id) DO UPDATE SET
                    last_position = excluded.last_position,
                    last_hash = excluded.last_hash
                """,
                (correlation_id, position, event_hash),
            )
            self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()
