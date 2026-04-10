"""Shared helper for generating and saving a variation."""

from parla.domain.learning_item import LearningItem
from parla.domain.source import Source
from parla.domain.variation import Variation
from parla.ports.variation_generation import PastVariationInfo, VariationGenerationPort
from parla.ports.variation_repository import VariationRepository

_MAX_HISTORY_FOR_PROMPT = 10


async def generate_and_save_variation(
    item: LearningItem,
    source: Source,
    variation_repo: VariationRepository,
    variation_generator: VariationGenerationPort,
) -> Variation:
    """Generate a variation for a learning item and save it.

    Raises on generation failure — caller handles the exception.
    """
    past_variations = variation_repo.get_variations_by_item(item.id)
    past_info = [PastVariationInfo(ja=v.ja, en=v.en) for v in past_variations[-_MAX_HISTORY_FOR_PROMPT:]]

    raw = await variation_generator.generate_variation(
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
    variation_repo.save_variation(variation)
    return variation
