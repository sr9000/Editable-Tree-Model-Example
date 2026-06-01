from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QLineEdit, QStyleOptionViewItem, QWidget

from delegates.base import _TextEditorDelegateBase, paint_editor_underlay
from delegates.edit_context import DefaultEditContext, DelegateEditContext
from delegates.validation_badge import draw_severity_badge
from editors.inline.caps_safe_line import _CapsLockSafeLineEdit
from themes import LIGHT_DEFAULT
from themes.spec import ThemeSpec
from tree.model_roles import VALIDATION_SEVERITY_ROLE


def _tab_adapter_context(host) -> DelegateEditContext:
    """Fallback when no edit context was injected; performs no parent walk."""
    return DefaultEditContext()


class NameDelegate(_TextEditorDelegateBase):
    def __init__(
        self,
        parent=None,
        *,
        theme: ThemeSpec | None = None,
        edit_context: DelegateEditContext | None = None,
    ):
        super().__init__(parent)
        self._theme = theme or LIGHT_DEFAULT
        self._monospace_fields_enabled = False
        self._mono_family = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()
        self._edit_context: DelegateEditContext | None = edit_context

    def set_edit_context(self, context: DelegateEditContext | None) -> None:
        self._edit_context = context

    def _context_for(self, host) -> DelegateEditContext:
        if self._edit_context is not None:
            return self._edit_context
        return _tab_adapter_context(host)

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

    def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex) -> None:  # type: ignore[override]
        super().initStyleOption(option, index)
        option.font = self._apply_monospace_font(option.font)

    def paint(self, painter, option, index) -> None:  # type: ignore[override]
        if self._is_editor_open(index):
            opt = QStyleOptionViewItem(option)
            self.initStyleOption(opt, index)
            paint_editor_underlay(painter, opt, option.widget)
            return
        severity = index.data(VALIDATION_SEVERITY_ROLE)
        if severity is not None:
            opt = QStyleOptionViewItem(option)
            self.initStyleOption(opt, index)
            draw_severity_badge(painter, opt, severity, self._theme)
            return
        super().paint(painter, option, index)

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget:
        editor = _CapsLockSafeLineEdit(parent)
        editor.setFont(self._apply_monospace_font(editor.font()))
        self._mark_editor_open(index)
        return editor

    def setEditorData(self, editor: QLineEdit, index: QModelIndex):
        editor.setText(str(index.data(Qt.ItemDataRole.EditRole) or ""))

    def setModelData(self, editor: QLineEdit, model: QAbstractItemModel, index: QModelIndex):
        self._context_for(editor).commit(index, editor.text(), Qt.ItemDataRole.EditRole)
