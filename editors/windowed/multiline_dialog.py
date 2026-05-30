from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QDialog, QVBoxLayout, QWidget

from editors.windowed.multiline_widget import QMultilineEditor
from settings import APPLICATION_ID, MODAL_WINDOW_SIZE
from ui.dialogs import Ui_QMultilineDialog

QMULTILINEDIALOG_ID = "QMultilineDialog-19beb602-e9c1-479b-a037-d9dbfbddec65"


class QMultilineDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        text: str = "",
        sensitive: bool = False,
        callback: Callable[[str], None] = lambda _: None,
    ) -> None:
        super().__init__(parent)
        self._ui = Ui_QMultilineDialog()
        self._ui.setupUi(self)
        self._callback = callback

        self.setModal(True)
        self.resize(*MODAL_WINDOW_SIZE)

        self.editor = QMultilineEditor(self._ui.editorHost)
        editor_layout = QVBoxLayout(self._ui.editorHost)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.addWidget(self.editor)
        if sensitive:
            self.editor.setSensitive(True)
        self.editor.setPlainText(text or "")
        self._applyGlobalEditorFontSettings()

        self.wrapCheckBox = self._ui.wrapCheckBox
        self.wrapCheckBox.setChecked(self.editor.wordWrap())
        self.wrapCheckBox.toggled.connect(self.editor.setWordWrap)
        self.wrapCheckBox.toggled.connect(self._saveSettings)

        self.lineNumbersCheckBox = self._ui.lineNumbersCheckBox
        self.lineNumbersCheckBox.setChecked(self.editor.lineNumbersVisible())
        self.lineNumbersCheckBox.toggled.connect(self.editor.setLineNumbersVisible)
        self.lineNumbersCheckBox.toggled.connect(self._saveSettings)

        self.monospacedCheckBox = self._ui.monospacedCheckBox
        self.monospacedCheckBox.setChecked(self.editor.isMonospaced())
        self.monospacedCheckBox.toggled.connect(self.editor.setMonospaced)
        self.monospacedCheckBox.toggled.connect(self._saveSettings)

        self.buttonBox = self._ui.buttonBox
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        # Restore settings after UI is fully initialized
        self._restoreSettings()

    def _applyGlobalEditorFontSettings(self) -> None:
        settings = QSettings(APPLICATION_ID, "app")
        regular_family = str(settings.value("view/regular_font_family", "", type=str) or "")
        mono_family = str(settings.value("view/monospace_font_family", "", type=str) or "")
        point_size_raw = settings.value("view/editor_font_point_size", 10, type=int)
        point_size = int(point_size_raw or 10)

        if regular_family:
            self.editor.setRegularFontFamily(regular_family)
        if mono_family:
            self.editor.setMonospaceFontFamily(mono_family)
        self.editor.setEditorPointSize(point_size)

    def text(self) -> str:
        return self.editor.toPlainText()

    def accept(self) -> None:
        super().accept()
        self._callback(self.text())

    def _saveSettings(self) -> None:
        """Save dialog preferences to QSettings"""
        settings = QSettings(APPLICATION_ID, QMULTILINEDIALOG_ID)
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("wordWrap", self.wrapCheckBox.isChecked())
        settings.setValue("lineNumbers", self.lineNumbersCheckBox.isChecked())
        settings.setValue("monospaced", self.monospacedCheckBox.isChecked())

    def _restoreSettings(self) -> None:
        """Restore dialog preferences from QSettings"""
        settings = QSettings(APPLICATION_ID, QMULTILINEDIALOG_ID)

        # Restore geometry if available
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        # Restore checkbox states
        word_wrap = bool(settings.value("wordWrap", True, type=bool))
        line_numbers = bool(settings.value("lineNumbers", True, type=bool))
        monospaced = bool(settings.value("monospaced", False, type=bool))

        self.wrapCheckBox.setChecked(word_wrap)
        self.lineNumbersCheckBox.setChecked(line_numbers)
        self.monospacedCheckBox.setChecked(monospaced)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        """Save geometry when dialog is resized"""
        super().resizeEvent(event)
        self._saveSettings()

    def moveEvent(self, event) -> None:  # type: ignore[override]
        """Save geometry when dialog is moved"""
        super().moveEvent(event)
        self._saveSettings()
