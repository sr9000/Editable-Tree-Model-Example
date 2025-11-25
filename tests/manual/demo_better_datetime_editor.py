"""Manual demo for BetterDateTimeEditor."""

from datetime import datetime

from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from datetime_editor.better_dt_editor import BetterDateTimeEditor


def main() -> None:
    app = QApplication.instance() or QApplication([])

    widget = QWidget()
    widget.setWindowTitle("BetterDateTimeEditor Demo")

    layout = QVBoxLayout(widget)
    layout.addWidget(QLabel("Edit the value and use arrow keys to increment segments."))

    editor = BetterDateTimeEditor()
    editor.setValue(datetime.now().replace(microsecond=0))
    layout.addWidget(editor)

    widget.show()
    app.exec()


if __name__ == "__main__":
    main()
