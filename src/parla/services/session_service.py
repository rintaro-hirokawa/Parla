"""Session composition and lifecycle orchestration service."""

from datetime import date, datetime
from uuid import UUID

import structlog

from parla.domain.events import (
    BackgroundGenerationCompleted,
    BackgroundGenerationStarted,
    MenuComposed,
    MenuConfirmed,
    MenuRecomposed,
    PassageGenerationCompleted,
    SessionCompleted,
    SessionInterrupted,
    SessionResumed,
    SessionStarted,
)
from parla.domain.session import (
    SessionConfig,
    SessionMenu,
    SessionState,
    compose_blocks,
    select_next_unlearned_passage,
    select_pattern,
)
from parla.domain.source import Source
from parla.domain.srs import SRSConfig
from parla.event_bus import EventBus
from parla.ports.feedback_repository import FeedbackRepository
from parla.ports.learning_item_repository import LearningItemRepository
from parla.ports.session_repository import SessionRepository
from parla.ports.source_repository import SourceRepository
from parla.ports.variation_generation import VariationGenerationPort
from parla.ports.variation_repository import VariationRepository
from parla.services.variation_helper import generate_and_save_variation

logger = structlog.get_logger()


class SessionService:
    """Orchestrates session composition, menu confirmation, and session lifecycle."""

    def __init__(
        self,
        event_bus: EventBus,
        session_repo: SessionRepository,
        source_repo: SourceRepository,
        item_repo: LearningItemRepository,
        variation_repo: VariationRepository,
        variation_generator: VariationGenerationPort,
        feedback_repo: FeedbackRepository,
        config: SessionConfig,
        srs_config: SRSConfig,
    ) -> None:
        self._bus = event_bus
        self._session_repo = session_repo
        self._source_repo = source_repo
        self._item_repo = item_repo
        self._variation_repo = variation_repo
        self._variation_generator = variation_generator
        self._feedback_repo = feedback_repo
        self._config = config
        self._srs_config = srs_config

    # --- Auto-compose on first source ---

    def handle_first_source_ready(self, event: PassageGenerationCompleted) -> None:
        """Auto-compose and confirm today's menu when a source completes generation."""
        today = date.today()
        existing = self._session_repo.get_menu_for_date(today)
        if existing is not None:
            return

        source = self._source_repo.get_source(event.source_id)
        if source is None or source.status != "not_started":
            return

        menu = self.compose_menu(target_date=today, source_id=source.id, today=today)
        if menu is not None:
            self.confirm_menu(menu.id)

    # --- Menu Composition ---

    def compose_menu(
        self,
        target_date: date,
        source_id: UUID,
        today: date,
    ) -> SessionMenu | None:
        """Compose a session menu for the given date. Deterministic, no LLM.

        Returns None when no content is available (no passages and no reviews).
        """
        pending_count = self._item_repo.count_due_items(today)
        pattern = select_pattern(pending_count, self._config)

        review_item_ids: list[UUID] = []
        if pattern in ("a", "b"):
            due_items = self._item_repo.get_due_items(today, limit=self._srs_config.review_limit)
            review_item_ids = [item.id for item in due_items]

        passage_ids: list[UUID] = []
        menu_source_id: UUID | None = None
        if pattern in ("a", "c"):
            passage_ids = self._select_next_passages(source_id)
            if passage_ids:
                menu_source_id = source_id
            elif pattern == "a":
                pattern = "b"  # downgrade: review only
            else:
                # pattern "c" with no passages and no reviews = nothing to do
                return None

        blocks = compose_blocks(
            pattern=pattern,
            review_item_ids=review_item_ids,
            passage_ids=passage_ids,
            config=self._config,
        )

        menu = SessionMenu(
            target_date=target_date,
            pattern=pattern,
            blocks=blocks,
            source_id=menu_source_id,
            pending_review_count=pending_count,
        )

        self._session_repo.save_menu(menu)
        self._bus.emit(
            MenuComposed(
                menu_id=menu.id,
                target_date=target_date,
                pattern=pattern,
                block_count=len(blocks),
            )
        )

        return menu

    def recompose_menu(
        self,
        menu_id: UUID,
        new_source_id: UUID,
        target_date: date,
        today: date,
    ) -> SessionMenu | None:
        """Recompose menu with a different source.

        Returns None when the new source has no remaining passages and no reviews.
        """
        old_menu = self._session_repo.get_menu(menu_id)
        if old_menu is None:
            msg = f"Menu not found: {menu_id}"
            raise ValueError(msg)

        new_menu = self.compose_menu(target_date=target_date, source_id=new_source_id, today=today)
        if new_menu is None:
            return None

        self._bus.emit(
            MenuRecomposed(
                menu_id=new_menu.id,
                new_source_id=new_source_id,
            )
        )

        return new_menu

    def _select_next_passages(self, source_id: UUID) -> list[UUID]:
        """Select the next unlearned passage from the source.

        Returns an empty list when all passages have been learned.
        """
        passages = self._source_repo.get_passages_by_source(source_id)
        passage_ids = [p.id for p in passages]

        learned_ids: set[UUID] = set()
        for passage in passages:
            has_feedback = any(
                self._feedback_repo.get_feedback_by_sentence(s.id) is not None for s in passage.sentences
            )
            if has_feedback:
                learned_ids.add(passage.id)

        next_id = select_next_unlearned_passage(passage_ids, learned_ids)
        return [next_id] if next_id is not None else []

    # --- Menu Confirmation ---

    def confirm_menu(self, menu_id: UUID) -> None:
        """Confirm the menu. Emits MenuConfirmed to trigger background generation."""
        menu = self._session_repo.get_menu(menu_id)
        if menu is None:
            msg = f"Menu not found: {menu_id}"
            raise ValueError(msg)

        confirmed = menu.model_copy(update={"confirmed": True})
        self._session_repo.save_menu(confirmed)

        self._bus.emit(
            MenuConfirmed(
                menu_id=menu_id,
                target_date=menu.target_date,
            )
        )

    # --- Background Generation (async handler) ---

    async def handle_menu_confirmed(self, event: MenuConfirmed) -> None:
        """Generate variations for all review items in the confirmed menu."""
        menu = self._session_repo.get_menu(event.menu_id)
        if menu is None:
            logger.error("menu_not_found", menu_id=str(event.menu_id))
            return

        review_block = next((b for b in menu.blocks if b.block_type == "review"), None)
        if review_block is None or len(review_block.items) == 0:
            self._bus.emit(
                BackgroundGenerationCompleted(
                    menu_id=event.menu_id,
                    success_count=0,
                    failure_count=0,
                )
            )
            return

        self._bus.emit(
            BackgroundGenerationStarted(
                menu_id=event.menu_id,
                item_count=len(review_block.items),
            )
        )

        success = 0
        failure = 0

        for item_id in review_block.items:
            item = self._item_repo.get_item(item_id)
            if item is None:
                logger.error("learning_item_not_found", item_id=str(item_id))
                failure += 1
                continue

            source = self._source_repo.get_source_by_sentence_id(item.source_sentence_id)
            if source is None:
                logger.error("source_not_found_for_item", item_id=str(item_id))
                failure += 1
                continue

            try:
                await generate_and_save_variation(
                    item=item,
                    source=source,
                    variation_repo=self._variation_repo,
                    variation_generator=self._variation_generator,
                )
                success += 1

            except Exception:
                logger.exception("variation_generation_failed", item_id=str(item_id))
                failure += 1

        self._bus.emit(
            BackgroundGenerationCompleted(
                menu_id=event.menu_id,
                success_count=success,
                failure_count=failure,
            )
        )

    # --- Session Lifecycle ---

    def start_session(self, menu_id: UUID) -> SessionState:
        """Start a session from a confirmed menu."""
        menu = self._session_repo.get_menu(menu_id)
        if menu is None:
            msg = f"Menu not found: {menu_id}"
            raise ValueError(msg)
        if not menu.confirmed:
            msg = f"Menu is not confirmed: {menu_id}"
            raise ValueError(msg)

        state = SessionState(
            menu_id=menu_id,
            status="in_progress",
            started_at=datetime.now(),
        )
        self._session_repo.save_state(state)

        self._bus.emit(
            SessionStarted(
                session_id=state.id,
                menu_id=menu_id,
            )
        )

        return state

    def interrupt_session(self, session_id: UUID) -> None:
        """Record interruption at current block."""
        state = self._get_state(session_id)
        updated = state.model_copy(update={"status": "interrupted", "interrupted_at": datetime.now()})
        self._session_repo.update_state(updated)

        self._bus.emit(
            SessionInterrupted(
                session_id=session_id,
                block_index=updated.current_block_index,
            )
        )

    def resume_session(self, session_id: UUID) -> SessionState:
        """Resume an interrupted session at the same block."""
        state = self._get_state(session_id)
        if state.status != "interrupted":
            msg = f"Session is not interrupted: {session_id}"
            raise ValueError(msg)

        updated = state.model_copy(update={"status": "in_progress", "interrupted_at": None})
        self._session_repo.update_state(updated)

        self._bus.emit(
            SessionResumed(
                session_id=session_id,
                block_index=updated.current_block_index,
            )
        )

        return updated

    def advance_block(self, session_id: UUID) -> SessionState:
        """Move to the next block. If last block, complete the session."""
        state = self._get_state(session_id)

        menu = self._session_repo.get_menu(state.menu_id)
        if menu is None:
            msg = f"Menu not found: {state.menu_id}"
            raise ValueError(msg)

        next_index = state.current_block_index + 1

        if next_index >= len(menu.blocks):
            updated = state.model_copy(update={"status": "completed", "completed_at": datetime.now()})
            self._session_repo.update_state(updated)
            self._bus.emit(SessionCompleted(session_id=session_id))
        else:
            updated = state.model_copy(update={"current_block_index": next_index})
            self._session_repo.update_state(updated)

        return updated

    def _get_state(self, session_id: UUID) -> SessionState:
        state = self._session_repo.get_state(session_id)
        if state is None:
            msg = f"Session not found: {session_id}"
            raise ValueError(msg)
        return state

    # --- Menu Freshness ---

    def check_menu_freshness(self, today: date) -> SessionMenu | None:
        """Return today's confirmed menu, or None if stale/missing."""
        return self._session_repo.get_menu_for_date(today)

    # --- Source Management ---

    def get_active_sources(self) -> list[Source]:
        """Return sources available for menu composition."""
        return list(self._source_repo.get_active_sources())
