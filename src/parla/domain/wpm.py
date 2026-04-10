"""WPM calculation and Phase C skip logic — pure functions."""

CEFR_WPM_TARGETS: dict[str, tuple[int, int]] = {
    "A2": (90, 100),
    "B1": (110, 130),
    "B2": (140, 170),
    "C1": (180, 200),
}


def calculate_wpm(word_count: int, duration_seconds: float) -> float:
    """Calculate words per minute from word count and duration."""
    if duration_seconds <= 0:
        return 0.0
    return word_count / duration_seconds * 60


def calculate_time_limit(word_count: int, cefr_level: str, buffer_ratio: float = 1.2) -> float:
    """Calculate time limit in seconds based on CEFR target WPM.

    Uses the lower bound of the CEFR range as the target,
    then applies a buffer ratio for learner tolerance.
    """
    lower_wpm, _ = CEFR_WPM_TARGETS[cefr_level]
    base_seconds = word_count / lower_wpm * 60
    return base_seconds * buffer_ratio


def is_wpm_in_target(wpm: float, cefr_level: str) -> bool:
    """Check if WPM falls within the CEFR target range (inclusive)."""
    lower, upper = CEFR_WPM_TARGETS[cefr_level]
    return lower <= wpm <= upper


def should_skip_phase_c(new_item_count: int, wpm: float, cefr_level: str) -> bool:
    """Phase C is skippable when there are no new learning items AND WPM is in target range."""
    return new_item_count == 0 and is_wpm_in_target(wpm, cefr_level)
