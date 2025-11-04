#!/usr/bin/env python3
"""Test script to verify highlighting feature in QHexEdit"""

import sys

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from qhexedit import QHexEdit


class DemoHighlightingQHexEditWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QHexEdit Highlighting Test")
        self.resize(800, 600)

        # Create central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Create hex editor
        self.hexEdit = QHexEdit()
        layout.addWidget(self.hexEdit)

        # Create control panel
        controlLayout = QHBoxLayout()
        layout.addLayout(controlLayout)

        # Highlighting toggle
        self.highlightingCheckbox = QCheckBox("Enable Highlighting")
        self.highlightingCheckbox.setChecked(True)
        self.highlightingCheckbox.stateChanged.connect(self.toggleHighlighting)
        controlLayout.addWidget(self.highlightingCheckbox)

        # Color picker
        colorBtn = QPushButton("Choose Highlighting Color")
        colorBtn.clicked.connect(self.chooseHighlightingColor)
        controlLayout.addWidget(colorBtn)

        # Modify button
        modifyBtn = QPushButton("Modify Byte at Cursor")
        modifyBtn.clicked.connect(self.modifyByte)
        controlLayout.addWidget(modifyBtn)

        # Load data button
        loadBtn = QPushButton("Load Sample Data")
        loadBtn.clicked.connect(self.loadSampleData)
        controlLayout.addWidget(loadBtn)

        controlLayout.addStretch()

        # Connect signals
        self.hexEdit.dataChanged.connect(self.onDataChanged)

        # Load initial data
        self.loadSampleData()

        # Display initial state
        self.updateStatus()

    def loadSampleData(self):
        """Load sample data into the hex editor"""
        data = bytearray(range(256))
        self.hexEdit.setData(data)
        self.statusBar().showMessage(f"Loaded {len(data)} bytes. Try modifying data to see highlighting.")

    def toggleHighlighting(self, state):
        """Toggle highlighting on/off"""
        enabled = bool(state)
        self.hexEdit.setHighlighting(enabled)
        self.statusBar().showMessage(f"Highlighting: {'Enabled' if enabled else 'Disabled'}")

    def chooseHighlightingColor(self):
        """Choose highlighting color"""
        current_color = self.hexEdit.highlightingColor()
        color = QColorDialog.getColor(current_color, self, "Choose Highlighting Color")
        if color.isValid():
            self.hexEdit.setHighlightingColor(color)
            self.statusBar().showMessage(f"Highlighting color set to: {color.name()}")

    def modifyByte(self):
        """Modify byte at current cursor position"""
        pos = self.hexEdit.cursorPosition() // 2
        if pos < self.hexEdit.data().__len__():
            current_byte = self.hexEdit.dataAt(pos, 1)[0]
            new_byte = (current_byte + 1) % 256
            self.hexEdit.replace(pos, new_byte)
            self.statusBar().showMessage(f"Modified byte at 0x{pos:04X}: 0x{current_byte:02X} -> 0x{new_byte:02X}")

    def onDataChanged(self):
        """Handle data change"""
        self.updateStatus()

    def updateStatus(self):
        """Update status display"""
        highlighting_state = "Enabled" if self.hexEdit.highlighting() else "Disabled"
        color = self.hexEdit.highlightingColor()
        self.statusBar().showMessage(f"Highlighting: {highlighting_state} | Color: {color.name() if color else 'None'}")


def demo():
    app = QApplication(sys.argv)
    window = DemoHighlightingQHexEditWindow()
    window.show()

    # Print instructions
    print("=" * 70)
    print("QHexEdit Highlighting Demo")
    print("=" * 70)
    print("\nInstructions:")
    print("1. The editor is loaded with sample data (0x00 - 0xFF)")
    print("2. Click on a byte and modify it (type a new hex value)")
    print("3. Modified bytes should appear highlighted (yellow background by default)")
    print("4. Use the checkbox to toggle highlighting on/off")
    print("5. Use 'Choose Highlighting Color' to change the highlight color")
    print("6. Use 'Modify Byte at Cursor' to programmatically change a byte")
    print("\nExpected behavior:")
    print("- When highlighting is ENABLED: modified bytes have colored background")
    print("- When highlighting is DISABLED: modified bytes use normal colors")
    print("=" * 70)

    sys.exit(app.exec())


if __name__ == "__main__":
    demo()
