import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow


def _resolve_app_icon() -> QIcon:
    """Return the bundled application icon, or an empty QIcon if missing.

    In a PyInstaller one-file build the data tree is unpacked under
    ``sys._MEIPASS``; in a normal source checkout it lives next to the
    repository root.
    """
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    icon_path = base / "packaging" / "linux" / "editabletreemodel.png"
    if icon_path.is_file():
        return QIcon(str(icon_path))
    return QIcon()


def main():
    filename = ""

    if len(sys.argv) == 2:
        filename = sys.argv[1]

    app = QApplication(sys.argv)
    # Force the cross-platform Fusion style so hover/selection palettes are
    # consistent and themable on every platform. Notably it tames the bright
    # blue native ``State_MouseOver`` highlight on Windows (issue #05).
    if sys.platform.startswith("win"):
        app.setStyle("Fusion")
    icon = _resolve_app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    window = MainWindow(filename)
    window.show_with_restored_mode()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
