import sys

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow


def main():
    filename = ""

    if len(sys.argv) == 2:
        filename = sys.argv[1]

    app = QApplication(sys.argv)
    window = MainWindow(filename)
    window.show_with_restored_mode()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
