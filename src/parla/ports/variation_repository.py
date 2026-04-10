"""Port for persisting variations (practice questions)."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from parla.domain.variation import Variation


class VariationRepository(Protocol):
    """Storage for generated variations."""

    def save_variation(self, variation: Variation) -> None: ...

    def get_variation(self, variation_id: UUID) -> Variation | None: ...

    def get_variations_by_item(self, item_id: UUID) -> Sequence[Variation]: ...
