"""Day 1 start-review state seeder — phases A/B/C done, review block ready."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import structlog

from parla.domain.feedback import SentenceFeedback
from parla.domain.learning_item import LearningItem
from parla.domain.session import SessionConfig, SessionMenu, compose_blocks
from parla.seeders.day1 import seed as seed_day1

if TYPE_CHECKING:
    from parla.ui.container import Container

logger = structlog.get_logger()


def seed(container: Container) -> None:
    """Seed day-1 state with passage 1 completed and 2 stocked learning items.

    Sets up a pattern "a" menu so the session starts with the review block.
    """
    logger.info("seed_day1_start_review_start")

    # 1. Base day-1 with 2 passages, no feedback yet
    seed_day1(container, max_passages=2, seed_feedback=False)

    # 2. Retrieve seeded source and passages
    sources = list(container.source_repo.get_active_sources())
    source = sources[0]
    passages = list(container.source_repo.get_passages_by_source(source.id))
    passage_1 = passages[0]
    passage_2 = passages[1]

    # 3. Seed feedback for passage 1 only (simulates completed A→B→C)
    for sentence in passage_1.sentences:
        feedback = SentenceFeedback(
            sentence_id=sentence.id,
            user_utterance=sentence.en,
            model_answer=sentence.en,
            is_acceptable=True,
        )
        container.feedback_repo.save_feedback(feedback)

    # 4. Create 2 learning items (auto_stocked, due today)
    today = date.today()
    items = [
        LearningItem(
            pattern="present tense third-person -s",
            explanation="三人称単数現在の -s を付け忘れる傾向がある。",
            category="文法",
            priority=4,
            source_sentence_id=passage_1.sentences[0].id,
            status="auto_stocked",
            next_review_date=today,
        ),
        LearningItem(
            pattern="by himself / by myself",
            explanation="「自分で」を表す再帰代名詞 + by の表現が出てこない。",
            category="表現",
            priority=5,
            source_sentence_id=passage_1.sentences[1].id,
            status="auto_stocked",
            next_review_date=today,
        ),
    ]
    container.item_repo.save_items(items)

    # 5. Compose pattern "a" menu (review → new_material → consolidation)
    blocks = compose_blocks(
        pattern="a",
        review_item_ids=[items[0].id, items[1].id],
        passage_ids=[passage_2.id],
        config=SessionConfig(),
    )
    menu = SessionMenu(
        target_date=today,
        pattern="a",
        blocks=blocks,
        source_id=source.id,
        confirmed=True,
        pending_review_count=2,
    )
    container.session_repo.save_menu(menu)

    logger.info(
        "seed_day1_start_review_done",
        source_id=str(source.id),
        item_count=len(items),
        menu_id=str(menu.id),
        menu_pattern=menu.pattern,
    )
