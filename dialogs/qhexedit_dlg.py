from typing import Callable

from PySide6.QtCore import QSettings
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QStatusBar, QVBoxLayout, QWidget

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
        self._applyGlobalEditorFontSettings()

        # Status bar
        self.statusBar = QStatusBar(self)
        self.editor.currentAddressChanged.connect(self.onAddressChanged)

        # Controls row
        self.addressCheckBox = QCheckBox("Address area")
        self.addressCheckBox.setChecked(self.editor.addressArea())
        self.addressCheckBox.toggled.connect(self.editor.setAddressArea)
        self.addressCheckBox.toggled.connect(self._saveSettings)

        self.asciiCheckBox = QCheckBox("ASCII area")
        self.asciiCheckBox.setChecked(self.editor.asciiArea())
        self.asciiCheckBox.toggled.connect(self.editor.setAsciiArea)
        self.asciiCheckBox.toggled.connect(self._saveSettings)

        self.highlightingCheckBox = QCheckBox("Modified bytes")
        self.highlightingCheckBox.setChecked(self.editor.highlighting())
        self.highlightingCheckBox.toggled.connect(self.editor.setHighlighting)
        self.highlightingCheckBox.toggled.connect(self._saveSettings)

        self.capsCheckBox = QCheckBox("CAPS")
        self.capsCheckBox.setChecked(self.editor.hexCaps())
        self.capsCheckBox.toggled.connect(self.editor.setHexCaps)
        self.capsCheckBox.toggled.connect(self._saveSettings)

        controls = QHBoxLayout()
        controls.addWidget(self.addressCheckBox)
        controls.addWidget(self.asciiCheckBox)
        controls.addWidget(self.highlightingCheckBox)
        controls.addWidget(self.capsCheckBox)
        controls.addStretch(1)

        # Buttons
        self.buttonBox = QDialogButtonBox(self)
        self.buttonBox.addButton(QDialogButtonBox.StandardButton.Ok).clicked.connect(self.accept)
        self.buttonBox.addButton(QDialogButtonBox.StandardButton.Cancel).clicked.connect(self.reject)

        # Layout
        self._layout = QVBoxLayout(self)
        self._layout.addLayout(controls)
        self._layout.addWidget(self.editor)
        self._layout.addWidget(self.statusBar)
        self._layout.addWidget(self.buttonBox)

        self.setLayout(self._layout)

        # Restore settings after UI is fully initialized
        self._restoreSettings()

    def _applyGlobalEditorFontSettings(self) -> None:
        settings = QSettings(APPLICATION_ID, "app")
        mono_family = str(settings.value("view/monospace_font_family", "", type=str) or "")
        point_size = int(settings.value("view/editor_font_point_size", 10, type=int) or 10)

        font = QFont(self.editor.font())
        if mono_family:
            font.setFamily(mono_family)
        if point_size > 0:
            font.setPointSize(max(6, point_size))
        self.editor.setFont(font)

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
        settings.setValue("CAPS", self.capsCheckBox.isChecked())

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
        caps = bool(settings.value("CAPS", True, type=bool))

        self.addressCheckBox.setChecked(address_area)
        self.asciiCheckBox.setChecked(ascii_area)
        self.highlightingCheckBox.setChecked(highlighting)
        self.capsCheckBox.setChecked(caps)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        """Save geometry when dialog is resized"""
        super().resizeEvent(event)
        self._saveSettings()

    def moveEvent(self, event) -> None:  # type: ignore[override]
        """Save geometry when dialog is moved"""
        super().moveEvent(event)
        self._saveSettings()

    def onAddressChanged(self, address):
        """Handle address change"""
        self.statusBar.showMessage(f"Address: 0x{address:08X}")
