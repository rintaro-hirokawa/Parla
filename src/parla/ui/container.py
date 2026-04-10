"""DI container — wires all infrastructure, services, and query services."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3

import structlog

from parla.adapters.azure_pronunciation import AzurePronunciationAdapter
from parla.adapters.elevenlabs_tts import ElevenLabsTTSAdapter
from parla.adapters.gemini_feedback import GeminiFeedbackAdapter
from parla.adapters.gemini_overlapping_lag import GeminiOverlappingLagAdapter
from parla.adapters.gemini_passage_generation import GeminiPassageGenerationAdapter
from parla.adapters.gemini_retry_judgment import GeminiRetryJudgmentAdapter
from parla.adapters.gemini_review_judgment import GeminiReviewJudgmentAdapter
from parla.adapters.gemini_variation import GeminiVariationAdapter
from parla.adapters.local_audio_storage import LocalAudioStorage
from parla.adapters.sqlite_db import create_connection, init_schema
from parla.adapters.sqlite_feedback_repository import SQLiteFeedbackRepository
from parla.adapters.sqlite_learning_item_repository import SQLiteLearningItemRepository
from parla.adapters.sqlite_practice_repository import SQLitePracticeRepository
from parla.adapters.sqlite_review_attempt_repository import SQLiteReviewAttemptRepository
from parla.adapters.sqlite_session_repository import SQLiteSessionRepository
from parla.adapters.sqlite_source_repository import SQLiteSourceRepository
from parla.adapters.sqlite_user_settings_repository import SQLiteUserSettingsRepository
from parla.adapters.sqlite_variation_repository import SQLiteVariationRepository
from parla.domain.events import (
    MenuConfirmed,
    ModelAudioRequested,
    SentenceRecorded,
    SourceRegistered,
    VariationGenerationRequested,
)
from parla.domain.session import SessionConfig
from parla.domain.srs import SRSConfig
from parla.event_bus import EventBus
from parla.services.app_state_query_service import AppStateQueryService
from parla.services.feedback_service import FeedbackService
from parla.services.history_query_service import HistoryQueryService
from parla.services.learning_item_query_service import LearningItemQueryService
from parla.services.practice_service import PracticeService
from parla.services.review_service import ReviewService
from parla.services.session_query_service import SessionQueryService
from parla.services.session_service import SessionService
from parla.services.settings_service import SettingsService
from parla.services.source_query_service import SourceQueryService
from parla.services.source_service import SourceService

logger = structlog.get_logger()

_DEFAULT_DATA_DIR = Path.home() / "AppData" / "Local" / "Parla"


class Container:
    """Wires all infrastructure, services, and query services."""

    def __init__(self, *, db_path: str | Path = "") -> None:
        # --- Infrastructure ---
        self.event_bus = EventBus()

        resolved_path = db_path or self._default_db_path()
        self.conn: sqlite3.Connection = create_connection(resolved_path)
        init_schema(self.conn)

        # --- Shared paths ---
        audio_dir = self._audio_dir(resolved_path)

        # --- Repositories ---
        self.session_repo = SQLiteSessionRepository(self.conn)
        self.source_repo = SQLiteSourceRepository(self.conn)
        self.item_repo = SQLiteLearningItemRepository(self.conn)
        self.feedback_repo = SQLiteFeedbackRepository(self.conn)
        self.settings_repo = SQLiteUserSettingsRepository(self.conn)
        self.variation_repo = SQLiteVariationRepository(self.conn)
        self.practice_repo = SQLitePracticeRepository(self.conn, audio_dir)
        self.attempt_repo = SQLiteReviewAttemptRepository(self.conn)

        # --- External Adapters ---
        self.audio_storage = LocalAudioStorage(base_dir=audio_dir)
        self.passage_generator = GeminiPassageGenerationAdapter()
        self.feedback_generator = GeminiFeedbackAdapter()
        self.variation_generator = GeminiVariationAdapter()
        self.retry_judge = GeminiRetryJudgmentAdapter()
        self.review_judge = GeminiReviewJudgmentAdapter()
        self.tts_generator = ElevenLabsTTSAdapter()
        self.pronunciation_assessor = AzurePronunciationAdapter()
        self.lag_detector = GeminiOverlappingLagAdapter()

        # --- Config ---
        self.session_config = SessionConfig()
        self.srs_config = SRSConfig()

        # --- Command Services ---
        self.settings_service = SettingsService(
            event_bus=self.event_bus,
            settings_repo=self.settings_repo,
        )
        self.source_service = SourceService(
            event_bus=self.event_bus,
            source_repo=self.source_repo,
            passage_generator=self.passage_generator,
        )
        self.feedback_service = FeedbackService(
            event_bus=self.event_bus,
            source_repo=self.source_repo,
            feedback_repo=self.feedback_repo,
            item_repo=self.item_repo,
            audio_storage=self.audio_storage,
            feedback_generator=self.feedback_generator,
            retry_judge=self.retry_judge,
        )
        self.review_service = ReviewService(
            event_bus=self.event_bus,
            source_repo=self.source_repo,
            item_repo=self.item_repo,
            variation_repo=self.variation_repo,
            attempt_repo=self.attempt_repo,
            audio_storage=self.audio_storage,
            variation_generator=self.variation_generator,
            review_judge=self.review_judge,
            srs_config=self.srs_config,
        )
        self.practice_service = PracticeService(
            event_bus=self.event_bus,
            source_repo=self.source_repo,
            feedback_repo=self.feedback_repo,
            practice_repo=self.practice_repo,
            tts_generator=self.tts_generator,
            pronunciation_assessor=self.pronunciation_assessor,
            lag_detector=self.lag_detector,
        )
        self.session_service = SessionService(
            event_bus=self.event_bus,
            session_repo=self.session_repo,
            source_repo=self.source_repo,
            item_repo=self.item_repo,
            variation_repo=self.variation_repo,
            variation_generator=self.variation_generator,
            feedback_repo=self.feedback_repo,
            config=self.session_config,
            srs_config=self.srs_config,
        )

        # --- EventBus handler registration ---
        self.event_bus.on_async(SourceRegistered)(self.source_service.handle_source_registered)
        self.event_bus.on_async(SentenceRecorded)(self.feedback_service.handle_sentence_recorded)
        self.event_bus.on_async(VariationGenerationRequested)(self.review_service.handle_variation_requested)
        self.event_bus.on_async(ModelAudioRequested)(self.practice_service.handle_model_audio_requested)
        self.event_bus.on_async(MenuConfirmed)(self.session_service.handle_menu_confirmed)

        # --- Query Services ---
        self.app_state_query = AppStateQueryService(
            settings_repo=self.settings_repo,
            session_repo=self.session_repo,
        )
        self.source_query = SourceQueryService(
            source_repo=self.source_repo,
            practice_repo=self.practice_repo,
        )
        self.item_query = LearningItemQueryService(
            item_repo=self.item_repo,
            source_repo=self.source_repo,
            variation_repo=self.variation_repo,
            review_attempt_repo=self.attempt_repo,
            feedback_repo=self.feedback_repo,
        )
        self.history_query = HistoryQueryService(
            session_repo=self.session_repo,
            practice_repo=self.practice_repo,
            item_repo=self.item_repo,
            review_attempt_repo=self.attempt_repo,
        )
        self.session_query = SessionQueryService(
            session_repo=self.session_repo,
            source_repo=self.source_repo,
            practice_repo=self.practice_repo,
            item_repo=self.item_repo,
            review_attempt_repo=self.attempt_repo,
        )

    def close(self) -> None:
        """Close database connection."""
        self.conn.close()

    @staticmethod
    def _default_db_path() -> Path:
        env = os.environ.get("PARLA_DATA_DIR", "")
        base = Path(env) if env and Path(env).is_absolute() else _DEFAULT_DATA_DIR
        base.mkdir(parents=True, exist_ok=True)
        return base / "parla.db"

    @staticmethod
    def _audio_dir(db_path: str | Path) -> Path:
        db_path = Path(db_path)
        audio = (_DEFAULT_DATA_DIR / "audio") if str(db_path) == ":memory:" else (db_path.parent / "audio")
        audio.mkdir(parents=True, exist_ok=True)
        return audio
