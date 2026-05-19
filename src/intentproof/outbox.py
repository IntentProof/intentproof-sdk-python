"""SQLite WAL outbox for signed execution events."""

from __future__ import annotations

import json
import sqlite3
from typing import Any


class Outbox:
    def __init__(self, db_path: str) -> None:
        self._db = sqlite3.connect(db_path)
        self._db.execute("PRAGMA journal_mode=WAL")
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
        self._db.execute(
            "INSERT INTO events (event_id, body) VALUES (?, ?)",
            (event_id, json.dumps(body)),
        )
        self._db.commit()

    def append_with_chain_state(
        self,
        event_id: str,
        body: dict[str, Any],
        correlation_id: str,
        position: int,
        event_hash: str,
    ) -> None:
        """Persist event and chain head in one transaction."""
        try:
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
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

    def get_events(self) -> list[dict[str, Any]]:
        rows = self._db.execute("SELECT body FROM events").fetchall()
        return [json.loads(row[0]) for row in rows]

    def get_chain_state(self, correlation_id: str) -> dict[str, Any] | None:
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
        self._db.close()
