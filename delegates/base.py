from PySide6.QtCore import QEvent, QModelIndex, QPersistentModelIndex
from PySide6.QtGui import QFocusEvent, QIcon, QKeyEvent, QPainter
from PySide6.QtWidgets import (QApplication, QStyle, QStyledItemDelegate,
                               QStyleOptionViewItem, QWidget)

from editors.inline.caps_safe_line import (_LAYOUT_SWITCH_FOCUS_REASONS,
                                           _LOCK_KEYS)

__all__ = [
    "_TextEditorDelegateBase",
    "paint_editor_underlay",
]


def paint_editor_underlay(
    painter: QPainter,
    option: QStyleOptionViewItem,
    widget: QWidget | None,
) -> None:
    """Paint only the cell background/selection — no text, no decoration.

    Used to blank out a cell whose inline editor is currently active, so
    semi-transparent or partially-covering editors do not visually overlap
    the previously formatted value underneath.
    """
    opt = QStyleOptionViewItem(option)
    opt.text = ""
    opt.icon = QIcon()
    opt.features &= ~QStyleOptionViewItem.ViewItemFeature.HasDecoration
    style = widget.style() if widget is not None else QApplication.style()
    style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)


class _TextEditorDelegateBase(QStyledItemDelegate):
    """Shared base for delegates that host inline text editors.

    Filters lock-key key events and layout-switch FocusOut events so
    Qt's default delegate ``eventFilter`` does not commit / close the
    editor when the user is just toggling CapsLock as a layout switch.

    Also tracks which indices currently have an open inline editor so
    subclasses can suppress cell text/decoration painting underneath
    the editor widget (avoids visible overlap with translucent or
    composite editors that don't fully cover the cell rect).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._editing_indices: set[QPersistentModelIndex] = set()

    # --- editor-open tracking ----------------------------------------------
    def _mark_editor_open(self, index: QModelIndex | QPersistentModelIndex) -> None:
        if index is None or not index.isValid():
            return
        self._editing_indices.add(QPersistentModelIndex(index))

    def _mark_editor_closed(self, index: QModelIndex | QPersistentModelIndex) -> None:
        if index is None:
            return
        pidx = QPersistentModelIndex(index) if index.isValid() else None
        if pidx is not None:
            self._editing_indices.discard(pidx)
        # Drop any stale persistent indices that have since been invalidated.
        self._editing_indices = {p for p in self._editing_indices if p.isValid()}

    def _is_editor_open(self, index: QModelIndex | QPersistentModelIndex) -> bool:
        if index is None or not index.isValid():
            return False
        return QPersistentModelIndex(index) in self._editing_indices

    def destroyEditor(self, editor, index) -> None:  # type: ignore[override]
        try:
            super().destroyEditor(editor, index)
        finally:
            self._mark_editor_closed(index)

    def eventFilter(self, editor, event):  # type: ignore[override]
        et = event.type()
        if et == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            if event.key() in _LOCK_KEYS:
                return True
        elif et == QEvent.Type.FocusOut and isinstance(event, QFocusEvent):
            if event.reason() in _LAYOUT_SWITCH_FOCUS_REASONS:
                return True
        return super().eventFilter(editor, event)
