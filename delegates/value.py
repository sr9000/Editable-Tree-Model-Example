import binascii
import zlib

from gmpy2 import mpq
from PySide6.QtCore import (
    QAbstractItemModel,
    QEvent,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QSortFilterProxyModel,
    Qt,
)
from PySide6.QtGui import QFont, QFontDatabase, QFontMetrics, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStyle,
    QStyleOptionViewItem,
    QTreeView,
    QWidget,
)

from datetime_editor.better_dt_editor import BetterDateTimeEditor
from datetime_editor.enums import DateTimeCategory
from delegates.base import _CapsLockSafeLineEdit, _TextEditorDelegateBase, paint_editor_underlay
from delegates.bytes_codec import decode_bytes, encode_bytes
from delegates.color_codec import color_to_html, parse_color
from delegates.number_affix_delegate import (
    AffixCompositeEditor,
    is_affix_json_type,
    kind_for_json_type,
    normalize_affix_value,
    validate_affix_value,
)
from delegates.validation_badge import draw_severity_badge
from delegates.value_formatting import _apply_type_style, format_default, format_with_type
from dialogs.qhexedit_dlg import QHexDialog
from dialogs.qmultiline_dlg import QMultilineDialog
from qbigint_spinbox import QBigIntSpinBox
from qmpq_spinbox import QMpqSpinBox
from settings import SECRET_HIDE_ON_FOCUS_OUT
from state.edit_limits import (
    get_binary_edit_warning_limit_bytes,
    get_multiline_edit_warning_limit_chars,
    get_string_edit_warning_limit_chars,
)
from themes import LIGHT_DEFAULT
from themes.spec import ThemeSpec
from tree.item import JsonTreeItem
from tree.model_roles import JSON_TYPE_ROLE, VALIDATION_SEVERITY_ROLE
from tree.types import TEXT_LINE_FAMILY, TEXT_MULTI_FAMILY, JsonType
from units import counts, format_bytes


class _SecretLineEdit(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._revealed = False
        self.line_edit = _CapsLockSafeLineEdit(self)
        self.line_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.toggle_button = QPushButton(self)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.toggle_button.setAutoDefault(False)
        self.toggle_button.setDefault(False)
        self.toggle_button.toggled.connect(self._set_revealed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.line_edit)

        self.setFocusProxy(self.line_edit)
        self._sync_toggle_button()

    def text(self) -> str:
        return self.line_edit.text()

    def setText(self, text: str) -> None:
        self.line_edit.setText(text)

    def _set_revealed(self, checked: bool) -> None:
        self._revealed = bool(checked)
        self.line_edit.setEchoMode(QLineEdit.EchoMode.Normal if self._revealed else QLineEdit.EchoMode.Password)
        self._sync_toggle_button()

    def _sync_toggle_button(self) -> None:
        label = "Shown" if self._revealed else "Hidden"
        self.toggle_button.setText(label)
        self.toggle_button.setToolTip(label)
        if self.toggle_button.isChecked() != self._revealed:
            self.toggle_button.blockSignals(True)
            self.toggle_button.setChecked(self._revealed)
            self.toggle_button.blockSignals(False)
        self._update_button_width()

    def _update_button_width(self) -> None:
        metrics = QFontMetrics(self.toggle_button.font())
        width = max(metrics.horizontalAdvance("Hidden"), metrics.horizontalAdvance("Shown")) + 18
        self.toggle_button.setFixedWidth(width)

    def setFont(self, font: QFont) -> None:
        super().setFont(font)
        self._update_button_width()


class _SecretEditorWatcher(QObject):
    def __init__(self, delegate: "ValueDelegate", editor: QWidget, index: QPersistentModelIndex):
        super().__init__(editor)
        self._delegate = delegate
        self._editor = editor
        self._index = index
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


class ValueDelegate(_TextEditorDelegateBase):
    def __init__(self, parent=None, *, theme: ThemeSpec | None = None):
        super().__init__(parent)
        self._theme = theme or LIGHT_DEFAULT
        self._monospace_fields_enabled = False
        self._mono_family = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()
        self._secret_watchers: dict[QWidget, _SecretEditorWatcher] = {}

    def set_theme(self, theme: ThemeSpec) -> None:
        self._theme = theme

    def set_monospace_fields_enabled(self, enabled: bool) -> None:
        self._monospace_fields_enabled = bool(enabled)

    def set_monospace_font_family(self, family: str) -> None:
        if family:
            self._mono_family = str(family)

    def _apply_monospace_font(self, font: QFont) -> QFont:
        if not self._monospace_fields_enabled:
            return font
        f = QFont(font)
        f.setFamily(self._mono_family)
        f.setStyleHint(QFont.StyleHint.Monospace)
        f.setFixedPitch(True)
        return f

    @staticmethod
    def _source_index(index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
        idx = ValueDelegate._to_index(index)
        model = idx.model()
        if isinstance(model, QSortFilterProxyModel):
            return model.mapToSource(idx)
        return idx

    @staticmethod
    def _format_default(value) -> str:
        return format_default(value)

    @staticmethod
    def _format_with_type(
        value,
        json_type: JsonType | None,
        *,
        item: JsonTreeItem | None = None,
        show_preview: bool = True,
    ) -> str:
        return format_with_type(value, json_type, item=item, show_preview=show_preview)

    @staticmethod
    def _coerce_json_type(value) -> JsonType | None:
        if isinstance(value, JsonType):
            return value
        if isinstance(value, str):
            try:
                return JsonType(value)
            except ValueError:
                return None
        return None

    def displayText(self, value, locale):  # type: ignore[override]
        return self._format_default(value)

    def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex) -> None:  # type: ignore[override]
        super().initStyleOption(option, index)
        source_index = self._source_index(index)
        item = source_index.internalPointer() if source_index.isValid() else None
        # Read raw value and type directly from the tree item when possible.
        # This avoids the Qt QVariant round-trip that silently overflows for
        # arbitrarily-large Python integers (bigints > 8-byte signed int limit).
        if isinstance(item, JsonTreeItem):
            raw = item.data(source_index.column())
            json_type = item.json_type
        else:
            model = index.model()
            raw = (
                model.data(index, Qt.ItemDataRole.EditRole)
                if model is not None
                else index.data(Qt.ItemDataRole.EditRole)
            )
            json_type = model.data(index, JSON_TYPE_ROLE) if model is not None else index.data(JSON_TYPE_ROLE)
        typed = self._coerce_json_type(json_type)
        show_preview = True
        if typed in (JsonType.ARRAY, JsonType.OBJECT) and isinstance(option.widget, QTreeView):
            tree_index = index.siblingAtColumn(0)
            show_preview = not option.widget.isExpanded(tree_index)
        option.text = self._format_with_type(
            raw,
            typed,
            item=item if isinstance(item, JsonTreeItem) else None,
            show_preview=show_preview,
        )
        if typed in (JsonType.COLOR_RGB, JsonType.COLOR_RGBA) and isinstance(raw, str):
            swatch = self._color_swatch_icon(raw, option)
            if swatch is not None:
                option.icon = swatch
                option.features |= QStyleOptionViewItem.ViewItemFeature.HasDecoration
        if typed is not None:
            _apply_type_style(
                option,
                self._theme.types[typed],
                selected=bool(option.state & QStyle.StateFlag.State_Selected),
                allow_background=True,
            )
        option.font = self._apply_monospace_font(option.font)

    def paint(self, painter, option, index) -> None:  # type: ignore[override]
        if self._is_editor_open(index):
            idx = self._to_index(index)
            opt = QStyleOptionViewItem(option)
            self.initStyleOption(opt, idx)
            paint_editor_underlay(painter, opt, option.widget)
            return
        severity = index.data(VALIDATION_SEVERITY_ROLE)
        if severity is not None:
            idx = self._to_index(index)
            opt = QStyleOptionViewItem(option)
            self.initStyleOption(opt, idx)
            draw_severity_badge(painter, opt, severity, self._theme)
            return
        super().paint(painter, option, index)

    @staticmethod
    def _color_swatch_icon(value: str, option: QStyleOptionViewItem) -> QIcon | None:
        color = parse_color(value)
        if color is None:
            return None
        size = max(8, min(option.decorationSize.height() or 16, 32))
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        try:
            # Checkerboard for transparency awareness
            if color.alpha() < 255:
                step = max(2, size // 4)
                light = Qt.GlobalColor.white
                dark = Qt.GlobalColor.lightGray
                for y in range(0, size, step):
                    for x in range(0, size, step):
                        painter.fillRect(x, y, step, step, light if ((x // step + y // step) % 2 == 0) else dark)
            painter.fillRect(0, 0, size, size, color)
            painter.setPen(Qt.GlobalColor.black)
            painter.drawRect(0, 0, size - 1, size - 1)
        finally:
            painter.end()
        return QIcon(pixmap)

    @staticmethod
    def _to_index(index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
        if isinstance(index, QPersistentModelIndex):
            return QModelIndex(index)
        return index

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
        """Surface a transient status message via the owning tab's status callback, if available."""
        tab = ValueDelegate._find_tab(host)
        cb = getattr(tab, "_status_message_callback", None) if tab is not None else None
        if cb is not None:
            try:
                cb(message, timeout)
            except Exception:
                pass

    @staticmethod
    def _confirm_large_binary_edit(host, payload_size: int) -> bool:
        limit = get_binary_edit_warning_limit_bytes()
        if payload_size <= limit:
            return True

        answer = QMessageBox.warning(
            host,
            "Large binary value",
            f"Binary value is {format_bytes(payload_size)}!\n"
            f"Limit is {format_bytes(limit)}.\n"
            f"Continue editing?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    @staticmethod
    def _confirm_large_text_edit(host, *, text_len: int, limit: int, title: str, kind: str) -> bool:
        if text_len <= limit:
            return True
        answer = QMessageBox.warning(
            host,
            title,
            f"{kind} is {counts(text_len)} chars!\n" f"Limit is {counts(limit)}.\n" f"Continue editing?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget | None:
        source_index = self._source_index(index)
        item: JsonTreeItem = source_index.internalPointer()

        editor = None
        match item.json_type:
            case _ if is_affix_json_type(item.json_type):
                tab = self._find_tab(parent)
                mru = getattr(tab, "affix_mru", None)
                kind = kind_for_json_type(item.json_type)
                mru_items = mru.items(kind) if mru is not None and hasattr(mru, "items") else []
                icon = QIcon()
                provider = getattr(tab, "_icon_provider", None)
                if provider is not None and hasattr(provider, "for_key"):
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
                if not self._confirm_large_text_edit(
                    parent,
                    text_len=text_len,
                    limit=limit,
                    title="Large string value",
                    kind="String value",
                ):
                    self._notify_status(parent, "String edit cancelled", 2000)
                    return None
                editor = _CapsLockSafeLineEdit(parent)
            case JsonType.SECRET_LINE:
                editor = _SecretLineEdit(parent)
            case JsonType.DATE | JsonType.TIME | JsonType.DATETIME | JsonType.DATETIMEZONE | JsonType.DATETIMEUTC:
                editor = BetterDateTimeEditor(parent)
            case _ if item.json_type in TEXT_MULTI_FAMILY:
                text_len = len(str(item.value or ""))
                limit = get_multiline_edit_warning_limit_chars()
                if not self._confirm_large_text_edit(
                    parent,
                    text_len=text_len,
                    limit=limit,
                    title="Large multiline text",
                    kind="Multiline value",
                ):
                    self._notify_status(parent, "Multiline edit cancelled", 2000)
                    return None
                pidx = QPersistentModelIndex(index)

                def _save_multiline(text: str) -> None:
                    if pidx.isValid():
                        self._commit(pidx, text, Qt.ItemDataRole.EditRole, host=parent)

                QMultilineDialog(parent=parent, text=str(item.value or ""), callback=_save_multiline).open()
                return None
            case JsonType.SECRET_TEXT:
                text_len = len(str(item.value or ""))
                limit = get_multiline_edit_warning_limit_chars()
                if not self._confirm_large_text_edit(
                    parent,
                    text_len=text_len,
                    limit=limit,
                    title="Large secret text",
                    kind="Secret value",
                ):
                    self._notify_status(parent, "Secret text edit cancelled", 2000)
                    return None

                pidx = QPersistentModelIndex(index)

                def _save_secret_text(text: str) -> None:
                    if pidx.isValid():
                        self._commit(pidx, text, Qt.ItemDataRole.EditRole, host=parent)

                dlg = QMultilineDialog(
                    parent=parent, text=str(item.value or ""), sensitive=True, callback=_save_secret_text
                )
                dlg.setWindowTitle("Edit Secret Text")
                dlg.open()
                return None
            case JsonType.COLOR_RGB | JsonType.COLOR_RGBA:
                pidx = QPersistentModelIndex(index)
                initial = parse_color(item.value if isinstance(item.value, str) else "") or parse_color("#000000")

                dialog = QColorDialog(initial, parent)
                if item.json_type is JsonType.COLOR_RGBA:
                    dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, True)
                dialog.setWindowTitle(
                    "Pick color (RGBA)" if item.json_type is JsonType.COLOR_RGBA else "Pick color (RGB)"
                )

                target_type = item.json_type

                def _on_color_selected(selected) -> None:
                    if not pidx.isValid():
                        return
                    text = color_to_html(selected, target_type)
                    self._commit(pidx, text, Qt.ItemDataRole.EditRole, host=parent)

                dialog.colorSelected.connect(_on_color_selected)
                dialog.open()
                return None

            case JsonType.BYTES | JsonType.ZLIB | JsonType.GZIP:
                try:
                    decoded = decode_bytes(item.value, item.json_type)
                except (ValueError, OSError, zlib.error, binascii.Error) as exc:
                    self._notify_status(parent, f"Decode failed: {exc}", 4000)
                    return None

                if not self._confirm_large_binary_edit(parent, len(decoded)):
                    self._notify_status(parent, "Binary edit cancelled", 2000)
                    return None

                pidx = QPersistentModelIndex(index)

                def _save_binary(data: bytes) -> None:
                    if not pidx.isValid():
                        return
                    encoded = encode_bytes(data, item.json_type)
                    self._commit(pidx, encoded, Qt.ItemDataRole.EditRole, host=parent)

                QHexDialog(parent=parent, data=decoded, callback=_save_binary).open()
                return None

            case _:
                raise ValueError(f"Inappropriate `JsonType` in `ValueDelegate.createEditor()`: {item.json_type=}")

        if editor is not None:
            editor.setFont(self._apply_monospace_font(editor.font()))
            self._mark_editor_open(index)
            if item.json_type in (JsonType.SECRET_LINE, JsonType.SECRET_TEXT):
                self._install_secret_watcher(editor, index)
        return editor

    def _install_secret_watcher(self, editor: QWidget, index: QModelIndex) -> None:
        watcher = _SecretEditorWatcher(self, editor, QPersistentModelIndex(index))
        editor.installEventFilter(watcher)
        for child in editor.findChildren(QWidget):
            child.installEventFilter(watcher)
        self._secret_watchers[editor] = watcher

    def _finalize_secret_editor(self, editor: QWidget, index: QPersistentModelIndex) -> None:
        if editor is None or not index.isValid():
            return
        self.commitData.emit(editor)
        self.closeEditor.emit(editor, self.EndEditHint.NoHint)

    def destroyEditor(self, editor, index) -> None:  # type: ignore[override]
        watcher = self._secret_watchers.pop(editor, None)
        if watcher is not None:
            watcher.cleanup()
        super().destroyEditor(editor, index)

    def setEditorData(self, editor: QWidget, index: QModelIndex):
        source_index = self._source_index(index)
        item: JsonTreeItem = source_index.internalPointer()
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
            category = self._category_for_json_type(item.json_type)
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

        super().setEditorData(editor, index)

    def setModelData(self, editor: QWidget, model: QAbstractItemModel, index: QModelIndex):
        if isinstance(editor, QBigIntSpinBox):
            self._commit(index, editor.value(), Qt.ItemDataRole.EditRole, host=editor)
            return

        if isinstance(editor, QMpqSpinBox):
            source_index = self._source_index(index)
            item: JsonTreeItem = source_index.internalPointer()
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

        if isinstance(editor, _SecretLineEdit):
            self._commit(index, editor.text(), Qt.ItemDataRole.EditRole, host=editor)
            return

        if isinstance(editor, QLineEdit):
            self._commit(index, editor.text(), Qt.ItemDataRole.EditRole, host=editor)
            return

        if isinstance(editor, AffixCompositeEditor):
            candidate = editor.build_value()
            validated = validate_affix_value(candidate)
            if validated is None:
                editor.set_invalid(True)
                return
            editor.set_invalid(False)
            if self._commit(index, validated, Qt.ItemDataRole.EditRole, host=editor):
                tab = self._find_tab(editor)
                mru = getattr(tab, "affix_mru", None)
                if mru is not None and hasattr(mru, "push"):
                    mru.push(validated.kind, validated.affix)
            return

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
            case JsonType.DATETIMEUTC:
                return DateTimeCategory.DateTimeUTC
            case _:
                return None
