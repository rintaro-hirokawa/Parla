"""Port for passage generation from source text."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from parla.domain.passage import Passage


class PassageGenerationPort(Protocol):
    """Generates learning passages from source text via LLM."""

    async def generate(
        self,
        source_id: UUID,
        source_text: str,
        cefr_level: str,
        english_variant: str,
    ) -> Sequence[Passage]: ...
