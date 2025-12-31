from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:  # pragma: no cover - avoids circular import at runtime
    from polymarketbot.strategy.live_two_leg import LiveStrategyState

logger = logging.getLogger(__name__)


class StateStore:
    """Simple SQLite-backed persistence for bot state and events."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                leg1_token_id TEXT,
                leg1_price REAL,
                leg1_time REAL,
                active INTEGER
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payload TEXT
            )
            """
        )
        conn.commit()
        conn.close()

    def save_state(self, state: "LiveStrategyState") -> None:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("DELETE FROM state")
        cur.execute(
            "INSERT INTO state (id, leg1_token_id, leg1_price, leg1_time, active) VALUES (?, ?, ?, ?, ?)",
            (1, state.leg1_token_id, state.leg1_price, state.leg1_time, int(state.active)),
        )
        conn.commit()
        conn.close()

    def load_state(self) -> Optional["LiveStrategyState"]:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT leg1_token_id, leg1_price, leg1_time, active FROM state WHERE id = 1")
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        token_id, price, ts, active = row
        from polymarketbot.strategy.live_two_leg import LiveStrategyState

        return LiveStrategyState(
            leg1_token_id=token_id,
            leg1_price=price,
            leg1_time=ts,
            active=bool(active),
        )

    def record_event(self, payload: Dict[str, Any]) -> None:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("INSERT INTO events (payload) VALUES (?)", (json.dumps(payload),))
        conn.commit()
        conn.close()
