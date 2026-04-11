"""Tests for StatusBadgeWidget."""

from parla.ui.widgets.status_badge_widget import StatusBadgeWidget


class TestStatusBadgeWidget:
    def test_set_correct(self, qtbot) -> None:
        w = StatusBadgeWidget()
        qtbot.addWidget(w)
        w.set_status("correct", "OK")
        assert w.text() == "OK"

    def test_set_needs_review(self, qtbot) -> None:
        w = StatusBadgeWidget()
        qtbot.addWidget(w)
        w.set_status("needs-review", "NG")
        assert w.text() == "NG"

    def test_set_loading(self, qtbot) -> None:
        w = StatusBadgeWidget()
        qtbot.addWidget(w)
        w.set_status("loading", "...")
        assert w.text() == "..."
