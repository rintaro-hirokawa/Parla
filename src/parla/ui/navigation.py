"""Navigation controller for tab switching, push/pop, and session mode."""

from collections.abc import Sequence

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QStackedWidget, QTabBar, QVBoxLayout, QWidget


class NavigationController(QWidget):
    """Manages tab navigation, sub-screen push/pop, and session mode.

    Normal mode: 4 main tabs with per-tab sub-screen stacks.
    Session mode: tabs hidden, separate session screen stack.
    """

    tab_changed = Signal(int)
    session_entered = Signal()
    session_exited = Signal()

    TAB_TODAY = 0
    TAB_ITEMS = 1
    TAB_HISTORY = 2
    TAB_SETTINGS = 3

    def __init__(self, tab_titles: Sequence[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._tab_bar = QTabBar()
        self._main_stack = QStackedWidget()
        self._session_stack = QStackedWidget()

        for title in tab_titles:
            self._tab_bar.addTab(title)
        self._tab_bar.currentChanged.connect(self._on_tab_changed)

        self._tab_roots: dict[int, QWidget] = {}
        self._nav_stacks: dict[int, list[QWidget]] = {}
        self._session_nav_stack: list[QWidget] = []
        self._in_session = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tab_bar)
        layout.addWidget(self._main_stack)
        layout.addWidget(self._session_stack)
        self._session_stack.hide()

    def set_tab_widget(self, tab_index: int, widget: QWidget) -> None:
        """Set the root widget for a tab. Called during app init."""
        self._tab_roots[tab_index] = widget
        self._main_stack.addWidget(widget)
        if tab_index == 0:
            self._main_stack.setCurrentWidget(widget)

    def switch_tab(self, index: int) -> None:
        """Programmatic tab switch."""
        self._tab_bar.setCurrentIndex(index)

    def current_widget(self) -> QWidget | None:
        """Return the currently visible widget."""
        if self._in_session:
            return self._session_stack.currentWidget()
        return self._main_stack.currentWidget()

    def push_screen(self, widget: QWidget) -> None:
        """Push a sub-screen onto the current context's stack."""
        if self._in_session:
            self._session_nav_stack.append(widget)
            self._session_stack.addWidget(widget)
            self._session_stack.setCurrentWidget(widget)
        else:
            tab = self._tab_bar.currentIndex()
            self._nav_stacks.setdefault(tab, [])
            self._nav_stacks[tab].append(widget)
            self._main_stack.addWidget(widget)
            self._main_stack.setCurrentWidget(widget)

    def pop_screen(self) -> QWidget | None:
        """Pop the top sub-screen. Returns None if stack is empty."""
        if self._in_session:
            if not self._session_nav_stack:
                return None
            widget = self._session_nav_stack.pop()
            self._session_stack.removeWidget(widget)
            widget.deleteLater()
            return widget

        tab = self._tab_bar.currentIndex()
        stack = self._nav_stacks.get(tab, [])
        if not stack:
            return None
        widget = stack.pop()
        self._main_stack.removeWidget(widget)
        if stack:
            self._main_stack.setCurrentWidget(stack[-1])
        elif tab in self._tab_roots:
            self._main_stack.setCurrentWidget(self._tab_roots[tab])
        widget.deleteLater()
        return widget

    def enter_session(self) -> None:
        """Hide tabs and show session screen stack."""
        self._in_session = True
        self._tab_bar.hide()
        self._main_stack.hide()
        self._session_stack.show()
        self.session_entered.emit()

    def exit_session(self) -> None:
        """End session mode: restore tabs, clear session stack."""
        self._in_session = False
        while self._session_nav_stack:
            w = self._session_nav_stack.pop()
            self._session_stack.removeWidget(w)
            w.deleteLater()
        self._session_stack.hide()
        self._tab_bar.show()
        self._main_stack.show()
        self._show_current_tab_widget()
        self.session_exited.emit()

    @property
    def tabs_visible(self) -> bool:
        """Whether the tab bar is currently shown."""
        return not self._tab_bar.isHidden()

    def set_tabs_visible(self, visible: bool) -> None:
        """Show or hide the tab bar."""
        self._tab_bar.setVisible(visible)

    @property
    def in_session(self) -> bool:
        """Whether the app is currently in session mode."""
        return self._in_session

    @property
    def current_tab(self) -> int:
        """Index of the currently selected tab."""
        return self._tab_bar.currentIndex()

    def _on_tab_changed(self, index: int) -> None:
        self._show_current_tab_widget()
        self.tab_changed.emit(index)

    def _show_current_tab_widget(self) -> None:
        """Show the correct widget for the current tab (top of stack or root)."""
        tab = self._tab_bar.currentIndex()
        stack = self._nav_stacks.get(tab, [])
        if stack:
            self._main_stack.setCurrentWidget(stack[-1])
        elif tab in self._tab_roots:
            self._main_stack.setCurrentWidget(self._tab_roots[tab])
