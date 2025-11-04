from typing import Callable

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QVBoxLayout, QWidget

from qhexedit import QHexEdit
from settings import APPLICATION_ID, MODAL_WINDOW_SIZE

QHEXDIALOG_ID = "QHexDialog-7a927c68-412c-4f06-8ce6-2158dde1314e"


class QHexDialog(QDialog):
    def __init__(
        self, parent: QWidget | None = None, data: bytes = b"", callback: Callable[[bytes], None] = lambda _: None
    ) -> None:
        super().__init__(parent)
        self._callback = callback

        self.setWindowTitle("Edit Binary Data")
        self.setModal(True)
        self.resize(*MODAL_WINDOW_SIZE)

        self.editor = QHexEdit(self)
        self.editor.setData(data or b"")

        # Controls row
        self.addressCheckBox = QCheckBox("Address area")
        self.addressCheckBox.setChecked(True)
        self.addressCheckBox.toggled.connect(self.editor.setAddressArea)
        self.addressCheckBox.toggled.connect(self._saveSettings)

        self.asciiCheckBox = QCheckBox("ASCII area")
        self.asciiCheckBox.setChecked(True)
        self.asciiCheckBox.toggled.connect(self.editor.setAsciiArea)
        self.asciiCheckBox.toggled.connect(self._saveSettings)

        self.highlightingCheckBox = QCheckBox("Highlighting")
        self.highlightingCheckBox.setChecked(True)
        self.highlightingCheckBox.toggled.connect(self.editor.setHighlighting)
        self.highlightingCheckBox.toggled.connect(self._saveSettings)

        controls = QHBoxLayout()
        controls.addWidget(self.addressCheckBox)
        controls.addWidget(self.asciiCheckBox)
        controls.addWidget(self.highlightingCheckBox)
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

    def data(self) -> bytes:
        return bytes(self.editor.data())

    def accept(self) -> None:
        super().accept()
        self._callback(self.data())

    def _saveSettings(self) -> None:
        """Save dialog preferences to QSettings"""
        settings = QSettings(APPLICATION_ID, QHEXDIALOG_ID)
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("addressArea", self.addressCheckBox.isChecked())
        settings.setValue("asciiArea", self.asciiCheckBox.isChecked())
        settings.setValue("highlighting", self.highlightingCheckBox.isChecked())

    def _restoreSettings(self) -> None:
        """Restore dialog preferences from QSettings"""
        settings = QSettings(APPLICATION_ID, QHEXDIALOG_ID)

        # Restore geometry if available
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        # Restore checkbox states
        address_area = bool(settings.value("addressArea", True, type=bool))
        ascii_area = bool(settings.value("asciiArea", True, type=bool))
        highlighting = bool(settings.value("highlighting", True, type=bool))

        self.addressCheckBox.setChecked(address_area)
        self.asciiCheckBox.setChecked(ascii_area)
        self.highlightingCheckBox.setChecked(highlighting)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        """Save geometry when dialog is resized"""
        super().resizeEvent(event)
        self._saveSettings()

    def moveEvent(self, event) -> None:  # type: ignore[override]
        """Save geometry when dialog is moved"""
        super().moveEvent(event)
        self._saveSettings()
