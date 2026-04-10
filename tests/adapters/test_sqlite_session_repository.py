"""Tests for SQLiteSessionRepository."""

from datetime import date, datetime
from uuid import uuid4

from parla.adapters.sqlite_db import create_connection, init_schema
from parla.adapters.sqlite_session_repository import SQLiteSessionRepository
from parla.domain.session import SessionBlock, SessionMenu, SessionState


def _setup():
    conn = create_connection(":memory:")
    init_schema(conn)
    repo = SQLiteSessionRepository(conn)
    return repo


def _make_menu(
    target_date: date = date(2026, 4, 11),
    confirmed: bool = False,
) -> SessionMenu:
    return SessionMenu(
        target_date=target_date,
        pattern="a",
        blocks=(
            SessionBlock(
                block_type="review",
                items=(uuid4(), uuid4()),
                estimated_minutes=4.0,
            ),
            SessionBlock(
                block_type="new_material",
                items=(uuid4(),),
                estimated_minutes=10.0,
            ),
            SessionBlock(
                block_type="consolidation",
                items=(),
                estimated_minutes=0.0,
            ),
        ),
        source_id=uuid4(),
        confirmed=confirmed,
        pending_review_count=15,
    )


class TestMenuPersistence:
    def test_save_and_get_menu(self) -> None:
        repo = _setup()
        menu = _make_menu()
        repo.save_menu(menu)

        loaded = repo.get_menu(menu.id)
        assert loaded is not None
        assert loaded.id == menu.id
        assert loaded.target_date == date(2026, 4, 11)
        assert loaded.pattern == "a"
        assert len(loaded.blocks) == 3
        assert loaded.blocks[0].block_type == "review"
        assert len(loaded.blocks[0].items) == 2
        assert loaded.blocks[1].block_type == "new_material"
        assert loaded.blocks[2].block_type == "consolidation"
        assert loaded.source_id == menu.source_id
        assert loaded.confirmed is False
        assert loaded.pending_review_count == 15

    def test_get_nonexistent_returns_none(self) -> None:
        repo = _setup()
        assert repo.get_menu(uuid4()) is None

    def test_save_menu_with_none_source_id(self) -> None:
        repo = _setup()
        menu = SessionMenu(
            target_date=date(2026, 4, 11),
            pattern="b",
            blocks=(SessionBlock(block_type="review", items=(uuid4(),), estimated_minutes=2.0),),
            source_id=None,
            confirmed=False,
            pending_review_count=31,
        )
        repo.save_menu(menu)

        loaded = repo.get_menu(menu.id)
        assert loaded is not None
        assert loaded.source_id is None
        assert loaded.pattern == "b"

    def test_save_replaces_existing(self) -> None:
        repo = _setup()
        menu = _make_menu()
        repo.save_menu(menu)

        confirmed = menu.model_copy(update={"confirmed": True})
        repo.save_menu(confirmed)

        loaded = repo.get_menu(menu.id)
        assert loaded is not None
        assert loaded.confirmed is True

    def test_get_menu_for_date(self) -> None:
        repo = _setup()
        menu = _make_menu(confirmed=True)
        repo.save_menu(menu)

        result = repo.get_menu_for_date(date(2026, 4, 11))
        assert result is not None
        assert result.id == menu.id

    def test_get_menu_for_date_unconfirmed_returns_none(self) -> None:
        repo = _setup()
        menu = _make_menu(confirmed=False)
        repo.save_menu(menu)

        result = repo.get_menu_for_date(date(2026, 4, 11))
        assert result is None

    def test_get_menu_for_date_wrong_date_returns_none(self) -> None:
        repo = _setup()
        menu = _make_menu(confirmed=True)
        repo.save_menu(menu)

        result = repo.get_menu_for_date(date(2026, 4, 12))
        assert result is None


class TestStatePersistence:
    def test_save_and_get_state(self) -> None:
        repo = _setup()
        menu = _make_menu()
        repo.save_menu(menu)

        state = SessionState(
            menu_id=menu.id,
            status="in_progress",
            started_at=datetime(2026, 4, 11, 9, 0),
        )
        repo.save_state(state)

        loaded = repo.get_state(state.id)
        assert loaded is not None
        assert loaded.menu_id == menu.id
        assert loaded.status == "in_progress"
        assert loaded.current_block_index == 0
        assert loaded.started_at == datetime(2026, 4, 11, 9, 0)

    def test_get_nonexistent_state_returns_none(self) -> None:
        repo = _setup()
        assert repo.get_state(uuid4()) is None

    def test_update_state(self) -> None:
        repo = _setup()
        menu = _make_menu()
        repo.save_menu(menu)

        state = SessionState(
            menu_id=menu.id,
            status="in_progress",
            started_at=datetime(2026, 4, 11, 9, 0),
        )
        repo.save_state(state)

        state.status = "interrupted"
        state.current_block_index = 1
        state.interrupted_at = datetime(2026, 4, 11, 9, 15)
        repo.update_state(state)

        loaded = repo.get_state(state.id)
        assert loaded is not None
        assert loaded.status == "interrupted"
        assert loaded.current_block_index == 1
        assert loaded.interrupted_at == datetime(2026, 4, 11, 9, 15)

    def test_get_active_state(self) -> None:
        repo = _setup()
        menu = _make_menu()
        repo.save_menu(menu)

        state = SessionState(
            menu_id=menu.id,
            status="in_progress",
            started_at=datetime(2026, 4, 11, 9, 0),
        )
        repo.save_state(state)

        active = repo.get_active_state()
        assert active is not None
        assert active.id == state.id

    def test_get_active_state_none_when_completed(self) -> None:
        repo = _setup()
        menu = _make_menu()
        repo.save_menu(menu)

        state = SessionState(
            menu_id=menu.id,
            status="completed",
            started_at=datetime(2026, 4, 11, 9, 0),
            completed_at=datetime(2026, 4, 11, 9, 30),
        )
        repo.save_state(state)

        assert repo.get_active_state() is None
