"""Tests for NavigationController."""

import pytest
from PySide6.QtWidgets import QLabel, QWidget

from parla.ui.navigation import NavigationController

_TAB_TITLES = ("Today", "Items", "History", "Settings")


@pytest.fixture()
def nav_with_tabs(qtbot) -> tuple[NavigationController, list[QWidget]]:
    nav = NavigationController(_TAB_TITLES)
    qtbot.addWidget(nav)
    tabs = [QLabel(t) for t in _TAB_TITLES]
    for i, w in enumerate(tabs):
        nav.set_tab_widget(i, w)
    return nav, tabs


class TestTabSwitching:
    def test_initial_tab_is_zero(self, qtbot) -> None:
        nav = NavigationController(_TAB_TITLES)
        qtbot.addWidget(nav)
        assert nav.current_tab == 0

    def test_switch_tab_changes_current(self, nav_with_tabs) -> None:
        nav, _tabs = nav_with_tabs
        nav.switch_tab(2)
        assert nav.current_tab == 2

    def test_switch_tab_emits_signal(self, nav_with_tabs, qtbot) -> None:
        nav, _tabs = nav_with_tabs
        with qtbot.waitSignal(nav.tab_changed, timeout=1000) as blocker:
            nav.switch_tab(3)
        assert blocker.args == [3]

    def test_switch_tab_shows_correct_widget(self, nav_with_tabs) -> None:
        nav, tabs = nav_with_tabs
        nav.switch_tab(1)
        assert nav.current_widget() is tabs[1]
        nav.switch_tab(3)
        assert nav.current_widget() is tabs[3]


class TestPushPop:
    def test_push_screen_shows_new_widget(self, nav_with_tabs) -> None:
        nav, _tabs = nav_with_tabs
        sub = QLabel("Sub Screen")
        nav.push_screen(sub)
        assert nav.current_widget() is sub

    def test_pop_screen_returns_to_previous(self, nav_with_tabs) -> None:
        nav, tabs = nav_with_tabs
        sub = QLabel("Sub Screen")
        nav.push_screen(sub)
        popped = nav.pop_screen()
        assert popped is sub
        assert nav.current_widget() is tabs[0]

    def test_pop_empty_stack_returns_none(self, nav_with_tabs) -> None:
        nav, _tabs = nav_with_tabs
        assert nav.pop_screen() is None

    def test_push_pop_per_tab_isolation(self, nav_with_tabs) -> None:
        nav, tabs = nav_with_tabs
        sub0 = QLabel("Sub on Tab 0")
        nav.push_screen(sub0)
        assert nav.current_widget() is sub0

        nav.switch_tab(1)
        assert nav.current_widget() is tabs[1]

        nav.switch_tab(0)
        assert nav.current_widget() is sub0

    def test_multiple_push_pop(self, nav_with_tabs) -> None:
        nav, tabs = nav_with_tabs
        sub1 = QLabel("Sub 1")
        sub2 = QLabel("Sub 2")
        nav.push_screen(sub1)
        nav.push_screen(sub2)
        assert nav.current_widget() is sub2

        nav.pop_screen()
        assert nav.current_widget() is sub1

        nav.pop_screen()
        assert nav.current_widget() is tabs[0]


class TestSessionMode:
    def test_enter_session_hides_tabs(self, nav_with_tabs) -> None:
        nav, _tabs = nav_with_tabs
        nav.enter_session()
        assert not nav.tabs_visible
        assert nav.in_session

    def test_exit_session_restores_tabs(self, nav_with_tabs) -> None:
        nav, _tabs = nav_with_tabs
        nav.enter_session()
        nav.exit_session()
        assert nav.tabs_visible
        assert not nav.in_session

    def test_session_push_pop(self, nav_with_tabs) -> None:
        nav, _tabs = nav_with_tabs
        nav.enter_session()
        screen1 = QLabel("Session Screen 1")
        nav.push_screen(screen1)
        assert nav.current_widget() is screen1

        screen2 = QLabel("Session Screen 2")
        nav.push_screen(screen2)
        assert nav.current_widget() is screen2

        nav.pop_screen()
        assert nav.current_widget() is screen1

    def test_exit_session_clears_session_widgets(self, nav_with_tabs) -> None:
        nav, _tabs = nav_with_tabs
        nav.enter_session()
        nav.push_screen(QLabel("S1"))
        nav.push_screen(QLabel("S2"))
        nav.exit_session()
        # After exit, current widget should be the tab root, not a session screen
        assert not nav.in_session

    def test_in_session_property(self, qtbot) -> None:
        nav = NavigationController(_TAB_TITLES)
        qtbot.addWidget(nav)
        assert nav.in_session is False
        nav.enter_session()
        assert nav.in_session is True
        nav.exit_session()
        assert nav.in_session is False

    def test_session_entered_signal(self, qtbot) -> None:
        nav = NavigationController(_TAB_TITLES)
        qtbot.addWidget(nav)
        with qtbot.waitSignal(nav.session_entered, timeout=1000):
            nav.enter_session()

    def test_session_exited_signal(self, qtbot) -> None:
        nav = NavigationController(_TAB_TITLES)
        qtbot.addWidget(nav)
        nav.enter_session()
        with qtbot.waitSignal(nav.session_exited, timeout=1000):
            nav.exit_session()

    def test_tab_state_preserved_after_session(self, nav_with_tabs) -> None:
        nav, tabs = nav_with_tabs
        nav.switch_tab(2)
        nav.enter_session()
        nav.push_screen(QLabel("Session"))
        nav.exit_session()

        assert nav.current_tab == 2
        assert nav.current_widget() is tabs[2]
