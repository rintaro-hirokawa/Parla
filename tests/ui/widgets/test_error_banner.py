"""Tests for ErrorBanner widget."""

from parla.ui.widgets.error_banner import ErrorBanner


class TestErrorBannerInitialState:
    def test_hidden_by_default(self, qtbot) -> None:
        banner = ErrorBanner()
        qtbot.addWidget(banner)
        assert banner.isHidden()

    def test_message_empty_initially(self, qtbot) -> None:
        banner = ErrorBanner()
        qtbot.addWidget(banner)
        assert banner.message == ""


class TestShowAndClear:
    def test_show_error_makes_visible(self, qtbot) -> None:
        banner = ErrorBanner()
        qtbot.addWidget(banner)

        banner.show_error("something went wrong")

        assert banner.isVisible()
        assert banner.message == "something went wrong"

    def test_clear_hides_banner(self, qtbot) -> None:
        banner = ErrorBanner()
        qtbot.addWidget(banner)

        banner.show_error("error")
        banner.clear()

        assert banner.isHidden()
        assert banner.message == ""

    def test_show_error_updates_message(self, qtbot) -> None:
        banner = ErrorBanner()
        qtbot.addWidget(banner)

        banner.show_error("first")
        banner.show_error("second")

        assert banner.message == "second"


class TestRetryButton:
    def test_retry_button_present_when_retryable(self, qtbot) -> None:
        banner = ErrorBanner(retryable=True)
        qtbot.addWidget(banner)

        assert banner._retry_button is not None
        assert banner.retryable is True

    def test_retry_button_absent_when_not_retryable(self, qtbot) -> None:
        banner = ErrorBanner(retryable=False)
        qtbot.addWidget(banner)

        assert banner._retry_button is None
        assert banner.retryable is False

    def test_retry_clicked_signal_emitted(self, qtbot) -> None:
        banner = ErrorBanner(retryable=True)
        qtbot.addWidget(banner)
        banner.show_error("error")

        with qtbot.waitSignal(banner.retry_clicked, timeout=1000):
            banner._retry_button.click()

    def test_default_is_not_retryable(self, qtbot) -> None:
        banner = ErrorBanner()
        qtbot.addWidget(banner)
        assert banner.retryable is False
        assert banner._retry_button is None
