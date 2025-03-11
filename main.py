import sys

from PySide6.QtWidgets import QApplication

from ui import MainWindow


def main():
    filename = "data.yaml"

    if len(sys.argv) == 2:
        filename = sys.argv[1]
    elif not filename:
        print("Usage: python main.py <file-name.yaml>")
        sys.exit(1)

    app = QApplication(sys.argv)
    window = MainWindow(filename)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
