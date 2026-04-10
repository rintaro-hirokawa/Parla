"""TDD tests for SRS interval calculation.

Requirements source: 06-srs-mastery.md
- 7 stages with fixed intervals: [0, 1, 3, 7, 14, 30, 60] days
- Correct: advance stage, apply confidence multiplier
- Incorrect: regress 1 stage (min 0)
- Timer 80%+ consumed but correct: don't advance
- Hint confidence: no hint=1.0, hint1=0.7, hint2=0.4
- Stage 6 is max, stage 0 is min
"""

from datetime import date

from parla.domain.srs import SRSConfig, calculate_next_review


class TestSRSConfig:
    def test_default_intervals(self) -> None:
        config = SRSConfig()
        assert config.intervals == (0, 1, 3, 7, 14, 30, 60)

    def test_default_confidence_multipliers(self) -> None:
        config = SRSConfig()
        assert config.confidence_multipliers == (1.0, 0.7, 0.4)

    def test_default_timer_threshold(self) -> None:
        config = SRSConfig()
        assert config.timer_penalty_threshold == 0.8

    def test_custom_intervals(self) -> None:
        config = SRSConfig(intervals=(0, 1, 2, 5))
        assert config.intervals == (0, 1, 2, 5)

    def test_immutable(self) -> None:
        config = SRSConfig()
        assert config.model_config.get("frozen") is True


class TestCorrectAnswer:
    """Correct answer: advance stage, apply interval * ease * confidence."""

    def test_stage0_to_stage1_no_hint(self) -> None:
        result = calculate_next_review(
            current_stage=0,
            correct=True,
            hint_level=0,
            timer_ratio=0.5,
            ease_factor=1.0,
            today=date(2026, 4, 10),
            config=SRSConfig(),
        )
        assert result.new_stage == 1
        # interval[1] * 1.0 * 1.0 = 1 day
        assert result.next_review_date == date(2026, 4, 11)

    def test_stage1_to_stage2_no_hint(self) -> None:
        result = calculate_next_review(
            current_stage=1,
            correct=True,
            hint_level=0,
            timer_ratio=0.3,
            ease_factor=1.0,
            today=date(2026, 4, 10),
            config=SRSConfig(),
        )
        assert result.new_stage == 2
        # interval[2] * 1.0 * 1.0 = 3 days
        assert result.next_review_date == date(2026, 4, 13)

    def test_stage5_to_stage6_no_hint(self) -> None:
        result = calculate_next_review(
            current_stage=5,
            correct=True,
            hint_level=0,
            timer_ratio=0.5,
            ease_factor=1.0,
            today=date(2026, 4, 10),
            config=SRSConfig(),
        )
        assert result.new_stage == 6
        # interval[6] * 1.0 * 1.0 = 60 days
        assert result.next_review_date == date(2026, 6, 9)


class TestCorrectWithHint:
    """Correct with hint: advance stage, but multiply interval by confidence."""

    def test_hint1_confidence_0_7(self) -> None:
        result = calculate_next_review(
            current_stage=1,
            correct=True,
            hint_level=1,
            timer_ratio=0.5,
            ease_factor=1.0,
            today=date(2026, 4, 10),
            config=SRSConfig(),
        )
        assert result.new_stage == 2
        # interval[2] * 1.0 * 0.7 = 3 * 0.7 = 2.1 -> ceil to 3 days
        assert result.next_review_date == date(2026, 4, 13)

    def test_hint2_confidence_0_4(self) -> None:
        result = calculate_next_review(
            current_stage=1,
            correct=True,
            hint_level=2,
            timer_ratio=0.5,
            ease_factor=1.0,
            today=date(2026, 4, 10),
            config=SRSConfig(),
        )
        assert result.new_stage == 2
        # interval[2] * 1.0 * 0.4 = 3 * 0.4 = 1.2 -> ceil to 2 days
        assert result.next_review_date == date(2026, 4, 12)

    def test_hint_with_high_stage(self) -> None:
        result = calculate_next_review(
            current_stage=4,
            correct=True,
            hint_level=1,
            timer_ratio=0.3,
            ease_factor=1.0,
            today=date(2026, 4, 10),
            config=SRSConfig(),
        )
        assert result.new_stage == 5
        # interval[5] * 1.0 * 0.7 = 30 * 0.7 = 21 days
        assert result.next_review_date == date(2026, 5, 1)


class TestTimerPenalty:
    """Timer 80%+ consumed: correct but don't advance stage."""

    def test_timer_exactly_80_percent(self) -> None:
        result = calculate_next_review(
            current_stage=2,
            correct=True,
            hint_level=0,
            timer_ratio=0.8,
            ease_factor=1.0,
            today=date(2026, 4, 10),
            config=SRSConfig(),
        )
        # Don't advance — too slow
        assert result.new_stage == 2
        # Stay at current interval: interval[2] = 3 days
        assert result.next_review_date == date(2026, 4, 13)

    def test_timer_90_percent(self) -> None:
        result = calculate_next_review(
            current_stage=1,
            correct=True,
            hint_level=0,
            timer_ratio=0.9,
            ease_factor=1.0,
            today=date(2026, 4, 10),
            config=SRSConfig(),
        )
        assert result.new_stage == 1
        # interval[1] = 1 day
        assert result.next_review_date == date(2026, 4, 11)

    def test_timer_79_percent_advances(self) -> None:
        result = calculate_next_review(
            current_stage=2,
            correct=True,
            hint_level=0,
            timer_ratio=0.79,
            ease_factor=1.0,
            today=date(2026, 4, 10),
            config=SRSConfig(),
        )
        # Should advance — under threshold
        assert result.new_stage == 3
        assert result.next_review_date == date(2026, 4, 17)


class TestIncorrectAnswer:
    """Incorrect: regress 1 stage."""

    def test_stage3_regress_to_2(self) -> None:
        result = calculate_next_review(
            current_stage=3,
            correct=False,
            hint_level=0,
            timer_ratio=0.5,
            ease_factor=1.0,
            today=date(2026, 4, 10),
            config=SRSConfig(),
        )
        assert result.new_stage == 2
        # interval[2] = 3 days
        assert result.next_review_date == date(2026, 4, 13)

    def test_stage1_regress_to_0(self) -> None:
        result = calculate_next_review(
            current_stage=1,
            correct=False,
            hint_level=0,
            timer_ratio=0.5,
            ease_factor=1.0,
            today=date(2026, 4, 10),
            config=SRSConfig(),
        )
        assert result.new_stage == 0
        # interval[0] = 0 days (same day)
        assert result.next_review_date == date(2026, 4, 10)

    def test_stage0_stays_at_0(self) -> None:
        result = calculate_next_review(
            current_stage=0,
            correct=False,
            hint_level=0,
            timer_ratio=0.5,
            ease_factor=1.0,
            today=date(2026, 4, 10),
            config=SRSConfig(),
        )
        assert result.new_stage == 0
        assert result.next_review_date == date(2026, 4, 10)

    def test_incorrect_ignores_hint_and_timer(self) -> None:
        """When incorrect, hint_level and timer_ratio don't matter."""
        result = calculate_next_review(
            current_stage=3,
            correct=False,
            hint_level=2,
            timer_ratio=0.9,
            ease_factor=1.0,
            today=date(2026, 4, 10),
            config=SRSConfig(),
        )
        assert result.new_stage == 2
        assert result.next_review_date == date(2026, 4, 13)


class TestStageBoundaries:
    """Stage upper/lower bounds."""

    def test_max_stage_stays_at_max(self) -> None:
        result = calculate_next_review(
            current_stage=6,
            correct=True,
            hint_level=0,
            timer_ratio=0.5,
            ease_factor=1.0,
            today=date(2026, 4, 10),
            config=SRSConfig(),
        )
        # Stage 6 is max — stays at 6
        assert result.new_stage == 6
        # interval[6] = 60 days
        assert result.next_review_date == date(2026, 6, 9)

    def test_max_stage_regress(self) -> None:
        result = calculate_next_review(
            current_stage=6,
            correct=False,
            hint_level=0,
            timer_ratio=0.5,
            ease_factor=1.0,
            today=date(2026, 4, 10),
            config=SRSConfig(),
        )
        assert result.new_stage == 5
        assert result.next_review_date == date(2026, 5, 10)


class TestEaseFactor:
    """ease_factor multiplies the interval."""

    def test_ease_factor_above_1(self) -> None:
        result = calculate_next_review(
            current_stage=2,
            correct=True,
            hint_level=0,
            timer_ratio=0.5,
            ease_factor=1.5,
            today=date(2026, 4, 10),
            config=SRSConfig(),
        )
        assert result.new_stage == 3
        # interval[3] * 1.5 * 1.0 = 7 * 1.5 = 10.5 -> 11 days
        assert result.next_review_date == date(2026, 4, 21)

    def test_ease_factor_with_hint(self) -> None:
        result = calculate_next_review(
            current_stage=2,
            correct=True,
            hint_level=1,
            timer_ratio=0.5,
            ease_factor=1.5,
            today=date(2026, 4, 10),
            config=SRSConfig(),
        )
        assert result.new_stage == 3
        # interval[3] * 1.5 * 0.7 = 7 * 1.05 = 7.35 -> ceil to 8 days
        assert result.next_review_date == date(2026, 4, 18)


class TestMinimumInterval:
    """Computed interval should never be less than 1 day (except stage 0)."""

    def test_very_low_confidence_still_at_least_1_day(self) -> None:
        result = calculate_next_review(
            current_stage=0,
            correct=True,
            hint_level=2,
            timer_ratio=0.5,
            ease_factor=1.0,
            today=date(2026, 4, 10),
            config=SRSConfig(),
        )
        assert result.new_stage == 1
        # interval[1] * 1.0 * 0.4 = 0.4 -> max(1, 0) = 1 day
        assert result.next_review_date == date(2026, 4, 11)


class TestCustomConfig:
    """SRSConfig can override defaults for testing and tuning."""

    def test_custom_intervals(self) -> None:
        config = SRSConfig(intervals=(0, 2, 5))
        result = calculate_next_review(
            current_stage=1,
            correct=True,
            hint_level=0,
            timer_ratio=0.5,
            ease_factor=1.0,
            today=date(2026, 4, 10),
            config=config,
        )
        assert result.new_stage == 2
        # custom interval[2] = 5 days
        assert result.next_review_date == date(2026, 4, 15)

    def test_custom_timer_threshold(self) -> None:
        config = SRSConfig(timer_penalty_threshold=0.9)
        result = calculate_next_review(
            current_stage=1,
            correct=True,
            hint_level=0,
            timer_ratio=0.85,
            ease_factor=1.0,
            today=date(2026, 4, 10),
            config=config,
        )
        # 0.85 < 0.9, so should advance
        assert result.new_stage == 2

    def test_custom_confidence_multipliers(self) -> None:
        config = SRSConfig(confidence_multipliers=(1.0, 0.5, 0.2))
        result = calculate_next_review(
            current_stage=1,
            correct=True,
            hint_level=1,
            timer_ratio=0.5,
            ease_factor=1.0,
            today=date(2026, 4, 10),
            config=config,
        )
        assert result.new_stage == 2
        # interval[2] * 1.0 * 0.5 = 3 * 0.5 = 1.5 -> 2 days
        assert result.next_review_date == date(2026, 4, 12)
