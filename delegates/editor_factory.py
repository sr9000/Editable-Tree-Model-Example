from __future__ import annotations

import binascii
import zlib
from typing import Protocol

from gmpy2 import mpq
from PySide6.QtCore import QEvent, QModelIndex, QObject, QPersistentModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QFont, QFontMetrics, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QStyleOptionViewItem,
    QWidget,
)

from datetime_editor.better_dt_editor import BetterDateTimeEditor
from datetime_editor.enums import DateTimeCategory
from delegates.base import _CapsLockSafeLineEdit
from delegates.bytes_codec import decode_bytes, encode_bytes
from delegates.color_codec import color_to_html, parse_color
from delegates.number_affix_delegate import (
    AffixCompositeEditor,
    is_affix_json_type,
    kind_for_json_type,
    normalize_affix_value,
    validate_affix_value,
)
from dialogs.qhexedit_dlg import QHexDialog
from dialogs.qmultiline_dlg import QMultilineDialog
from qbigint_spinbox import QBigIntSpinBox
from qmpq_spinbox import QMpqSpinBox
from settings import SECRET_HIDE_ON_FOCUS_OUT
from state.edit_limits import get_multiline_edit_warning_limit_chars, get_string_edit_warning_limit_chars
from tree.item import JsonTreeItem
from tree.types import TEXT_LINE_FAMILY, TEXT_MULTI_FAMILY, JsonType


class ValueDelegateProtocol(Protocol):
    _secret_watchers: dict[QWidget, "_SecretEditorWatcher"]

    def _context_for(self, host) -> "EditorContextProtocol": ...

    def _finalize_secret_editor(self, editor: QWidget, index: QPersistentModelIndex) -> None: ...

    def _apply_monospace_font(self, font: QFont) -> QFont: ...

    def _mark_editor_open(self, index: QModelIndex | QPersistentModelIndex) -> None: ...


class EditorContextProtocol(Protocol):
    def commit(self, index: QModelIndex, value, role: Qt.ItemDataRole = Qt.ItemDataRole.EditRole): ...

    def notify_status(self, message: str, timeout_ms: int = 0) -> None: ...

    def confirm_large_binary_edit(self, parent, payload_size: int) -> bool: ...

    def confirm_large_text_edit(
        self,
        parent,
        *,
        text_len: int,
        limit: int,
        title: str,
        kind: str,
    ) -> bool: ...

    def affix_mru(self): ...

    def icon_provider(self): ...


class _SecretLineEdit(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._revealed = False
        self._line_edit = _CapsLockSafeLineEdit(self)
        self._line_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._toggle_btn = QPushButton(self)
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._toggle_btn.setAutoDefault(False)
        self._toggle_btn.setDefault(False)
        self._toggle_btn.toggled.connect(self._set_revealed)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self._layout.addWidget(self._toggle_btn)
        self._layout.addWidget(self._line_edit)

        self.setFocusProxy(self._line_edit)
        self._sync_toggle_button()

        # Bubble up line-edit signals so Qt's delegate infrastructure is happy.
        self.textChanged = self._line_edit.textChanged
        self.textEdited = self._line_edit.textEdited
        self.returnPressed = self._line_edit.returnPressed

        self._update_button_width()

    def text(self) -> str:
        return self._line_edit.text()

    def setText(self, text: str) -> None:
        self._line_edit.setText(text)

    def _set_revealed(self, checked: bool) -> None:
        self._revealed = bool(checked)
        self._line_edit.setEchoMode(QLineEdit.EchoMode.Normal if self._revealed else QLineEdit.EchoMode.Password)
        self._sync_toggle_button()

    def _sync_toggle_button(self) -> None:
        label = "Shown" if self._revealed else "Hidden"
        self._toggle_btn.setText(label)
        self._toggle_btn.setToolTip(label)
        if self._toggle_btn.isChecked() != self._revealed:
            self._toggle_btn.blockSignals(True)
            self._toggle_btn.setChecked(self._revealed)
            self._toggle_btn.blockSignals(False)
        self._update_button_width()

    def _update_button_width(self) -> None:
        metrics = QFontMetrics(self._toggle_btn.font())
        width = max(metrics.horizontalAdvance("Hidden"), metrics.horizontalAdvance("Shown")) + 18
        self._toggle_btn.setFixedWidth(width)

    def setFont(self, font: QFont) -> None:
        super().setFont(font)
        self._line_edit.setFont(font)
        self._toggle_btn.setFont(font)
        self._update_button_width()


class _SecretEditorWatcher(QObject):
    def __init__(self, delegate: ValueDelegateProtocol, editor: QWidget, index: QPersistentModelIndex):
        super().__init__(editor)
        self._delegate = delegate
        self._editor = editor
        self._index = index

        # Listen for application-wide focus transitions to hide sensitive inputs immediately
        app = QApplication.instance()
        if app is not None:
            app.applicationStateChanged.connect(self._on_app_state_changed)

    def cleanup(self) -> None:
        app = QApplication.instance()
        if app is not None:
            try:
                app.applicationStateChanged.disconnect(self._on_app_state_changed)
            except (RuntimeError, TypeError):
                pass

    def eventFilter(self, watched, event):  # type: ignore[override]
        if event.type() == QEvent.Type.FocusOut and SECRET_HIDE_ON_FOCUS_OUT:
            self._delegate._finalize_secret_editor(self._editor, self._index)
        return super().eventFilter(watched, event)

    def _on_app_state_changed(self, state) -> None:
        if SECRET_HIDE_ON_FOCUS_OUT and state != Qt.ApplicationState.ApplicationActive:
            self._delegate._finalize_secret_editor(self._editor, self._index)


def _to_index(index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
    if isinstance(index, QPersistentModelIndex):
        return QModelIndex(index)
    return index


def _source_index(index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
    idx = _to_index(index)
    model = idx.model()
    if isinstance(model, QSortFilterProxyModel):
        return model.mapToSource(idx)
    return idx


def _commit(
    delegate: ValueDelegateProtocol,
    index: QModelIndex | QPersistentModelIndex,
    value,
    role: Qt.ItemDataRole = Qt.ItemDataRole.EditRole,
    host=None,
) -> bool:
    idx = _to_index(index)
    if idx.model() is None:
        return False
    ctx = delegate._context_for(host)
    result = ctx.commit(idx, value, role)
    return bool(result)


def _notify_status(delegate: ValueDelegateProtocol, host, message: str, timeout: int = 3000) -> None:
    delegate._context_for(host).notify_status(message, timeout)


def _confirm_large_binary_edit(delegate: ValueDelegateProtocol, host, payload_size: int) -> bool:
    return delegate._context_for(host).confirm_large_binary_edit(host, payload_size)


def _confirm_large_text_edit(
    delegate: ValueDelegateProtocol, host, *, text_len: int, limit: int, title: str, kind: str
) -> bool:
    return delegate._context_for(host).confirm_large_text_edit(
        host, text_len=text_len, limit=limit, title=title, kind=kind
    )


def create_value_editor(
    delegate: ValueDelegateProtocol, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex
) -> QWidget | None:
    src_idx = _source_index(index)
    item: JsonTreeItem = src_idx.internalPointer()

    editor = None
    match item.json_type:
        case _ if is_affix_json_type(item.json_type):
            ctx = delegate._context_for(parent)
            mru = ctx.affix_mru()
            kind = kind_for_json_type(item.json_type)
            mru_items = mru.items(kind) if mru is not None else []
            icon = QIcon()
            provider = ctx.icon_provider()
            if provider is not None:
                key = "affix_prefix" if kind.value == "prefix" else "affix_suffix"
                icon = provider.for_key(key)
            editor = AffixCompositeEditor(parent, json_type=item.json_type, mru_items=mru_items)
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
        case _ if item.json_type in TEXT_LINE_FAMILY:
            text_len = len(str(item.value or ""))
            limit = get_string_edit_warning_limit_chars()
            if not _confirm_large_text_edit(
                delegate,
                parent,
                text_len=text_len,
                limit=limit,
                title="Large string value",
                kind="String value",
            ):
                _notify_status(delegate, parent, "String edit cancelled", 2000)
                return None
            editor = _CapsLockSafeLineEdit(parent)
        case JsonType.SECRET_LINE:
            editor = _SecretLineEdit(parent)
        case JsonType.DATE | JsonType.TIME | JsonType.DATETIME | JsonType.DATETIMEZONE | JsonType.DATETIMEUTC:
            editor = BetterDateTimeEditor(parent)
        case _ if item.json_type in TEXT_MULTI_FAMILY:
            text_len = len(str(item.value or ""))
            limit = get_multiline_edit_warning_limit_chars()
            if not _confirm_large_text_edit(
                delegate,
                parent,
                text_len=text_len,
                limit=limit,
                title="Large multiline text",
                kind="Multiline value",
            ):
                _notify_status(delegate, parent, "Multiline edit cancelled", 2000)
                return None
            pidx = QPersistentModelIndex(index)

            def _save_multiline(text: str) -> None:
                if pidx.isValid():
                    _commit(delegate, pidx, text, Qt.ItemDataRole.EditRole, host=parent)

            QMultilineDialog(parent=parent, text=str(item.value or ""), callback=_save_multiline).open()
            return None
        case JsonType.SECRET_TEXT:
            text_len = len(str(item.value or ""))
            limit = get_multiline_edit_warning_limit_chars()
            if not _confirm_large_text_edit(
                delegate,
                parent,
                text_len=text_len,
                limit=limit,
                title="Large secret text",
                kind="Secret value",
            ):
                _notify_status(delegate, parent, "Secret text edit cancelled", 2000)
                return None

            pidx = QPersistentModelIndex(index)

            def _save_secret_text(text: str) -> None:
                if pidx.isValid():
                    _commit(delegate, pidx, text, Qt.ItemDataRole.EditRole, host=parent)

            dlg = QMultilineDialog(
                parent=parent, text=str(item.value or ""), sensitive=True, callback=_save_secret_text
            )
            dlg.setWindowTitle("Edit Secret Text")
            dlg.open()
            return None
        case JsonType.COLOR_RGB | JsonType.COLOR_RGBA:
            pidx = QPersistentModelIndex(index)
            initial = parse_color(item.value if isinstance(item.value, str) else "") or parse_color("#000000")

            dialog = QColorDialog(parent, currentColor=initial)
            if item.json_type is JsonType.COLOR_RGBA:
                dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, True)
            dialog.setWindowTitle("Pick color (RGBA)" if item.json_type is JsonType.COLOR_RGBA else "Pick color (RGB)")

            target_type = item.json_type

            def _on_color_selected(selected) -> None:
                if not pidx.isValid():
                    return
                text = color_to_html(selected, target_type)
                _commit(delegate, pidx, text, Qt.ItemDataRole.EditRole, host=parent)

            dialog.colorSelected.connect(_on_color_selected)
            dialog.open()
            return None

        case JsonType.BYTES | JsonType.ZLIB | JsonType.GZIP:
            try:
                decoded = decode_bytes(item.value, item.json_type)
            except (ValueError, OSError, zlib.error, binascii.Error) as exc:
                _notify_status(delegate, parent, f"Decode failed: {exc}", 4000)
                return None

            if not _confirm_large_binary_edit(delegate, parent, len(decoded)):
                _notify_status(delegate, parent, "Binary edit cancelled", 2000)
                return None

            pidx = QPersistentModelIndex(index)

            def _save_binary(data: bytes) -> None:
                if not pidx.isValid():
                    return
                encoded = encode_bytes(data, item.json_type)
                _commit(delegate, pidx, encoded, Qt.ItemDataRole.EditRole, host=parent)

            QHexDialog(parent=parent, data=decoded, callback=_save_binary).open()
            return None

        case _:
            raise ValueError(f"Inappropriate `JsonType` in `ValueDelegate.createEditor()`: {item.json_type=}")

    if editor is not None:
        editor.setFont(delegate._apply_monospace_font(editor.font()))
        delegate._mark_editor_open(index)
        if item.json_type in (JsonType.SECRET_LINE, JsonType.SECRET_TEXT):
            _install_secret_watcher(delegate, editor, index)
    return editor


def _install_secret_watcher(delegate: ValueDelegateProtocol, editor: QWidget, index: QModelIndex) -> None:
    watcher = _SecretEditorWatcher(delegate, editor, QPersistentModelIndex(index))
    editor.installEventFilter(watcher)
    for child in editor.findChildren(QWidget):
        child.installEventFilter(watcher)
    delegate._secret_watchers[editor] = watcher


def set_value_editor_data(delegate: ValueDelegateProtocol, editor: QWidget, index: QModelIndex):
    src_idx = _source_index(index)
    item: JsonTreeItem = src_idx.internalPointer()
    value = item.value

    if isinstance(editor, QBigIntSpinBox):
        try:
            editor.setValue(int(value))
        except (TypeError, ValueError):
            editor.setValue(0)
        return

    if isinstance(editor, AffixCompositeEditor):
        normalized = normalize_affix_value(value, item.json_type)
        if normalized is not None:
            editor.set_value(normalized)
        return

    if isinstance(editor, QMpqSpinBox):
        try:
            v = mpq(str(value)) if not isinstance(value, mpq) else value
        except (TypeError, ValueError):
            v = mpq(0)
        if item.json_type is JsonType.PERCENT:
            v = v * 100
        editor.setValue(v)
        return

    if isinstance(editor, QComboBox):
        editor.setCurrentIndex(0 if bool(value) else 1)
        return

    if isinstance(editor, BetterDateTimeEditor):
        category = _category_for_json_type(item.json_type)
        if category is not None:
            editor.setCategory(category)
        editor.setText(str(value or ""))
        return

    if isinstance(editor, _SecretLineEdit):
        editor.setText("" if value is None else str(value))
        return

    if isinstance(editor, QLineEdit):
        editor.setText("" if value is None else str(value))
        return

    super(type(delegate), delegate).setEditorData(editor, index)


def set_value_model_data(delegate: ValueDelegateProtocol, editor: QWidget, model, index: QModelIndex):
    if isinstance(editor, QBigIntSpinBox):
        _commit(delegate, index, editor.value(), Qt.ItemDataRole.EditRole, host=editor)
        return

    if isinstance(editor, QMpqSpinBox):
        src_idx = _source_index(index)
        item: JsonTreeItem = src_idx.internalPointer()
        value = editor.value()
        if item is not None and item.json_type is JsonType.PERCENT:
            value = value / mpq("100")
        _commit(delegate, index, value, Qt.ItemDataRole.EditRole, host=editor)
        return

    if isinstance(editor, QComboBox):
        _commit(delegate, index, editor.currentData(), Qt.ItemDataRole.EditRole, host=editor)
        return

    if isinstance(editor, BetterDateTimeEditor):
        _commit(delegate, index, editor.text(), Qt.ItemDataRole.EditRole, host=editor)
        return

    if isinstance(editor, _SecretLineEdit):
        _commit(delegate, index, editor.text(), Qt.ItemDataRole.EditRole, host=editor)
        return

    if isinstance(editor, QLineEdit):
        _commit(delegate, index, editor.text(), Qt.ItemDataRole.EditRole, host=editor)
        return

    if isinstance(editor, AffixCompositeEditor):
        candidate = editor.build_value()
        validated = validate_affix_value(candidate)
        if validated is None:
            editor.set_invalid(True)
            return
        editor.set_invalid(False)
        if _commit(delegate, index, validated, Qt.ItemDataRole.EditRole, host=editor):
            mru = delegate._context_for(editor).affix_mru()
            if mru is not None:
                mru.push(validated.kind, validated.affix)
        return

    super(type(delegate), delegate).setModelData(editor, model, index)


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
        case JsonType.DATETIMEUTC:
            return DateTimeCategory.DateTimeUTC
        case _:
            return None
