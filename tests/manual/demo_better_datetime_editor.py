"""Manual demo for BetterDateTimeEditor."""

from datetime import datetime

from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from editors.inline.datetime.better_dt_editor import BetterDateTimeEditor


def main() -> None:
    app = QApplication.instance() or QApplication([])

    widget = QWidget()
    widget.setWindowTitle("BetterDateTimeEditor Demo")

    layout = QVBoxLayout(widget)
    layout.addWidget(QLabel("Edit the value and use arrow keys to increment segments."))

    editor = BetterDateTimeEditor()
    editor.setValue(datetime.now().astimezone().replace(microsecond=123456))
    layout.addWidget(editor)

    widget.show()
    app.exec()


if __name__ == "__main__":
    main()
