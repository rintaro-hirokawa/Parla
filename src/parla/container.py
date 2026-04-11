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
from parla.adapters.sqlite_db import create_connection, init_schema, reset_db
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
    PassageGenerationCompleted,
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
    """Wires all infrastructure, services, and query services.

    Public attributes: event_bus, command services, query services, configs.
    Repositories, adapters, and DB connections are private (prefixed with _).
    """

    def __init__(self, *, db_path: str | Path = "") -> None:
        # --- Infrastructure ---
        self.event_bus = EventBus()

        resolved_path = db_path or self._default_db_path()
        self._conn: sqlite3.Connection = create_connection(resolved_path)
        init_schema(self._conn)

        # --- Shared paths ---
        self._audio_dir_path = self._audio_dir(resolved_path)
        audio_dir = self._audio_dir_path
        tts_cache_dir = self._tts_cache_dir(resolved_path)

        # --- Repositories (private) ---
        _session_repo = SQLiteSessionRepository(self._conn)
        _source_repo = SQLiteSourceRepository(self._conn)
        _item_repo = SQLiteLearningItemRepository(self._conn)
        _feedback_repo = SQLiteFeedbackRepository(self._conn)
        _settings_repo = SQLiteUserSettingsRepository(self._conn)
        _variation_repo = SQLiteVariationRepository(self._conn)
        _practice_repo = SQLitePracticeRepository(self._conn, audio_dir)
        _attempt_repo = SQLiteReviewAttemptRepository(self._conn)

        # --- External Adapters (private) ---
        _audio_storage = LocalAudioStorage(base_dir=audio_dir)
        _passage_generator = GeminiPassageGenerationAdapter()
        _feedback_generator = GeminiFeedbackAdapter()
        _variation_generator = GeminiVariationAdapter()
        _retry_judge = GeminiRetryJudgmentAdapter()
        _review_judge = GeminiReviewJudgmentAdapter()
        _tts_generator = ElevenLabsTTSAdapter(cache_dir=tts_cache_dir)
        _pronunciation_assessor = AzurePronunciationAdapter()
        _lag_detector = GeminiOverlappingLagAdapter()

        # --- Config (public) ---
        self.session_config = SessionConfig()
        self.srs_config = SRSConfig()

        # --- Command Services (public) ---
        self.settings_service = SettingsService(
            event_bus=self.event_bus,
            settings_repo=_settings_repo,
        )
        self.source_service = SourceService(
            event_bus=self.event_bus,
            source_repo=_source_repo,
            passage_generator=_passage_generator,
        )
        self.feedback_service = FeedbackService(
            event_bus=self.event_bus,
            source_repo=_source_repo,
            feedback_repo=_feedback_repo,
            item_repo=_item_repo,
            audio_storage=_audio_storage,
            feedback_generator=_feedback_generator,
            retry_judge=_retry_judge,
        )
        self.review_service = ReviewService(
            event_bus=self.event_bus,
            source_repo=_source_repo,
            item_repo=_item_repo,
            variation_repo=_variation_repo,
            attempt_repo=_attempt_repo,
            audio_storage=_audio_storage,
            variation_generator=_variation_generator,
            review_judge=_review_judge,
            srs_config=self.srs_config,
        )
        self.practice_service = PracticeService(
            event_bus=self.event_bus,
            source_repo=_source_repo,
            feedback_repo=_feedback_repo,
            practice_repo=_practice_repo,
            tts_generator=_tts_generator,
            pronunciation_assessor=_pronunciation_assessor,
            lag_detector=_lag_detector,
        )
        self.session_service = SessionService(
            event_bus=self.event_bus,
            session_repo=_session_repo,
            source_repo=_source_repo,
            item_repo=_item_repo,
            variation_repo=_variation_repo,
            variation_generator=_variation_generator,
            feedback_repo=_feedback_repo,
            config=self.session_config,
            srs_config=self.srs_config,
        )

        # --- EventBus handler registration ---
        self.event_bus.on_async(SourceRegistered)(self.source_service.handle_source_registered)
        self.event_bus.on_async(SentenceRecorded)(self.feedback_service.handle_sentence_recorded)
        self.event_bus.on_async(VariationGenerationRequested)(self.review_service.handle_variation_requested)
        self.event_bus.on_async(ModelAudioRequested)(self.practice_service.handle_model_audio_requested)
        self.event_bus.on_async(MenuConfirmed)(self.session_service.handle_menu_confirmed)
        self.event_bus.on_sync(PassageGenerationCompleted)(self.session_service.handle_first_source_ready)

        # --- Query Services (public) ---
        self.app_state_query = AppStateQueryService(
            settings_repo=_settings_repo,
            session_repo=_session_repo,
        )
        self.source_query = SourceQueryService(
            source_repo=_source_repo,
            practice_repo=_practice_repo,
        )
        self.item_query = LearningItemQueryService(
            item_repo=_item_repo,
            source_repo=_source_repo,
            variation_repo=_variation_repo,
            review_attempt_repo=_attempt_repo,
            feedback_repo=_feedback_repo,
        )
        self.history_query = HistoryQueryService(
            session_repo=_session_repo,
            practice_repo=_practice_repo,
            item_repo=_item_repo,
            review_attempt_repo=_attempt_repo,
        )
        self.session_query = SessionQueryService(
            session_repo=_session_repo,
            source_repo=_source_repo,
            practice_repo=_practice_repo,
            item_repo=_item_repo,
            review_attempt_repo=_attempt_repo,
        )

        # --- Seeders need direct repo access (dev-only) ---
        self._session_repo = _session_repo
        self._source_repo = _source_repo
        self._item_repo = _item_repo
        self._feedback_repo = _feedback_repo
        self._settings_repo = _settings_repo
        self._variation_repo = _variation_repo
        self._practice_repo = _practice_repo
        self._attempt_repo = _attempt_repo
        self._skip_to_phase: str | None = None

    def reset_state(self) -> None:
        """Reset all application state: DB tables and audio files. TTS cache is preserved."""
        reset_db(self._conn)
        for f in self._audio_dir_path.iterdir():
            if f.is_file():
                f.unlink()

    def close(self) -> None:
        """Close database connection."""
        self._conn.close()

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

    @staticmethod
    def _tts_cache_dir(db_path: str | Path) -> Path:
        db_path = Path(db_path)
        d = (_DEFAULT_DATA_DIR / "tts_cache") if str(db_path) == ":memory:" else (db_path.parent / "tts_cache")
        d.mkdir(parents=True, exist_ok=True)
        return d
