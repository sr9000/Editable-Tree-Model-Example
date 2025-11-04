from typing import Callable

from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QVBoxLayout, QWidget

from . import QHexEdit


class QHexDialog(QDialog):
    def __init__(
        self, parent: QWidget | None = None, data: bytes = b"", callback: Callable[[bytes], None] = lambda _: None
    ) -> None:
        super().__init__(parent)
        self._callback = callback

        self.setWindowTitle("Edit Binary Data")
        self.setModal(True)
        self.resize(800, 500)

        self.editor = QHexEdit(self)
        self.editor.setData(data or b"")

        # Controls row
        self.addressCheckBox = QCheckBox("Address area")
        self.addressCheckBox.setChecked(True)
        self.addressCheckBox.toggled.connect(self.editor.setAddressArea)

        self.asciiCheckBox = QCheckBox("ASCII area")
        self.asciiCheckBox.setChecked(True)
        self.asciiCheckBox.toggled.connect(self.editor.setAsciiArea)

        self.highlightingCheckBox = QCheckBox("Highlighting")
        self.highlightingCheckBox.setChecked(True)
        self.highlightingCheckBox.toggled.connect(self.editor.setHighlighting)

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

    def data(self) -> bytes:
        return bytes(self.editor.data())

    def accept(self) -> None:
        super().accept()
        self._callback(self.data())
