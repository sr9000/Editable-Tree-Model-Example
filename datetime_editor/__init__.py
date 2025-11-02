from datetime import date, datetime, time

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

from .enums import DateTimeCategory
from .regex import parse_datetime_text
from .validator import DateTimeValidator


class DateTimeEditor(QWidget):
    """
    Like QDateEdit and QDateTimeEdit BUT supports editing dates and times in different formats:
    Date Only:
      - date only       "YYYY-MM-DD"                       (year, month, day)
    Time Only:
      - time only                  "hh:mm:ss"              (hour, minute, second)
      - time+ms                    "hh:mm:ss.123456"       (hour, minute, second, microsecond)
    Date Time:
      - datetime        "YYYY-MM-DD hh:mm:ss"              (year, month, day, hour, minute, second)
      - tdatetime       "YYYY-MM-DDThh:mm:ss"              (year, month, day, hour, minute, second)
      - datetime+ms     "YYYY-MM-DD hh:mm:ss.123456"       (year, month, day, hour, minute, second, microsecond)
      - tdatetime+ms    "YYYY-MM-DDThh:mm:ss.123456"       (year, month, day, hour, minute, second, microsecond)
    Date Time with TZ info:
      - datetime+tz     "YYYY-MM-DD hh:mm:ss+hh:mm"        (year, month, day, hour, minute, second, timezone offset ([+-]HH:MM))
      - tdatetime+tz    "YYYY-MM-DDThh:mm:ss+hh:mm"        (year, month, day, hour, minute, second, timezone offset ([+-]HH:MM))
      - datetime+ms+tz  "YYYY-MM-DD hh:mm:ss.123456+hh:mm" (year, month, day, hour, minute, second, microsecond, timezone offset ([+-]HH:MM))
      - tdatetime+ms+tz "YYYY-MM-DDThh:mm:ss.123456+hh:mm" (year, month, day, hour, minute, second, microsecond, timezone offset ([+-]HH:MM))
    """

    editingFinished = Signal()
    valueChanged = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._editor = QLineEdit()
        self._validator = DateTimeValidator(self)
        self._editor.setValidator(self._validator)
        self._editor.editingFinished.connect(self._on_editing_finished)
        layout = QVBoxLayout()
        layout.addWidget(self._editor)
        self.setLayout(layout)
        self._value = None
        self._category = None

    def value(self):
        return self._value

    @staticmethod
    def get_category(value):
        if isinstance(value, datetime):
            if value.tzinfo:
                return DateTimeCategory.DateTimeWithTZ
            return DateTimeCategory.DateTime
        elif isinstance(value, date):
            return DateTimeCategory.Date
        elif isinstance(value, time):
            return DateTimeCategory.Time
        return None

    def setValue(self, value):
        self._value = value
        self._category = self.get_category(value)
        self._editor.setText(str(value))

    @Slot()
    def _on_editing_finished(self):
        text = self._editor.text()
        self._value = parse_datetime_text(text, self._category)
        self.valueChanged.emit(self._value)
        self.editingFinished.emit()
