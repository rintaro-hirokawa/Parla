"""Parla application entry point."""

import sys
from datetime import date

import structlog
from PySide6 import QtAsyncio
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

from parla.ui.container import Container
from parla.ui.navigation import NavigationController

logger = structlog.get_logger()

_TAB_TITLES = ("Today's Learning", "Learning Items", "History", "Settings")


class MainWindow(QMainWindow):
    """Main application window with navigation controller."""

    def __init__(self, container: Container, parent: None = None) -> None:
        super().__init__(parent)
        self._container = container

        self.setWindowTitle("Parla")
        self.resize(400, 700)

        self._nav = NavigationController()
        self.setCentralWidget(self._nav)

        # Placeholder widgets for each tab (replaced by real screens later)
        for i, title in enumerate(_TAB_TITLES):
            self._nav.set_tab_widget(i, QLabel(title))

    @property
    def navigation(self) -> NavigationController:
        return self._nav

    def closeEvent(self, event: QCloseEvent) -> None:
        self._container.close()
        super().closeEvent(event)


def main() -> None:
    """Launch the Parla application."""
    _app = QApplication(sys.argv)  # noqa: F841 — must stay alive for Qt event loop

    container = Container()

    # Log EventBus handler registry (event-driven "map")
    for reg in container.event_bus.get_registry():
        for handler in reg.handlers:
            logger.info(
                "handler_registered",
                event=reg.event_name,
                handler=handler.name,
                kind=handler.kind,
            )

    # Determine startup routing
    bootstrap = container.app_state_query.get_bootstrap_state(today=date.today())
    logger.info(
        "bootstrap_state",
        needs_setup=bootstrap.needs_setup,
        has_resumable_session=bootstrap.has_resumable_session,
        has_today_menu=bootstrap.has_today_menu,
    )

    window = MainWindow(container)

    # Initial routing (placeholder — real screen navigation in future tasks)
    if bootstrap.needs_setup:
        pass  # TODO: show setup screen (SCREEN-B)
    elif bootstrap.has_resumable_session:
        pass  # TODO: show resume dialog

    window.show()

    QtAsyncio.run(handle_sigint=True)
