"""SQLite implementation of SessionRepository."""

import json
import sqlite3
from datetime import date, datetime
from uuid import UUID

from parla.domain.session import SessionBlock, SessionMenu, SessionState


class SQLiteSessionRepository:
    """Persists session menus and execution state to SQLite."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # --- Menu ---

    def save_menu(self, menu: SessionMenu) -> None:
        blocks_json = json.dumps([b.model_dump(mode="json") for b in menu.blocks])
        self._conn.execute(
            """INSERT OR REPLACE INTO session_menus
               (id, target_date, pattern, blocks, source_id,
                confirmed, pending_review_count, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(menu.id),
                menu.target_date.isoformat(),
                menu.pattern,
                blocks_json,
                str(menu.source_id) if menu.source_id else None,
                int(menu.confirmed),
                menu.pending_review_count,
                menu.created_at.isoformat(),
            ),
        )
        self._conn.commit()

    def get_menu(self, menu_id: UUID) -> SessionMenu | None:
        row = self._conn.execute(
            "SELECT * FROM session_menus WHERE id = ?",
            (str(menu_id),),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_menu(row)

    def get_menu_for_date(self, target_date: date) -> SessionMenu | None:
        row = self._conn.execute(
            """SELECT * FROM session_menus
               WHERE target_date = ? AND confirmed = 1
               ORDER BY created_at DESC LIMIT 1""",
            (target_date.isoformat(),),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_menu(row)

    def _row_to_menu(self, row: sqlite3.Row) -> SessionMenu:
        blocks_data = json.loads(row["blocks"])
        blocks = tuple(SessionBlock.model_validate(b) for b in blocks_data)
        return SessionMenu(
            id=UUID(row["id"]),
            target_date=date.fromisoformat(row["target_date"]),
            pattern=row["pattern"],
            blocks=blocks,
            source_id=UUID(row["source_id"]) if row["source_id"] else None,
            confirmed=bool(row["confirmed"]),
            pending_review_count=row["pending_review_count"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    # --- State ---

    def save_state(self, state: SessionState) -> None:
        self._conn.execute(
            """INSERT INTO session_states
               (id, menu_id, status, current_block_index,
                started_at, completed_at, interrupted_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            self._state_to_params(state),
        )
        self._conn.commit()

    def get_state(self, session_id: UUID) -> SessionState | None:
        row = self._conn.execute(
            "SELECT * FROM session_states WHERE id = ?",
            (str(session_id),),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_state(row)

    def get_active_state(self) -> SessionState | None:
        row = self._conn.execute(
            """SELECT * FROM session_states
               WHERE status IN ('in_progress', 'interrupted')
               ORDER BY started_at DESC LIMIT 1""",
        ).fetchone()
        if row is None:
            return None
        return self._row_to_state(row)

    def update_state(self, state: SessionState) -> None:
        self._conn.execute(
            """UPDATE session_states
               SET status = ?, current_block_index = ?,
                   started_at = ?, completed_at = ?, interrupted_at = ?
               WHERE id = ?""",
            (
                state.status,
                state.current_block_index,
                state.started_at.isoformat() if state.started_at else None,
                state.completed_at.isoformat() if state.completed_at else None,
                state.interrupted_at.isoformat() if state.interrupted_at else None,
                str(state.id),
            ),
        )
        self._conn.commit()

    def _state_to_params(self, state: SessionState) -> tuple[str, str, str, int, str | None, str | None, str | None]:
        return (
            str(state.id),
            str(state.menu_id),
            state.status,
            state.current_block_index,
            state.started_at.isoformat() if state.started_at else None,
            state.completed_at.isoformat() if state.completed_at else None,
            state.interrupted_at.isoformat() if state.interrupted_at else None,
        )

    def _row_to_state(self, row: sqlite3.Row) -> SessionState:
        return SessionState(
            id=UUID(row["id"]),
            menu_id=UUID(row["menu_id"]),
            status=row["status"],
            current_block_index=row["current_block_index"],
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            interrupted_at=datetime.fromisoformat(row["interrupted_at"]) if row["interrupted_at"] else None,
        )
