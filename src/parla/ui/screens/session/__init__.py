"""Session screens package."""

from enum import StrEnum

MAX_RETRY = 3


class FeedbackMode(StrEnum):
    """Determines which events FeedbackViewModel subscribes to."""

    NEW_MATERIAL = "new_material"
    REVIEW = "review"
