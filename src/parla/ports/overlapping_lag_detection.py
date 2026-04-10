"""Port for overlapping lag detection (LLM call #7)."""

from typing import Protocol

from parla.domain.lag_detection import DelayedPhrase, LagDetectionResult


class OverlappingLagDetectionPort(Protocol):
    """Estimates causes of delayed phrases during overlapping practice."""

    async def detect(
        self,
        passage_text: str,
        delayed_phrases: list[DelayedPhrase],
    ) -> LagDetectionResult: ...
