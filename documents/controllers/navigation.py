from __future__ import annotations

from collections.abc import Callable
from enum import IntEnum

from PySide6.QtCore import QEvent, QModelIndex, QObject, Qt
from PySide6.QtGui import QKeyEvent


class NavigationKey(IntEnum):
    LEFT = int(Qt.Key.Key_Left)
    RIGHT = int(Qt.Key.Key_Right)
    UP = int(Qt.Key.Key_Up)
    DOWN = int(Qt.Key.Key_Down)

    @classmethod
    def from_qt_key(cls, key: int | Qt.Key) -> "NavigationKey | None":
        try:
            return cls(int(key))
        except ValueError:
            return None


class JsonTabNavigationController:
    """Keyboard navigation helper for a tab tree view."""

    def __init__(self, tab, edit_name_or_value_from_enter: Callable[[], None]) -> None:
        self._tab = tab
        self._edit_name_or_value_from_enter = edit_name_or_value_from_enter

    def handle_event_filter(self, watched: QObject | None, event: QEvent) -> bool:
        """Return ``True`` when a keyboard event is consumed."""
        view = self._tab.view
        if view is not None and watched in (view, view.viewport()):
            if event.type() != QEvent.Type.KeyPress or not isinstance(event, QKeyEvent):
                return False
            key_event = event
            if key_event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._edit_name_or_value_from_enter()
                return True
            if key_event.key() == Qt.Key.Key_Space and key_event.modifiers() == Qt.KeyboardModifier.NoModifier:
                self.toggle_current_row_expansion_with_space()
                return True
            if self.handle_arrow_navigation(key_event.key(), key_event.modifiers()):
                return True
        return False

    def toggle_current_row_expansion_with_space(self) -> None:
        view = self._tab.view
        if view is None:
            return
        current = view.currentIndex()
        if not current.isValid():
            return
        row_anchor = current.siblingAtColumn(0)
        if not row_anchor.isValid():
            return
        view.setExpanded(row_anchor, not view.isExpanded(row_anchor))

    def handle_arrow_navigation(self, key: int | Qt.Key, modifiers: Qt.KeyboardModifier) -> bool:
        """Use arrows for cell navigation without expanding or collapsing rows."""
        if modifiers != Qt.KeyboardModifier.NoModifier:
            return False
        navigation_key = NavigationKey.from_qt_key(key)
        if navigation_key is None:
            return False

        view = self._tab.view
        if view is None:
            return True

        current = view.currentIndex()
        if not current.isValid():
            return True

        target = QModelIndex(current)
        if navigation_key is NavigationKey.LEFT:
            target = current.siblingAtColumn(max(0, current.column() - 1))
        elif navigation_key is NavigationKey.RIGHT:
            model = view.model()
            if model is None:
                return True
            last_col = max(0, model.columnCount(current.parent()) - 1)
            target = current.siblingAtColumn(min(last_col, current.column() + 1))
        elif navigation_key is NavigationKey.UP:
            above = view.indexAbove(current)
            if above.isValid():
                target = above
        elif navigation_key is NavigationKey.DOWN:
            below = view.indexBelow(current)
            if below.isValid():
                target = below

        view.setCurrentIndex(target)
        return True


__all__ = ["JsonTabNavigationController", "NavigationKey"]
