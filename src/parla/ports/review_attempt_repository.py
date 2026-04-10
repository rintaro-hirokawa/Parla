"""Port for persisting review attempts (Block 1/3)."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from parla.domain.review import ReviewAttempt


class ReviewAttemptRepository(Protocol):
    """Storage for Block 1/3 review attempt records."""

    def save_attempt(self, attempt: ReviewAttempt) -> None: ...

    def get_attempts_by_variation(self, variation_id: UUID) -> Sequence[ReviewAttempt]: ...
