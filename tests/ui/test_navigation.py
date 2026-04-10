"""Tests for NavigationController."""

from PySide6.QtWidgets import QLabel, QWidget

from parla.ui.navigation import NavigationController


def _make_tab_widgets() -> list[QWidget]:
    """Create 4 placeholder widgets for the 4 main tabs."""
    return [QLabel(title) for title in ["Today", "Items", "History", "Settings"]]


class TestTabSwitching:
    def test_initial_tab_is_zero(self, qtbot) -> None:
        nav = NavigationController()
        qtbot.addWidget(nav)
        assert nav.current_tab == 0

    def test_switch_tab_changes_current(self, qtbot) -> None:
        nav = NavigationController()
        qtbot.addWidget(nav)
        for w in _make_tab_widgets():
            nav.set_tab_widget(nav.TAB_TODAY + _make_tab_widgets().index(w) if False else 0, w)
        # Set up tabs properly
        nav2 = NavigationController()
        qtbot.addWidget(nav2)
        tabs = _make_tab_widgets()
        for i, w in enumerate(tabs):
            nav2.set_tab_widget(i, w)

        nav2.switch_tab(2)
        assert nav2.current_tab == 2

    def test_switch_tab_emits_signal(self, qtbot) -> None:
        nav = NavigationController()
        qtbot.addWidget(nav)
        tabs = _make_tab_widgets()
        for i, w in enumerate(tabs):
            nav.set_tab_widget(i, w)

        with qtbot.waitSignal(nav.tab_changed, timeout=1000) as blocker:
            nav.switch_tab(3)

        assert blocker.args == [3]

    def test_switch_tab_shows_correct_widget(self, qtbot) -> None:
        nav = NavigationController()
        qtbot.addWidget(nav)
        tabs = _make_tab_widgets()
        for i, w in enumerate(tabs):
            nav.set_tab_widget(i, w)

        nav.switch_tab(1)
        assert nav.current_widget() is tabs[1]

        nav.switch_tab(3)
        assert nav.current_widget() is tabs[3]


class TestPushPop:
    def test_push_screen_shows_new_widget(self, qtbot) -> None:
        nav = NavigationController()
        qtbot.addWidget(nav)
        tabs = _make_tab_widgets()
        for i, w in enumerate(tabs):
            nav.set_tab_widget(i, w)

        sub = QLabel("Sub Screen")
        nav.push_screen(sub)
        assert nav.current_widget() is sub

    def test_pop_screen_returns_to_previous(self, qtbot) -> None:
        nav = NavigationController()
        qtbot.addWidget(nav)
        tabs = _make_tab_widgets()
        for i, w in enumerate(tabs):
            nav.set_tab_widget(i, w)

        sub = QLabel("Sub Screen")
        nav.push_screen(sub)
        popped = nav.pop_screen()
        assert popped is sub
        assert nav.current_widget() is tabs[0]

    def test_pop_empty_stack_returns_none(self, qtbot) -> None:
        nav = NavigationController()
        qtbot.addWidget(nav)
        tabs = _make_tab_widgets()
        for i, w in enumerate(tabs):
            nav.set_tab_widget(i, w)

        assert nav.pop_screen() is None

    def test_push_pop_per_tab_isolation(self, qtbot) -> None:
        nav = NavigationController()
        qtbot.addWidget(nav)
        tabs = _make_tab_widgets()
        for i, w in enumerate(tabs):
            nav.set_tab_widget(i, w)

        # Push sub-screen on tab 0
        sub0 = QLabel("Sub on Tab 0")
        nav.push_screen(sub0)
        assert nav.current_widget() is sub0

        # Switch to tab 1 — should show tab 1's root
        nav.switch_tab(1)
        assert nav.current_widget() is tabs[1]

        # Switch back to tab 0 — should show the pushed sub-screen
        nav.switch_tab(0)
        assert nav.current_widget() is sub0

    def test_multiple_push_pop(self, qtbot) -> None:
        nav = NavigationController()
        qtbot.addWidget(nav)
        tabs = _make_tab_widgets()
        for i, w in enumerate(tabs):
            nav.set_tab_widget(i, w)

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
    def test_enter_session_hides_tabs(self, qtbot) -> None:
        nav = NavigationController()
        qtbot.addWidget(nav)
        tabs = _make_tab_widgets()
        for i, w in enumerate(tabs):
            nav.set_tab_widget(i, w)

        nav.enter_session()
        assert nav._tab_bar.isHidden()
        assert nav._main_stack.isHidden()
        assert not nav._session_stack.isHidden()

    def test_exit_session_restores_tabs(self, qtbot) -> None:
        nav = NavigationController()
        qtbot.addWidget(nav)
        tabs = _make_tab_widgets()
        for i, w in enumerate(tabs):
            nav.set_tab_widget(i, w)

        nav.enter_session()
        nav.exit_session()
        assert not nav._tab_bar.isHidden()
        assert not nav._main_stack.isHidden()
        assert nav._session_stack.isHidden()

    def test_session_push_pop(self, qtbot) -> None:
        nav = NavigationController()
        qtbot.addWidget(nav)
        tabs = _make_tab_widgets()
        for i, w in enumerate(tabs):
            nav.set_tab_widget(i, w)

        nav.enter_session()
        screen1 = QLabel("Session Screen 1")
        nav.push_screen(screen1)
        assert nav.current_widget() is screen1

        screen2 = QLabel("Session Screen 2")
        nav.push_screen(screen2)
        assert nav.current_widget() is screen2

        nav.pop_screen()
        assert nav.current_widget() is screen1

    def test_exit_session_clears_session_stack(self, qtbot) -> None:
        nav = NavigationController()
        qtbot.addWidget(nav)
        tabs = _make_tab_widgets()
        for i, w in enumerate(tabs):
            nav.set_tab_widget(i, w)

        nav.enter_session()
        nav.push_screen(QLabel("S1"))
        nav.push_screen(QLabel("S2"))

        nav.exit_session()
        assert nav._session_stack.count() == 0

    def test_in_session_property(self, qtbot) -> None:
        nav = NavigationController()
        qtbot.addWidget(nav)

        assert nav.in_session is False
        nav.enter_session()
        assert nav.in_session is True
        nav.exit_session()
        assert nav.in_session is False

    def test_session_entered_signal(self, qtbot) -> None:
        nav = NavigationController()
        qtbot.addWidget(nav)

        with qtbot.waitSignal(nav.session_entered, timeout=1000):
            nav.enter_session()

    def test_session_exited_signal(self, qtbot) -> None:
        nav = NavigationController()
        qtbot.addWidget(nav)

        nav.enter_session()
        with qtbot.waitSignal(nav.session_exited, timeout=1000):
            nav.exit_session()

    def test_tab_state_preserved_after_session(self, qtbot) -> None:
        nav = NavigationController()
        qtbot.addWidget(nav)
        tabs = _make_tab_widgets()
        for i, w in enumerate(tabs):
            nav.set_tab_widget(i, w)

        nav.switch_tab(2)
        nav.enter_session()
        nav.push_screen(QLabel("Session"))
        nav.exit_session()

        # Tab 2 should still be selected after exiting session
        assert nav.current_tab == 2
        assert nav.current_widget() is tabs[2]
