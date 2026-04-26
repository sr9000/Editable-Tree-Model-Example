import sys

from PySide6.QtWidgets import QApplication

from settings import WINDOW_DEFAULT_SIZE
from app.main_window import MainWindow


def main():
    filename = "data.yaml"

    if len(sys.argv) == 2:
        filename = sys.argv[1]
    elif not filename:
        print("Usage: python main.py <file-name.yaml>")
        sys.exit(1)

    app = QApplication(sys.argv)
    window = MainWindow(filename)
    window.resize(*WINDOW_DEFAULT_SIZE)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
