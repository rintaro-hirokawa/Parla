"""Port for sentence feedback and practice attempt persistence."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from parla.domain.feedback import PracticeAttempt, SentenceFeedback


class FeedbackRepository(Protocol):
    """Persists feedback results and retry practice attempts."""

    def save_feedback(self, feedback: SentenceFeedback) -> None: ...

    def get_feedback_by_sentence(self, sentence_id: UUID) -> SentenceFeedback | None: ...

    def save_practice_attempt(self, attempt: PracticeAttempt) -> None: ...

    def get_attempts_by_sentence(self, sentence_id: UUID) -> Sequence[PracticeAttempt]: ...
