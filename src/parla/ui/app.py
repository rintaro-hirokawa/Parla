"""Parla application entry point."""

import sys
from datetime import date
from uuid import UUID

import structlog
from PySide6 import QtAsyncio
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget

from parla.ui import theme
from parla.ui.base_view_model import BaseViewModel
from parla.ui.container import Container
from parla.ui.navigation import NavigationController
from parla.ui.screens.history.view import HistoryView
from parla.ui.screens.history.view_model import HistoryViewModel
from parla.ui.screens.items.detail_view import DetailView
from parla.ui.screens.items.detail_view_model import DetailViewModel
from parla.ui.screens.items.list_view import ListView
from parla.ui.screens.items.list_view_model import ListViewModel
from parla.ui.screens.session.coordinator import SessionCoordinator
from parla.ui.screens.settings.view import SettingsView
from parla.ui.screens.settings.view_model import SettingsViewModel
from parla.ui.screens.setup.view import SetupView
from parla.ui.screens.setup.view_model import SetupViewModel
from parla.ui.screens.sources.list_view import SourceListView
from parla.ui.screens.sources.list_view_model import SourceListViewModel
from parla.ui.screens.sources.registration_view import SourceRegistrationView
from parla.ui.screens.sources.registration_view_model import SourceRegistrationViewModel
from parla.ui.screens.today.view import TodayView
from parla.ui.screens.today.view_model import TodayViewModel

logger = structlog.get_logger()

TAB_TITLES = ("Today's Learning", "Learning Items", "History", "Settings")


class MainWindow(QMainWindow):
    """Main application window with navigation controller."""

    def __init__(self, container: Container, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._container = container
        self._pushed_vms: list[BaseViewModel] = []
        self._coordinator: SessionCoordinator | None = None

        self.setWindowTitle("Parla")
        self.resize(*theme.WINDOW_INITIAL_SIZE)
        self.setMinimumSize(*theme.WINDOW_MIN_SIZE)

        self._nav = NavigationController(TAB_TITLES)
        self.setCentralWidget(self._nav)

        self._today_vm = TodayViewModel(container.event_bus, container.session_query)
        self._items_vm = ListViewModel(container.event_bus, container.item_query)
        self._history_vm = HistoryViewModel(container.event_bus, container.history_query)
        self._settings_vm = SettingsViewModel(container.event_bus, container.settings_service)

        today_view = TodayView(self._today_vm)
        items_view = ListView(self._items_vm)
        history_view = HistoryView(self._history_vm)
        settings_view = SettingsView(self._settings_vm)

        self._nav.set_tab_widget(NavigationController.TAB_TODAY, today_view)
        self._nav.set_tab_widget(NavigationController.TAB_ITEMS, items_view)
        self._nav.set_tab_widget(NavigationController.TAB_HISTORY, history_view)
        self._nav.set_tab_widget(NavigationController.TAB_SETTINGS, settings_view)

        self._settings_vm.navigate_to_sources.connect(self._push_source_list)
        self._today_vm.start_session_requested.connect(self._enter_session)
        self._today_vm.navigate_to_source_registration.connect(self._push_source_registration)
        self._items_vm.navigate_to_detail.connect(self._push_item_detail)

        self._settings_vm.activate()
        self._settings_vm.load_settings()
        self._today_vm.activate()
        self._today_vm.load_dashboard()
        self._items_vm.activate()
        self._items_vm.load_items()
        self._history_vm.activate()
        self._history_vm.load_overview()

    @property
    def navigation(self) -> NavigationController:
        return self._nav

    def show_setup(self) -> None:
        """Show the initial setup screen."""
        setup_vm = SetupViewModel(self._container.event_bus, self._container.settings_service)
        setup_view = SetupView(setup_vm)
        setup_vm.setup_completed.connect(lambda: self._finish_setup(setup_view, setup_vm))
        self._nav.set_tab_widget(NavigationController.TAB_TODAY, setup_view)
        self._nav.switch_tab(NavigationController.TAB_TODAY)
        self._nav.set_tabs_visible(False)

    def _finish_setup(self, setup_view: SetupView, setup_vm: SetupViewModel) -> None:
        """Complete setup: replace setup screen with today view, show tabs."""
        setup_vm.deactivate()
        today_view = TodayView(self._today_vm)
        self._nav.set_tab_widget(NavigationController.TAB_TODAY, today_view)
        self._nav.set_tabs_visible(True)
        self._nav.switch_tab(NavigationController.TAB_TODAY)
        self._today_vm.load_dashboard()
        setup_view.deleteLater()

    def _push_screen_with_vm(self, view: QWidget, vm: BaseViewModel) -> None:
        """Push a screen and track its ViewModel for lifecycle management."""
        self._pushed_vms.append(vm)
        view.destroyed.connect(lambda: self._on_pushed_view_destroyed(vm))
        vm.activate()
        self._nav.push_screen(view)

    def _on_pushed_view_destroyed(self, vm: BaseViewModel) -> None:
        """Deactivate ViewModel when its View is destroyed (popped)."""
        vm.deactivate()
        if vm in self._pushed_vms:
            self._pushed_vms.remove(vm)

    def _push_item_detail(self, item_id: object) -> None:
        """Push item detail screen onto items tab stack."""
        assert isinstance(item_id, UUID)
        vm = DetailViewModel(self._container.event_bus, self._container.item_query)
        view = DetailView(vm)
        vm.navigate_back.connect(lambda: self._nav.pop_screen())
        vm.load_detail(item_id)
        self._push_screen_with_vm(view, vm)

    def _push_source_list(self) -> None:
        """Push source list screen onto settings tab stack."""
        vm = SourceListViewModel(self._container.event_bus, self._container.source_query)
        view = SourceListView(vm)
        vm.navigate_to_registration.connect(self._push_source_registration)
        vm.load_sources()
        self._push_screen_with_vm(view, vm)

    def _push_source_registration(self) -> None:
        """Push source registration screen."""
        vm = SourceRegistrationViewModel(
            self._container.event_bus,
            self._container.source_service,
            self._container.settings_service,
        )
        view = SourceRegistrationView(vm)
        vm.navigate_back.connect(lambda: self._nav.pop_screen())
        vm.load_settings()
        self._push_screen_with_vm(view, vm)

    def _enter_session(self) -> None:
        """Enter session mode via the SessionCoordinator."""
        dashboard = self._today_vm.dashboard
        if dashboard is None:
            return

        self._coordinator = SessionCoordinator(
            nav=self._nav,
            container=self._container,
        )
        self._coordinator.session_finished.connect(self._on_session_finished)

        if dashboard.has_resumable_session and dashboard.resumable_session_id:
            logger.info("session_resume", session_id=str(dashboard.resumable_session_id))
            self._coordinator.start_resumed(dashboard.resumable_session_id)
        elif dashboard.menu_id:
            logger.info("session_start", menu_id=str(dashboard.menu_id))
            self._coordinator.start(dashboard.menu_id)

    def _on_session_finished(self) -> None:
        """Clean up coordinator and refresh dashboard."""
        self._coordinator = None
        self._today_vm.load_dashboard()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._coordinator is not None:
            self._coordinator.interrupt()
            self._coordinator = None
        self._today_vm.deactivate()
        self._items_vm.deactivate()
        self._history_vm.deactivate()
        self._settings_vm.deactivate()
        for vm in self._pushed_vms:
            vm.deactivate()
        self._pushed_vms.clear()
        self._container.close()
        super().closeEvent(event)


def main(*, state: str | None = None) -> None:
    """Launch the Parla application."""
    _app = QApplication(sys.argv)  # noqa: F841 — must stay alive for Qt event loop
    _app.setStyleSheet(theme.build_app_qss())

    container = Container()

    if state:
        from parla.seeders import apply_state

        apply_state(state, container)

    # Log EventBus handler registry (event-driven "map")
    for reg in container.event_bus.get_registry():
        for handler in reg.handlers:
            logger.info(
                "handler_registered",
                event_name=reg.event_name,
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

    # Initial routing
    if bootstrap.needs_setup:
        window.show_setup()

    window.show()

    QtAsyncio.run(handle_sigint=True)
