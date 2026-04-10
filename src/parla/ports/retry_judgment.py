"""Port for immediate retry judgment in Phase B."""

from typing import Protocol

from parla.domain.feedback import RetryResult


class RetryJudgmentPort(Protocol):
    """Judges whether a retry utterance matches the reference answer."""

    async def judge(
        self,
        audio_data: bytes,
        audio_format: str,
        reference_answer: str,
    ) -> RetryResult: ...
