import sys

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from settings import WINDOW_DEFAULT_SIZE


def main():
    filename = ""

    if len(sys.argv) == 2:
        filename = sys.argv[1]

    app = QApplication(sys.argv)
    window = MainWindow(filename)
    window.resize(*WINDOW_DEFAULT_SIZE)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
