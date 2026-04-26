import base64
import binascii
import gzip
import zlib

from gmpy2 import mpq
from PySide6.QtCore import QAbstractItemModel, QEvent, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QFocusEvent, QKeyEvent
from PySide6.QtWidgets import QComboBox, QLineEdit, QStyledItemDelegate, QStyleOptionViewItem, QWidget

from datetime_editor.better_dt_editor import BetterDateTimeEditor
from datetime_editor.enums import DateTimeCategory
from dialogs.qhexedit_dlg import QHexDialog
from dialogs.qmultiline_dlg import QMultilineDialog
from enums import JsonType
from mpq2py import mpq_serialization
from qbigint_spinbox import QBigIntSpinBox
from qmpq_spinbox import QMpqSpinBox
from tree_item import JsonTreeItem
from tree_model import JSON_TYPE_ROLE
from units import format_bytes

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


class ValueDelegate(_TextEditorDelegateBase):
    @staticmethod
    def _format_default(value) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, mpq):
            return str(mpq_serialization(value)[0])
        if isinstance(value, bytes):
            return f"<{format_bytes(len(value))}>"
        if isinstance(value, str) and len(value) > 80:
            return value[:80] + "…"
        return str(value)

    @staticmethod
    def _format_with_type(value, json_type: JsonType | None) -> str:
        if json_type is JsonType.PERCENT:
            try:
                q = value if isinstance(value, mpq) else mpq(str(value))
                return f"{float(q * 100):g}%"
            except (TypeError, ValueError):
                return ValueDelegate._format_default(value)

        if json_type in (JsonType.BYTES, JsonType.ZLIB, JsonType.GZIP):
            try:
                raw = decode_bytes(value, json_type) if isinstance(value, str) else bytes(value)
                return f"<{format_bytes(len(raw))}>"
            except Exception:
                return ValueDelegate._format_default(value)

        return ValueDelegate._format_default(value)

    def displayText(self, value, locale):  # type: ignore[override]
        return self._format_default(value)

    def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex) -> None:  # type: ignore[override]
        super().initStyleOption(option, index)
        model = index.model()
        raw = model.data(index, Qt.ItemDataRole.EditRole) if model is not None else index.data(Qt.ItemDataRole.EditRole)
        json_type = model.data(index, JSON_TYPE_ROLE) if model is not None else index.data(JSON_TYPE_ROLE)
        option.text = self._format_with_type(raw, json_type if isinstance(json_type, JsonType) else None)

    @staticmethod
    def _to_index(index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
        return QModelIndex(index) if isinstance(index, QPersistentModelIndex) else index

    @staticmethod
    def _find_tab(host) -> object | None:
        cursor = host
        while cursor is not None:
            if hasattr(cursor, "commit_set_data"):
                return cursor
            cursor = cursor.parent() if hasattr(cursor, "parent") else None
        return None

    @staticmethod
    def _commit(
        index: QModelIndex | QPersistentModelIndex,
        value,
        role: Qt.ItemDataRole = Qt.ItemDataRole.EditRole,
        host=None,
    ) -> bool:
        idx = ValueDelegate._to_index(index)
        model = idx.model()
        if model is None:
            return False

        tab = ValueDelegate._find_tab(host)
        if tab is not None:
            return bool(tab.commit_set_data(idx, value, role))
        return bool(model.setData(idx, value, role))

    @staticmethod
    def _notify_status(host, message: str, timeout: int = 3000) -> None:
        """Surface a transient status message via the owning tab's
        status callback, if available. Falls back to a no-op."""
        tab = ValueDelegate._find_tab(host)
        cb = getattr(tab, "_status_message_callback", None) if tab is not None else None
        if cb is not None:
            try:
                cb(message, timeout)
            except Exception:
                pass

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget | None:

        item: JsonTreeItem = index.internalPointer()

        editor = None
        match item.json_type:
            case JsonType.INTEGER:
                editor = QBigIntSpinBox(parent)
            case JsonType.FLOAT:
                editor = QMpqSpinBox(parent, item.value)
            case JsonType.PERCENT:
                editor = QMpqSpinBox(
                    parent,
                    suffix="%",
                    minimum=mpq("0"),
                    maximum=mpq("100"),
                    single_step=mpq("0.1"),
                )
            case JsonType.BOOLEAN:
                editor = QComboBox(parent)
                editor.addItem("true", True)
                editor.addItem("false", False)
            case JsonType.STRING | JsonType.UNICODE:
                editor = _CapsLockSafeLineEdit(parent)
            case JsonType.DATE | JsonType.TIME | JsonType.DATETIME | JsonType.DATETIMEZONE:
                editor = BetterDateTimeEditor(parent)
            case JsonType.MULTILINE | JsonType.TEXT:
                pidx = QPersistentModelIndex(index)

                def _save_multiline(text: str) -> None:
                    if pidx.isValid():
                        self._commit(pidx, text, Qt.ItemDataRole.EditRole, host=parent)

                QMultilineDialog(  # Use a modal dialog-based editor for multiline text
                    parent=parent,
                    text=str(item.value or ""),
                    callback=_save_multiline,
                ).open()

                return None  # Do not return an inline editor for multiline values

            case JsonType.BYTES | JsonType.ZLIB | JsonType.GZIP:
                try:
                    decoded = decode_bytes(item.value, item.json_type)
                except (ValueError, OSError, zlib.error, binascii.Error) as exc:
                    self._notify_status(parent, f"Decode failed: {exc}", 4000)
                    return None

                pidx = QPersistentModelIndex(index)

                def _save_binary(data: bytes) -> None:
                    if not pidx.isValid():
                        return
                    encoded = encode_bytes(data, item.json_type)
                    self._commit(pidx, encoded, Qt.ItemDataRole.EditRole, host=parent)

                QHexDialog(  # Use a modal dialog-based editor for binary data
                    parent=parent,
                    data=decoded,
                    callback=_save_binary,
                ).open()

                return None  # Do not return an inline editor for binary values

            case _:
                raise ValueError(f"Inappropriate `JsonType` in `ValueDelegate.createEditor()`: {item.json_type=}")

        return editor

    def setEditorData(
        self,
        editor: QWidget,
        index: QModelIndex,
    ):
        # IMPORTANT: dispatch on the editor's *widget class*, not on
        # ``item.json_type``. The editor was created for a specific JSON
        # type by ``createEditor``; if the type was changed afterwards
        # (e.g. via the type combo) Qt may still call us with that old
        # widget. Keying off ``item.json_type`` would then call methods
        # that don't exist on the old widget (``setText`` on
        # ``QMpqSpinBox`` etc.).
        item: JsonTreeItem = index.internalPointer()
        value = item.value

        if isinstance(editor, QBigIntSpinBox):
            try:
                editor.setValue(int(value))
            except (TypeError, ValueError):
                editor.setValue(0)
            return

        if isinstance(editor, QMpqSpinBox):
            # PERCENT stores 0..1 fractions but the editor shows 0..100.
            try:
                v = mpq(str(value)) if not isinstance(value, mpq) else value
            except (TypeError, ValueError):
                v = mpq(0)
            if item.json_type is JsonType.PERCENT:
                v = v * 100
            editor.setValue(v)
            return

        if isinstance(editor, QComboBox):
            # Used for BOOLEAN values.
            editor.setCurrentIndex(0 if bool(value) else 1)
            return

        if isinstance(editor, BetterDateTimeEditor):
            category = self._category_for_json_type(item.json_type)
            if category is not None:
                editor.setCategory(category)
            editor.setText(str(value or ""))
            return

        if isinstance(editor, QLineEdit):
            editor.setText("" if value is None else str(value))
            return

        # Unknown editor class — fall back to the default implementation.
        super().setEditorData(editor, index)

    def setModelData(self, editor: QWidget, model: QAbstractItemModel, index: QModelIndex):
        # Same rationale as in setEditorData: dispatch by editor widget
        # class so a stale editor (created for a previous JSON type) still
        # commits a sensible value. The model's ``setData`` handles type
        # coercion or rejection.
        if isinstance(editor, QBigIntSpinBox):
            self._commit(index, editor.value(), Qt.ItemDataRole.EditRole, host=editor)
            return

        if isinstance(editor, QMpqSpinBox):
            item: JsonTreeItem = index.internalPointer()
            value = editor.value()
            if item is not None and item.json_type is JsonType.PERCENT:
                value = value / mpq("100")
            self._commit(index, value, Qt.ItemDataRole.EditRole, host=editor)
            return

        if isinstance(editor, QComboBox):
            self._commit(index, editor.currentData(), Qt.ItemDataRole.EditRole, host=editor)
            return

        if isinstance(editor, BetterDateTimeEditor):
            self._commit(index, editor.text(), Qt.ItemDataRole.EditRole, host=editor)
            return

        if isinstance(editor, QLineEdit):
            self._commit(index, editor.text(), Qt.ItemDataRole.EditRole, host=editor)
            return

        # Modal-dialog types have no inline editor; nothing to commit.
        super().setModelData(editor, model, index)

    @staticmethod
    def _category_for_json_type(json_type: JsonType) -> DateTimeCategory | None:
        match json_type:
            case JsonType.TIME:
                return DateTimeCategory.Time
            case JsonType.DATE:
                return DateTimeCategory.Date
            case JsonType.DATETIME:
                return DateTimeCategory.DateTime
            case JsonType.DATETIMEZONE:
                return DateTimeCategory.DateTimeWithTZ
            case _:
                return None


class JsonTypeDelegate(QStyledItemDelegate):
    @staticmethod
    def _find_tab(host) -> object | None:
        cursor = host
        while cursor is not None:
            if hasattr(cursor, "commit_set_data"):
                return cursor
            cursor = cursor.parent() if hasattr(cursor, "parent") else None
        return None

    def __init__(self, parent=None):
        super().__init__(parent)
        # ``_interactive`` is set to ``True`` for the duration of an
        # interactive (user-driven) commit out of the type combo. The
        # ``JsonTab._on_type_changed`` slot reads it to decide whether to
        # auto-reopen the value editor on the row whose type just changed.
        # Programmatic ``model.setData(...)`` calls bypass this delegate
        # entirely, so the flag stays ``False`` and no editor is reopened —
        # this is what keeps the smoke tests in
        # ``tests/test_smoke_mainwindow.py`` from logging
        # ``edit: editing failed``.
        self._interactive: bool = False

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget:
        editor = QComboBox(parent)
        for tp in JsonType:
            editor.addItem(tp.value, tp)
        return editor

    def setEditorData(self, editor: QComboBox, index: QModelIndex):
        item: JsonTreeItem = index.internalPointer()
        idx = editor.findData(item.json_type)
        editor.setCurrentIndex(idx if idx >= 0 else 0)

    def setModelData(self, editor: QComboBox, model: QAbstractItemModel, index: QModelIndex):
        selected_type = editor.currentData()

        self._interactive = True
        try:
            tab = self._find_tab(editor)
            if tab is not None:
                tab.commit_set_data(index, selected_type, Qt.ItemDataRole.EditRole)
                return

            model.setData(index, selected_type, Qt.ItemDataRole.EditRole)
        finally:
            self._interactive = False


class NameDelegate(_TextEditorDelegateBase):
    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget:
        return _CapsLockSafeLineEdit(parent)

    def setEditorData(self, editor: QLineEdit, index: QModelIndex):
        editor.setText(str(index.data(Qt.ItemDataRole.EditRole) or ""))

    def setModelData(self, editor: QLineEdit, model: QAbstractItemModel, index: QModelIndex):
        ValueDelegate._commit(index, editor.text(), Qt.ItemDataRole.EditRole, host=editor)


def decode_bytes(b64string: str, json_type: JsonType) -> bytes:
    # Prepare binary data for hex editor
    raw = base64.b64decode(b64string, validate=True) if b64string else b""

    match json_type:  # Decompress if needed
        case JsonType.ZLIB:
            return zlib.decompress(raw)
        case JsonType.GZIP:
            return gzip.decompress(raw)
        case _:
            return raw


# Callback to handle edited data
def encode_bytes(edited_data: bytes, json_type: JsonType) -> str:
    match json_type:  # Compress if needed
        case JsonType.ZLIB:
            edited_data = zlib.compress(edited_data)
        case JsonType.GZIP:
            edited_data = gzip.compress(edited_data)

    # Encode to base64 and update model
    return base64.b64encode(edited_data).decode("ascii")
