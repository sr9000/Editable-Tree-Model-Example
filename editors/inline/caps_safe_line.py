from PySide6.QtCore import Qt
from PySide6.QtGui import QFocusEvent, QKeyEvent
from PySide6.QtWidgets import QLineEdit

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
