"""Tests for SessionContext — shared session-level state holder."""

from parla.ui.screens.session.session_context import SessionContext


class TestInitialState:
    def test_initial_values(self, qtbot) -> None:
        ctx = SessionContext()

        assert ctx.block_name == ""
        assert ctx.progress_current == 0
        assert ctx.progress_total == 0
        assert ctx.elapsed_seconds == 0
        assert ctx.cumulative_word_count == 0
        assert ctx.average_wpm == 0.0

    def test_progress_label_empty_initially(self, qtbot) -> None:
        ctx = SessionContext()
        assert ctx.progress_label == ""


class TestUpdateProgress:
    def test_update_progress_emits_signal(self, qtbot) -> None:
        ctx = SessionContext()

        with qtbot.waitSignal(ctx.progress_changed, timeout=1000):
            ctx.update_progress("ブロック1 復習", 3, 20)

        assert ctx.block_name == "ブロック1 復習"
        assert ctx.progress_current == 3
        assert ctx.progress_total == 20

    def test_progress_label_format(self, qtbot) -> None:
        ctx = SessionContext()
        ctx.update_progress("ブロック1 復習", 8, 20)
        assert ctx.progress_label == "ブロック1 復習 (8/20)"

    def test_progress_label_zero_total(self, qtbot) -> None:
        ctx = SessionContext()
        ctx.update_progress("ブロック2 新規素材", 0, 0)
        assert ctx.progress_label == "ブロック2 新規素材"


class TestWordCount:
    def test_add_words_accumulates(self, qtbot) -> None:
        ctx = SessionContext()

        ctx.add_words(10)
        assert ctx.cumulative_word_count == 10

        with qtbot.waitSignal(ctx.words_changed, timeout=1000):
            ctx.add_words(5)

        assert ctx.cumulative_word_count == 15

    def test_wpm_updates_after_adding_words(self, qtbot) -> None:
        ctx = SessionContext()

        # Simulate 60 seconds elapsed
        ctx._elapsed_seconds = 60
        ctx.add_words(120)
        assert ctx.average_wpm == 120.0  # 120 words / 1 minute

    def test_wpm_zero_when_no_time(self, qtbot) -> None:
        ctx = SessionContext()
        ctx.add_words(50)
        assert ctx.average_wpm == 0.0


class TestTimer:
    def test_start_timer(self, qtbot) -> None:
        ctx = SessionContext()

        ctx.start_timer()
        assert ctx.is_running is True
        ctx.stop_timer()

    def test_stop_timer(self, qtbot) -> None:
        ctx = SessionContext()

        ctx.start_timer()
        ctx.stop_timer()
        assert ctx.is_running is False

    def test_timer_ticks(self, qtbot) -> None:
        ctx = SessionContext()

        ctx.start_timer()
        with qtbot.waitSignal(ctx.elapsed_changed, timeout=2000):
            pass  # Wait for the first tick
        ctx.stop_timer()
        assert ctx.elapsed_seconds >= 1

    def test_elapsed_format(self, qtbot) -> None:
        ctx = SessionContext()

        ctx._elapsed_seconds = 0
        assert ctx.elapsed_display == "00:00"

        ctx._elapsed_seconds = 65
        assert ctx.elapsed_display == "01:05"

        ctx._elapsed_seconds = 3661
        assert ctx.elapsed_display == "61:01"


class TestReset:
    def test_reset_clears_all(self, qtbot) -> None:
        ctx = SessionContext()

        ctx.update_progress("ブロック1", 5, 10)
        ctx.add_words(100)
        ctx._elapsed_seconds = 120
        ctx.start_timer()

        ctx.reset()

        assert ctx.block_name == ""
        assert ctx.progress_current == 0
        assert ctx.progress_total == 0
        assert ctx.elapsed_seconds == 0
        assert ctx.cumulative_word_count == 0
        assert ctx.average_wpm == 0.0
        assert ctx.is_running is False
