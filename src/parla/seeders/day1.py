"""Day 1 state seeder — fresh start with Toyota source and passages ready."""

from __future__ import annotations

import json
import struct
import wave
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from parla.domain.audio import AudioData
from parla.domain.feedback import SentenceFeedback
from parla.domain.passage import Hint, Passage, Sentence
from parla.domain.practice import ModelAudio, WordTimestamp
from parla.domain.session import SessionConfig, SessionMenu, compose_blocks
from parla.domain.source import CEFRLevel, EnglishVariant, Source
from parla.domain.user_settings import UserSettings

if TYPE_CHECKING:
    from parla.container import Container

logger = structlog.get_logger()

_FIXTURES = Path(__file__).parent / "fixtures"


def seed(
    container: Container,
    *,
    max_passages: int | None = None,
    max_sentences: int | None = None,
    seed_feedback: bool = False,
    seed_model_audio: bool = False,
) -> None:
    """Reset DB and seed day-1 state: settings, source, passages, confirmed menu."""
    logger.info("seed_day1_start")

    container.reset_state()

    # 1. User settings
    settings = UserSettings(cefr_level=CEFRLevel.A2, english_variant=EnglishVariant.AMERICAN)
    container._settings_repo.save(settings)

    # 2. Source
    source_text = (_FIXTURES / "sample_01.txt").read_text(encoding="utf-8")
    source = Source(
        text=source_text,
        cefr_level=CEFRLevel.A2,
        english_variant=EnglishVariant.AMERICAN,
        status="not_started",
    )
    container._source_repo.save_source(source)

    # 3. Passages
    raw = json.loads((_FIXTURES / "passage_generation_response.json").read_text(encoding="utf-8"))
    raw_passages = raw["passages"]
    if max_passages is not None:
        raw_passages = raw_passages[:max_passages]

    passages: list[Passage] = []
    for p in raw_passages:
        raw_sentences = p["sentences"]
        if max_sentences is not None:
            raw_sentences = raw_sentences[:max_sentences]
        sentences = tuple(
            Sentence(
                order=i,
                ja=s["ja"],
                en=s["en"],
                hints=Hint(hint1=s["hints"]["hint1"], hint2=s["hints"]["hint2"]),
            )
            for i, s in enumerate(raw_sentences)
        )
        passages.append(
            Passage(
                source_id=source.id,
                order=p["passage_index"],
                topic=p["topic"],
                passage_type=p["passage_type"],
                sentences=sentences,
            )
        )
    container._source_repo.save_passages(passages)

    # 3b. Sentence feedback (optional — needed for Phase C seeding)
    if seed_feedback:
        for passage in passages:
            for sentence in passage.sentences:
                feedback = SentenceFeedback(
                    sentence_id=sentence.id,
                    user_utterance=sentence.en,
                    model_answer=sentence.en,
                    is_acceptable=True,
                )
                container._feedback_repo.save_feedback(feedback)

    # 3c. Model audio (optional — pre-seeds TTS output for Phase C)
    if seed_model_audio:
        for passage in passages:
            _seed_model_audio_for_passage(passage, container)

    # 4. Session menu (pattern "c" — new material only, no reviews on day 1)
    today = date.today()
    blocks = compose_blocks(
        pattern="c",
        review_item_ids=[],
        passage_ids=[passages[0].id],
        config=SessionConfig(),
    )
    menu = SessionMenu(
        target_date=today,
        pattern="c",
        blocks=blocks,
        source_id=source.id,
        confirmed=True,
    )
    container._session_repo.save_menu(menu)

    logger.info(
        "seed_day1_done",
        source_id=str(source.id),
        passage_count=len(passages),
        menu_id=str(menu.id),
    )


def _seed_model_audio_for_passage(passage: Passage, container: Container) -> None:
    """Generate synthetic model audio with word timestamps for a passage."""
    sentence_texts = tuple(s.en for s in passage.sentences)
    all_words = " ".join(sentence_texts).split()

    # Build word timestamps (0.3s per word)
    timestamps: list[WordTimestamp] = []
    t = 0.0
    for word in all_words:
        timestamps.append(WordTimestamp(word=word, start_seconds=t, end_seconds=t + 0.3))
        t += 0.35

    duration = t if timestamps else 1.0

    # Generate silent WAV
    sample_rate = 16000
    n_samples = int(duration * sample_rate)
    buf = BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{n_samples}h", *([0] * n_samples)))

    audio = AudioData(
        data=buf.getvalue(),
        format="wav",
        sample_rate=sample_rate,
        channels=1,
        sample_width=2,
        duration_seconds=duration,
    )

    model_audio = ModelAudio(
        passage_id=passage.id,
        audio=audio,
        word_timestamps=tuple(timestamps),
        sentence_texts=sentence_texts,
    )
    container._practice_repo.save_model_audio(model_audio)
