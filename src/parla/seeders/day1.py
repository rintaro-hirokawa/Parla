"""Day 1 state seeder — fresh start with Toyota source and passages ready."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from parla.adapters.sqlite_db import reset_db
from parla.domain.passage import Hint, Passage, Sentence
from parla.domain.session import SessionConfig, SessionMenu, compose_blocks
from parla.domain.source import CEFRLevel, EnglishVariant, Source
from parla.domain.user_settings import UserSettings

if TYPE_CHECKING:
    from parla.ui.container import Container

logger = structlog.get_logger()

_FIXTURES = Path(__file__).parent / "fixtures"


def seed(
    container: Container,
    *,
    max_passages: int | None = None,
    max_sentences: int | None = None,
) -> None:
    """Reset DB and seed day-1 state: settings, source, passages, confirmed menu."""
    logger.info("seed_day1_start")

    reset_db(container.conn)

    # 1. User settings
    settings = UserSettings(cefr_level=CEFRLevel.A2, english_variant=EnglishVariant.AMERICAN)
    container.settings_repo.save(settings)

    # 2. Source
    source_text = (_FIXTURES / "sample_01.txt").read_text(encoding="utf-8")
    source = Source(
        text=source_text,
        cefr_level=CEFRLevel.A2,
        english_variant=EnglishVariant.AMERICAN,
        status="not_started",
    )
    container.source_repo.save_source(source)

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
    container.source_repo.save_passages(passages)

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
    container.session_repo.save_menu(menu)

    logger.info(
        "seed_day1_done",
        source_id=str(source.id),
        passage_count=len(passages),
        menu_id=str(menu.id),
    )
