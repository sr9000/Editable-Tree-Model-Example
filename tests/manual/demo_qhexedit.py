#!/usr/bin/env python3
"""Simple test for QHexEdit widget"""

import sys

from PySide6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QPushButton, QVBoxLayout, QWidget

from editors.windowed.hexedit import QHexEdit


class DemoQHexEditWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QHexEdit Demo")
        self.resize(800, 600)

        # Create central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Create hex editor
        self.hexEdit = QHexEdit()
        layout.addWidget(self.hexEdit)

        # Create button bar
        buttonLayout = QHBoxLayout()
        layout.addLayout(buttonLayout)

        # Add buttons
        loadBtn = QPushButton("Load Sample Data")
        loadBtn.clicked.connect(self.loadSampleData)
        buttonLayout.addWidget(loadBtn)

        clearBtn = QPushButton("Clear")
        clearBtn.clicked.connect(self.clearData)
        buttonLayout.addWidget(clearBtn)

        readOnlyBtn = QPushButton("Toggle Read-Only")
        readOnlyBtn.clicked.connect(self.toggleReadOnly)
        buttonLayout.addWidget(readOnlyBtn)

        capsBtn = QPushButton("Toggle Hex Caps")
        capsBtn.clicked.connect(self.toggleHexCaps)
        buttonLayout.addWidget(capsBtn)

        buttonLayout.addStretch()

        # Connect signals
        self.hexEdit.currentAddressChanged.connect(self.onAddressChanged)
        self.hexEdit.currentSizeChanged.connect(self.onSizeChanged)
        self.hexEdit.dataChanged.connect(self.onDataChanged)

        # Load initial data
        self.loadSampleData()

    def loadSampleData(self):
        """Load sample data into the hex editor"""
        # Create some sample data
        data = bytearray(range(256))
        data.extend(b"Hello, World! This is a test of the QHexEdit widget.\x00")
        data.extend(bytes([0xFF, 0xFE, 0xFD, 0xFC, 0xFB, 0xFA]))

        self.hexEdit.setData(data)
        self.statusBar().showMessage(f"Loaded {len(data)} bytes")

    def clearData(self):
        """Clear all data"""
        self.hexEdit.setData(bytearray())
        self.statusBar().showMessage("Cleared data")

    def toggleReadOnly(self):
        """Toggle read-only mode"""
        readOnly = not self.hexEdit.isReadOnly()
        self.hexEdit.setReadOnly(readOnly)
        self.statusBar().showMessage(f"Read-only: {readOnly}")

    def toggleHexCaps(self):
        """Toggle hex capitalization"""
        hexCaps = not self.hexEdit.hexCaps()
        self.hexEdit.setHexCaps(hexCaps)
        self.statusBar().showMessage(f"Hex caps: {hexCaps}")

    def onAddressChanged(self, address):
        """Handle address change"""
        self.statusBar().showMessage(f"Address: 0x{address:08X}")

    def onSizeChanged(self, size):
        """Handle size change"""
        print(f"Size changed: {size} bytes")

    def onDataChanged(self):
        """Handle data change"""
        print("Data changed")


def demo():
    app = QApplication(sys.argv)
    window = DemoQHexEditWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    demo()
