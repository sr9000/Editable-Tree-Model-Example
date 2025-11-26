from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QVBoxLayout, QWidget

from qmultiline_editor import QMultilineEditor
from settings import APPLICATION_ID, MODAL_WINDOW_SIZE

QMULTILINEDIALOG_ID = "QMultilineDialog-19beb602-e9c1-479b-a037-d9dbfbddec65"


class QMultilineDialog(QDialog):
    def __init__(
        self, parent: QWidget | None = None, text: str = "", callback: Callable[[str], None] = lambda _: None
    ) -> None:
        super().__init__(parent)
        self._callback = callback

        self.setWindowTitle("Edit Multiline Text")
        self.setModal(True)
        self.resize(*MODAL_WINDOW_SIZE)

        self.editor = QMultilineEditor(self)
        self.editor.setPlainText(text or "")

        # Controls row
        self.wrapCheckBox = QCheckBox("Word wrap")
        self.wrapCheckBox.setChecked(self.editor.wordWrap())
        self.wrapCheckBox.toggled.connect(self.editor.setWordWrap)
        self.wrapCheckBox.toggled.connect(self._saveSettings)

        self.lineNumbersCheckBox = QCheckBox("Line numbers")
        self.lineNumbersCheckBox.setChecked(self.editor.lineNumbersVisible())
        self.lineNumbersCheckBox.toggled.connect(self.editor.setLineNumbersVisible)
        self.lineNumbersCheckBox.toggled.connect(self._saveSettings)

        self.monospacedCheckBox = QCheckBox("Monospaced")
        self.monospacedCheckBox.setChecked(self.editor.isMonospaced())
        self.monospacedCheckBox.toggled.connect(self.editor.setMonospaced)
        self.monospacedCheckBox.toggled.connect(self._saveSettings)

        controls = QHBoxLayout()
        controls.addWidget(self.wrapCheckBox)
        controls.addWidget(self.lineNumbersCheckBox)
        controls.addWidget(self.monospacedCheckBox)
        controls.addStretch(1)

        # Buttons
        self.buttonBox = QDialogButtonBox(self)
        self.buttonBox.addButton(QDialogButtonBox.StandardButton.Ok).clicked.connect(self.accept)
        self.buttonBox.addButton(QDialogButtonBox.StandardButton.Cancel).clicked.connect(self.reject)

        # Layout
        self._layout = QVBoxLayout(self)
        self._layout.addLayout(controls)
        self._layout.addWidget(self.editor)
        self._layout.addWidget(self.buttonBox)

        self.setLayout(self._layout)

        # Restore settings after UI is fully initialized
        self._restoreSettings()

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
