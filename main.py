import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QApplication,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class AppDemo(QMainWindow):
    def __init__(self):
        super(AppDemo, self).__init__()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout(self.central_widget)

        label = QLabel("Hello World", self)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AppDemo()
    window.show()
    sys.exit(app.exec())
