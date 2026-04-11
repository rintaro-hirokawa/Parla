"""SQLite implementation of PracticeRepository."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import UUID

from parla.domain.audio import AudioData
from parla.domain.practice import (
    LiveDeliveryResult,
    ModelAudio,
    OverlappingResult,
    PronunciationWord,
    SentenceStatus,
    WordTimestamp,
)


class SQLitePracticeRepository:
    """Persists Phase C practice results to SQLite."""

    def __init__(self, conn: sqlite3.Connection, audio_dir: Path) -> None:
        self._conn = conn
        self._audio_dir = audio_dir
        self._audio_dir.mkdir(parents=True, exist_ok=True)

    # --- Model Audio ---

    def save_model_audio(self, model_audio: ModelAudio) -> None:
        audio_path = self._audio_dir / f"model_{model_audio.passage_id}.{model_audio.audio.format}"
        audio_path.write_bytes(model_audio.audio.data)

        timestamps_json = json.dumps(
            [
                {"word": wt.word, "start_seconds": wt.start_seconds, "end_seconds": wt.end_seconds}
                for wt in model_audio.word_timestamps
            ]
        )
        sentence_texts_json = json.dumps(list(model_audio.sentence_texts))

        self._conn.execute(
            """INSERT OR REPLACE INTO model_audio
               (passage_id, audio_path, timestamps, sample_rate, channels,
                sample_width, duration_seconds, generated_at, sentence_texts)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(model_audio.passage_id),
                str(audio_path),
                timestamps_json,
                model_audio.audio.sample_rate,
                model_audio.audio.channels,
                model_audio.audio.sample_width,
                model_audio.audio.duration_seconds,
                model_audio.generated_at.isoformat(),
                sentence_texts_json,
            ),
        )
        self._conn.commit()

    def get_model_audio(self, passage_id: UUID) -> ModelAudio | None:
        row = self._conn.execute(
            "SELECT * FROM model_audio WHERE passage_id = ?",
            (str(passage_id),),
        ).fetchone()
        if row is None:
            return None

        audio_path = Path(row["audio_path"])
        if not audio_path.exists():
            return None

        audio_data = audio_path.read_bytes()
        fmt = audio_path.suffix.lstrip(".")

        timestamps = tuple(
            WordTimestamp(word=t["word"], start_seconds=t["start_seconds"], end_seconds=t["end_seconds"])
            for t in json.loads(row["timestamps"])
        )

        sentence_texts = tuple(json.loads(row["sentence_texts"]))

        return ModelAudio(
            passage_id=UUID(row["passage_id"]),
            audio=AudioData(
                data=audio_data,
                format=fmt,
                sample_rate=row["sample_rate"],
                channels=row["channels"],
                sample_width=row["sample_width"],
                duration_seconds=row["duration_seconds"],
            ),
            word_timestamps=timestamps,
            sentence_texts=sentence_texts,
            generated_at=datetime.fromisoformat(row["generated_at"]),
        )

    # --- Overlapping Results ---

    def save_overlapping_result(self, result: OverlappingResult) -> None:
        words_json = json.dumps([w.model_dump() for w in result.words])
        deviations_json = json.dumps(list(result.timing_deviations))

        self._conn.execute(
            """INSERT INTO overlapping_results
               (id, passage_id, words, timing_deviations, accuracy_score,
                fluency_score, prosody_score, pronunciation_score, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(result.id),
                str(result.passage_id),
                words_json,
                deviations_json,
                result.accuracy_score,
                result.fluency_score,
                result.prosody_score,
                result.pronunciation_score,
                result.created_at.isoformat(),
            ),
        )
        self._conn.commit()

    def get_overlapping_result(self, passage_id: UUID) -> OverlappingResult | None:
        row = self._conn.execute(
            "SELECT * FROM overlapping_results WHERE passage_id = ? ORDER BY created_at DESC LIMIT 1",
            (str(passage_id),),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_overlapping_result(row)

    # --- Live Delivery Results ---

    def save_live_delivery_result(self, result: LiveDeliveryResult) -> None:
        statuses_json = json.dumps([s.model_dump() for s in result.sentence_statuses])

        self._conn.execute(
            """INSERT INTO live_delivery_results
               (id, passage_id, passed, sentence_statuses, duration_seconds, wpm, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                str(result.id),
                str(result.passage_id),
                int(result.passed),
                statuses_json,
                result.duration_seconds,
                result.wpm,
                result.created_at.isoformat(),
            ),
        )
        self._conn.commit()

    def get_live_delivery_results(self, passage_id: UUID) -> list[LiveDeliveryResult]:
        rows = self._conn.execute(
            "SELECT * FROM live_delivery_results WHERE passage_id = ? ORDER BY created_at",
            (str(passage_id),),
        ).fetchall()
        return [self._row_to_live_delivery(r) for r in rows]

    def get_all_live_delivery_results(self) -> list[LiveDeliveryResult]:
        rows = self._conn.execute(
            "SELECT * FROM live_delivery_results ORDER BY created_at",
        ).fetchall()
        return [self._row_to_live_delivery(r) for r in rows]

    # --- Passage Achievements ---

    def save_achievement(self, passage_id: UUID, achieved_at: datetime) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO passage_achievements (passage_id, achieved_at)
               VALUES (?, ?)""",
            (str(passage_id), achieved_at.isoformat()),
        )
        self._conn.commit()

    def has_achievement(self, passage_id: UUID) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM passage_achievements WHERE passage_id = ?",
            (str(passage_id),),
        ).fetchone()
        return row is not None

    # --- Row converters ---

    @staticmethod
    def _row_to_overlapping_result(row: sqlite3.Row) -> OverlappingResult:
        words = tuple(PronunciationWord(**w) for w in json.loads(row["words"]))
        deviations = tuple(json.loads(row["timing_deviations"]))
        return OverlappingResult(
            id=UUID(row["id"]),
            passage_id=UUID(row["passage_id"]),
            words=words,
            timing_deviations=deviations,
            accuracy_score=row["accuracy_score"],
            fluency_score=row["fluency_score"],
            prosody_score=row["prosody_score"],
            pronunciation_score=row["pronunciation_score"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    @staticmethod
    def _row_to_live_delivery(row: sqlite3.Row) -> LiveDeliveryResult:
        statuses = tuple(SentenceStatus(**s) for s in json.loads(row["sentence_statuses"]))
        return LiveDeliveryResult(
            id=UUID(row["id"]),
            passage_id=UUID(row["passage_id"]),
            passed=bool(row["passed"]),
            sentence_statuses=statuses,
            duration_seconds=row["duration_seconds"],
            wpm=row["wpm"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
