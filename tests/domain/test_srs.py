"""TDD tests for SRS interval calculation.

Requirements source: 06-srs-mastery.md
- 7 stages with fixed intervals: [0, 1, 3, 7, 14, 30, 60] days
- Correct: advance stage, apply ease_factor
- Incorrect: regress 1 stage (min 0)
- Stage 6 is max, stage 0 is min
"""

from datetime import date

from parla.domain.srs import SRSConfig, calculate_next_review


class TestSRSConfig:
    def test_default_intervals(self) -> None:
        config = SRSConfig()
        assert config.intervals == (0, 1, 3, 7, 14, 30, 60)

    def test_custom_intervals(self) -> None:
        config = SRSConfig(intervals=(0, 1, 2, 5))
        assert config.intervals == (0, 1, 2, 5)

    def test_immutable(self) -> None:
        config = SRSConfig()
        assert config.model_config.get("frozen") is True


class TestCorrectAnswer:
    """Correct answer: advance stage, apply interval * ease."""

    def test_stage0_to_stage1(self) -> None:
        result = calculate_next_review(
            current_stage=0,
            correct=True,
            ease_factor=1.0,
            today=date(2026, 4, 10),
            config=SRSConfig(),
        )
        assert result.new_stage == 1
        # interval[1] * 1.0 = 1 day
        assert result.next_review_date == date(2026, 4, 11)

    def test_stage1_to_stage2(self) -> None:
        result = calculate_next_review(
            current_stage=1,
            correct=True,
            ease_factor=1.0,
            today=date(2026, 4, 10),
            config=SRSConfig(),
        )
        assert result.new_stage == 2
        # interval[2] * 1.0 = 3 days
        assert result.next_review_date == date(2026, 4, 13)

    def test_stage5_to_stage6(self) -> None:
        result = calculate_next_review(
            current_stage=5,
            correct=True,
            ease_factor=1.0,
            today=date(2026, 4, 10),
            config=SRSConfig(),
        )
        assert result.new_stage == 6
        # interval[6] * 1.0 = 60 days
        assert result.next_review_date == date(2026, 6, 9)


class TestIncorrectAnswer:
    """Incorrect: regress 1 stage."""

    def test_stage3_regress_to_2(self) -> None:
        result = calculate_next_review(
            current_stage=3,
            correct=False,
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
            ease_factor=1.0,
            today=date(2026, 4, 10),
            config=SRSConfig(),
        )
        assert result.new_stage == 0
        assert result.next_review_date == date(2026, 4, 10)


class TestStageBoundaries:
    """Stage upper/lower bounds."""

    def test_max_stage_stays_at_max(self) -> None:
        result = calculate_next_review(
            current_stage=6,
            correct=True,
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
            ease_factor=1.5,
            today=date(2026, 4, 10),
            config=SRSConfig(),
        )
        assert result.new_stage == 3
        # interval[3] * 1.5 = 7 * 1.5 = 10.5 -> 11 days
        assert result.next_review_date == date(2026, 4, 21)


class TestCustomConfig:
    """SRSConfig can override defaults for testing and tuning."""

    def test_custom_intervals(self) -> None:
        config = SRSConfig(intervals=(0, 2, 5))
        result = calculate_next_review(
            current_stage=1,
            correct=True,
            ease_factor=1.0,
            today=date(2026, 4, 10),
            config=config,
        )
        assert result.new_stage == 2
        # custom interval[2] = 5 days
        assert result.next_review_date == date(2026, 4, 15)
