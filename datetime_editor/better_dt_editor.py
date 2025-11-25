from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional, Union

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFocusEvent, QKeyEvent, QValidator
from PySide6.QtWidgets import QLineEdit

from .enums import DateTimeCategory
from .regex import PARTIAL_DATETIME_RE, parse_datetime_text
from .validator import DateTimeValidator


ValueType = Union[date, time, datetime, None]


@dataclass
class _Segment:
    # name identifies the part (year, hour, tz_hour, ...)
    name: str
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start


class BetterDateTimeEditor(QLineEdit):
    """
    Looks like QDateTimeEdit but supports python datetime.date, datetime.time, and datetime.datetime
    formats for input and display.

    Uses DateTimeValidator for input validation.

    Preserves original user input formatting when loading and saving values.

    [!important] Supports incrementing/decrementing date and time parts via keyboard or mouse.
    - all parsed parts are incrementable/decrementable
    - missing parts are omitted from the editor UI but can be added via typing
    - typing supports partial inputs and caret movement
    """

    valueChanged = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._category: Optional[DateTimeCategory] = None
        self._value: ValueType = None
        self._last_valid_text: str = ""
        self._segments: list[_Segment] = []
        self._validator = DateTimeValidator(self)
        self.setValidator(self._validator)
        self.textChanged.connect(self._handle_text_changed)

    # ------------------------------------------------------------------
    # Public API
    def category(self) -> Optional[DateTimeCategory]:
        return self._category

    def setCategory(self, category: Optional[DateTimeCategory]) -> None:
        self._category = category
        self._validator.category = category
        self._update_state_from_text(self.text())

    def value(self) -> ValueType:
        return self._value

    def setValue(self, value: ValueType) -> None:
        text, category = self._format_value(value)
        self._value = value
        self._category = category
        self._validator.category = category
        self.blockSignals(True)
        self.setText(text)
        self.blockSignals(False)
        self._last_valid_text = text
        self._segments = self._extract_segments(text)

    # ------------------------------------------------------------------
    # Text/validation handling
    def _handle_text_changed(self, text: str) -> None:
        state = self.validator().validate(text, self.cursorPosition())[0]
        if state == QValidator.State.Acceptable:
            parsed = parse_datetime_text(text, self._category)
            if parsed is not None:
                self._value = parsed
                self._last_valid_text = text
                self._segments = self._extract_segments(text)
                self.valueChanged.emit(parsed)
        elif state == QValidator.State.Intermediate:
            self._segments = self._extract_segments(text)
        else:  # Invalid
            self.blockSignals(True)
            self.setText(self._last_valid_text)
            self.blockSignals(False)
            self.setCursorPosition(len(self._last_valid_text))

    def _update_state_from_text(self, text: str) -> None:
        parsed = parse_datetime_text(text, self._category)
        if parsed is not None:
            self._value = parsed
            self._last_valid_text = text
        self._segments = self._extract_segments(text)

    def _extract_segments(self, text: str) -> list[_Segment]:
        segments: list[_Segment] = []
        match = PARTIAL_DATETIME_RE.fullmatch(text.upper())
        if not match:
            return segments
        cursor = 0
        for name, value in match.groupdict().items():
            if value is None:
                continue
            idx = text.upper().find(value.upper(), cursor)
            if idx == -1:
                continue
            segments.append(_Segment(name=name, start=idx, end=idx + len(value)))
            cursor = idx + len(value)
        return segments

    # ------------------------------------------------------------------
    # Increment/decrement behavior
    def stepUp(self):
        self._step(+1)

    def stepDown(self):
        self._step(-1)

    def _step(self, delta: int) -> None:
        if not self._segments or self._value is None:
            return
        idx = self._segment_index_at_cursor()
        if idx is None:
            idx = len(self._segments) - 1
        segment = self._segments[idx]
        new_text = self._apply_delta_to_segment(segment, delta)
        if new_text is None:
            return
        self.blockSignals(True)
        self.setText(new_text)
        self.blockSignals(False)
        self.setCursorPosition(segment.start + segment.length)

    def _segment_index_at_cursor(self) -> Optional[int]:
        cursor = self.cursorPosition()
        for i, seg in enumerate(self._segments):
            if seg.start <= cursor <= seg.end:
                return i
        return None

    def _apply_delta_to_segment(self, segment: _Segment, delta: int) -> Optional[str]:
        if self._value is None:
            return None
        value = self._as_datetime(self._value)
        if segment.name == "year":
            value = value.replace(year=max(1, min(9999, value.year + delta)))
        elif segment.name == "month":
            month = (value.month - 1 + delta) % 12 + 1
            year = value.year + (value.month - 1 + delta) // 12
            value = value.replace(year=year, month=month)
        elif segment.name == "day":
            value += timedelta(days=delta)
        elif segment.name == "hour":
            value += timedelta(hours=delta)
        elif segment.name == "minute":
            value += timedelta(minutes=delta)
        elif segment.name == "second":
            value += timedelta(seconds=delta)
        elif segment.name == "microsecond":
            value += timedelta(microseconds=delta)
        else:
            return None

        self._value = self._restore_type(value)
        formatted = self._format_value(self._value)[0]
        self._segments = self._extract_segments(formatted)
        self._last_valid_text = formatted
        return formatted

    # ------------------------------------------------------------------
    # Event handling
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key_Up, Qt.Key_PageUp):
            self.stepUp()
            event.accept()
            return
        if event.key() in (Qt.Key_Down, Qt.Key_PageDown):
            self.stepDown()
            event.accept()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        if self.validator() and self.validator().validate(self.text(), 0)[0] != QValidator.State.Acceptable:
            self.blockSignals(True)
            self.setText(self._last_valid_text)
            self.blockSignals(False)
        super().focusOutEvent(event)

    # ------------------------------------------------------------------
    # Helpers
    def _format_value(self, value: ValueType) -> tuple[str, Optional[DateTimeCategory]]:
        if value is None:
            return "", None
        if isinstance(value, datetime):
            if value.tzinfo:
                return value.isoformat(), DateTimeCategory.DateTimeWithTZ
            return value.isoformat(sep=" "), DateTimeCategory.DateTime
        if isinstance(value, date):
            return value.isoformat(), DateTimeCategory.Date
        if isinstance(value, time):
            return value.isoformat(), DateTimeCategory.Time
        raise TypeError("Unsupported value type")

    def _as_datetime(self, value: ValueType) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, time())
        if isinstance(value, time):
            return datetime.combine(date.today(), value)
        raise TypeError("Unsupported value type")

    def _restore_type(self, value: datetime) -> ValueType:
        match self._category:
            case DateTimeCategory.Date:
                return value.date()
            case DateTimeCategory.Time:
                return value.time()
            case DateTimeCategory.DateTime:
                return value.replace(tzinfo=None)
            case DateTimeCategory.DateTimeWithTZ:
                if value.tzinfo is None:
                    value = value.replace(tzinfo=timezone.utc)
                return value
            case _:
                return value
