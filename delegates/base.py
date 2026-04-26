from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QFocusEvent, QKeyEvent
from PySide6.QtWidgets import QLineEdit, QStyledItemDelegate

# Some users bind CapsLock to a keyboard-layout switch via xkb / IM.
# That can deliver a Key_CapsLock event, plus an ``ActiveWindowFocusReason``
# / ``OtherFocusReason`` ``FocusOut`` to the embedded line-editor, which the
# default ``QStyledItemDelegate.eventFilter`` would interpret as "commit and
# close editor". We absorb both so inline editing survives a layout switch.
_LAYOUT_SWITCH_FOCUS_REASONS = (
    Qt.FocusReason.ActiveWindowFocusReason,
    Qt.FocusReason.OtherFocusReason,
)
_LOCK_KEYS = (
    Qt.Key.Key_CapsLock,
    Qt.Key.Key_NumLock,
    Qt.Key.Key_ScrollLock,
)


class _CapsLockSafeLineEdit(QLineEdit):
    """Inline text editor that survives CapsLock-driven layout switches.

    Swallows lock-key key events and ignores ``FocusOut`` events whose
    reason matches a layout / app-state change, so the delegate never
    sees a "commit and close" trigger from those.
    """

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in _LOCK_KEYS:
            event.accept()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        if event.reason() in _LAYOUT_SWITCH_FOCUS_REASONS:
            event.ignore()
            return
        super().focusOutEvent(event)


class _TextEditorDelegateBase(QStyledItemDelegate):
    """Shared base for delegates that host inline text editors.

    Filters lock-key key events and layout-switch FocusOut events so
    Qt's default delegate ``eventFilter`` does not commit / close the
    editor when the user is just toggling CapsLock as a layout switch.
    """

    def eventFilter(self, editor, event):  # type: ignore[override]
        et = event.type()
        if et == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            if event.key() in _LOCK_KEYS:
                return True
        elif et == QEvent.Type.FocusOut and isinstance(event, QFocusEvent):
            if event.reason() in _LAYOUT_SWITCH_FOCUS_REASONS:
                return True
        return super().eventFilter(editor, event)
