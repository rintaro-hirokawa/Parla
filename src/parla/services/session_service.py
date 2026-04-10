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
    select_pattern,
)
from parla.domain.source import Source
from parla.domain.variation import Variation
from parla.event_bus import EventBus
from parla.ports.feedback_repository import FeedbackRepository
from parla.ports.learning_item_repository import LearningItemRepository
from parla.ports.session_repository import SessionRepository
from parla.ports.source_repository import SourceRepository
from parla.ports.variation_generation import PastVariationInfo, VariationGenerationPort
from parla.ports.variation_repository import VariationRepository

logger = structlog.get_logger()

_MAX_HISTORY_FOR_PROMPT = 10


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
    ) -> None:
        self._bus = event_bus
        self._session_repo = session_repo
        self._source_repo = source_repo
        self._item_repo = item_repo
        self._variation_repo = variation_repo
        self._variation_generator = variation_generator
        self._feedback_repo = feedback_repo
        self._config = config

    # --- Menu Composition ---

    def compose_menu(
        self,
        target_date: date,
        source_id: UUID,
        today: date,
    ) -> SessionMenu:
        """Compose a session menu for the given date. Deterministic, no LLM."""
        pending_count = self._item_repo.count_due_items(today)
        pattern = select_pattern(pending_count, self._config)

        review_item_ids: list[UUID] = []
        if pattern in ("a", "b"):
            due_items = self._item_repo.get_due_items(today, limit=self._config.review_limit)
            review_item_ids = [item.id for item in due_items]

        passage_ids: list[UUID] = []
        menu_source_id: UUID | None = None
        if pattern in ("a", "c"):
            passage_ids = self._select_next_passages(source_id)
            menu_source_id = source_id

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
    ) -> SessionMenu:
        """Recompose menu with a different source."""
        old_menu = self._session_repo.get_menu(menu_id)
        if old_menu is None:
            msg = f"Menu not found: {menu_id}"
            raise ValueError(msg)

        new_menu = self.compose_menu(target_date=target_date, source_id=new_source_id, today=today)

        self._bus.emit(
            MenuRecomposed(
                menu_id=new_menu.id,
                new_source_id=new_source_id,
            )
        )

        return new_menu

    def _select_next_passages(self, source_id: UUID) -> list[UUID]:
        """Select the next unlearned passage from the source."""
        passages = self._source_repo.get_passages_by_source(source_id)
        for passage in passages:
            has_feedback = any(
                self._feedback_repo.get_feedback_by_sentence(s.id) is not None for s in passage.sentences
            )
            if not has_feedback:
                return [passage.id]
        # All passages learned — return the first one as fallback
        if passages:
            return [passages[0].id]
        return []

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

            # Find the source for context via sentence → passage → source
            source = self._find_source_for_item(item.source_sentence_id)
            if source is None:
                logger.error("source_not_found_for_item", item_id=str(item_id))
                failure += 1
                continue

            try:
                past_variations = self._variation_repo.get_variations_by_item(item_id)
                past_info = [PastVariationInfo(ja=v.ja, en=v.en) for v in past_variations[-_MAX_HISTORY_FOR_PROMPT:]]

                raw = await self._variation_generator.generate_variation(
                    learning_item_pattern=item.pattern,
                    learning_item_explanation=item.explanation,
                    cefr_level=source.cefr_level,
                    english_variant=source.english_variant,
                    source_text=source.text,
                    past_variations=past_info,
                )

                variation = Variation(
                    learning_item_id=item.id,
                    source_id=source.id,
                    ja=raw.ja,
                    en=raw.en,
                    hint1=raw.hint1,
                    hint2=raw.hint2,
                )
                self._variation_repo.save_variation(variation)
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

    def _find_source_for_item(self, source_sentence_id: UUID) -> Source | None:
        """Trace source_sentence_id → passage → source."""
        # Look through all sources to find the one containing the sentence
        sources = self._source_repo.get_active_sources()
        for source in sources:
            passages = self._source_repo.get_passages_by_source(source.id)
            for passage in passages:
                for sentence in passage.sentences:
                    if sentence.id == source_sentence_id:
                        return source
        return None

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
        state = self._session_repo.get_state(session_id)
        if state is None:
            msg = f"Session not found: {session_id}"
            raise ValueError(msg)

        state.status = "interrupted"
        state.interrupted_at = datetime.now()
        self._session_repo.update_state(state)

        self._bus.emit(
            SessionInterrupted(
                session_id=session_id,
                block_index=state.current_block_index,
            )
        )

    def resume_session(self, session_id: UUID) -> SessionState:
        """Resume an interrupted session at the same block."""
        state = self._session_repo.get_state(session_id)
        if state is None:
            msg = f"Session not found: {session_id}"
            raise ValueError(msg)
        if state.status != "interrupted":
            msg = f"Session is not interrupted: {session_id}"
            raise ValueError(msg)

        state.status = "in_progress"
        state.interrupted_at = None
        self._session_repo.update_state(state)

        self._bus.emit(
            SessionResumed(
                session_id=session_id,
                block_index=state.current_block_index,
            )
        )

        return state

    def advance_block(self, session_id: UUID) -> SessionState:
        """Move to the next block. If last block, complete the session."""
        state = self._session_repo.get_state(session_id)
        if state is None:
            msg = f"Session not found: {session_id}"
            raise ValueError(msg)

        menu = self._session_repo.get_menu(state.menu_id)
        if menu is None:
            msg = f"Menu not found: {state.menu_id}"
            raise ValueError(msg)

        next_index = state.current_block_index + 1

        if next_index >= len(menu.blocks):
            state.status = "completed"
            state.completed_at = datetime.now()
            self._session_repo.update_state(state)
            self._bus.emit(SessionCompleted(session_id=session_id))
        else:
            state.current_block_index = next_index
            self._session_repo.update_state(state)

        return state

    # --- Menu Freshness ---

    def check_menu_freshness(self, today: date) -> SessionMenu | None:
        """Return today's confirmed menu, or None if stale/missing."""
        return self._session_repo.get_menu_for_date(today)

    # --- Source Management ---

    def get_active_sources(self) -> list[Source]:
        """Return sources available for menu composition."""
        return list(self._source_repo.get_active_sources())
