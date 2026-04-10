"""Port for Block 1/3 review judgment.

Checks whether the target learning item pattern was used correctly.
Different from RetryJudgmentPort which checks model answer reproduction.
"""

from typing import Protocol

from parla.domain.review import ReviewResult


class ReviewJudgmentPort(Protocol):
    """Judges whether a review utterance uses the target learning item."""

    async def judge(
        self,
        audio_data: bytes,
        audio_format: str,
        target_pattern: str,
        reference_answer: str,
        ja_prompt: str,
        cefr_level: str,
    ) -> ReviewResult: ...
