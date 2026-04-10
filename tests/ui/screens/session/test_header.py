"""Tests for SessionHeaderWidget."""

from parla.ui.screens.session.header import SessionHeaderWidget
from parla.ui.screens.session.session_context import SessionContext


class TestDisplay:
    def test_initial_labels_empty(self, qtbot) -> None:
        ctx = SessionContext()
        header = SessionHeaderWidget(ctx)
        qtbot.addWidget(header)

        assert header.progress_text() == ""
        assert header.elapsed_text() == "00:00"
        assert header.word_count_text() == "0 words"
        assert header.wpm_text() == "0.0 WPM"

    def test_progress_label_updates(self, qtbot) -> None:
        ctx = SessionContext()
        header = SessionHeaderWidget(ctx)
        qtbot.addWidget(header)

        ctx.update_progress("ブロック1 復習", 8, 20)
        assert header.progress_text() == "ブロック1 復習 (8/20)"

    def test_elapsed_label_updates(self, qtbot) -> None:
        ctx = SessionContext()
        header = SessionHeaderWidget(ctx)
        qtbot.addWidget(header)

        ctx._elapsed_seconds = 125
        ctx.elapsed_changed.emit(125)
        assert header.elapsed_text() == "02:05"

    def test_word_count_label_updates(self, qtbot) -> None:
        ctx = SessionContext()
        header = SessionHeaderWidget(ctx)
        qtbot.addWidget(header)

        ctx.add_words(42)
        assert header.word_count_text() == "42 words"

    def test_wpm_label_updates(self, qtbot) -> None:
        ctx = SessionContext()
        header = SessionHeaderWidget(ctx)
        qtbot.addWidget(header)

        ctx._elapsed_seconds = 60
        ctx.add_words(150)
        assert header.wpm_text() == "150.0 WPM"


class TestRenderNoCrash:
    def test_show_no_crash(self, qtbot) -> None:
        ctx = SessionContext()
        header = SessionHeaderWidget(ctx)
        qtbot.addWidget(header)
        header.show()
        qtbot.waitExposed(header)
