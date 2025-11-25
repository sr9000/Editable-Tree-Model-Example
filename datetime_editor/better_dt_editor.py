from __future__ import annotations

from calendar import monthrange
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
    text: str

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
        state = self._validation_state(text, self.cursorPosition())
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

    def _validation_state(self, text: str, pos: int) -> QValidator.State:
        validator = self.validator()
        if validator is None:
            return QValidator.State.Acceptable
        result = validator.validate(text, pos)
        if isinstance(result, tuple):
            return result[0]
        return result

    def _extract_segments(self, text: str) -> list[_Segment]:
        segments: list[_Segment] = []
        match = PARTIAL_DATETIME_RE.fullmatch(text.upper())
        if not match:
            return segments
        cursor = 0
        for name, value in match.groupdict().items():
            if not value:
                continue
            idx = text.upper().find(value.upper(), cursor)
            if idx == -1:
                continue
            segment_text = text[idx : idx + len(value)]
            segments.append(_Segment(name=name, start=idx, end=idx + len(value), text=segment_text))
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
        result = self._apply_delta_to_segment(segment, delta)
        if result is None:
            return
        new_text, new_cursor = result
        if new_text == self.text():
            return
        self.setText(new_text)
        self.setCursorPosition(min(new_cursor, len(new_text)))

    def _segment_index_at_cursor(self) -> Optional[int]:
        cursor = self.cursorPosition()
        for i, seg in enumerate(self._segments):
            if seg.start <= cursor <= seg.end:
                return i
        return None

    def _segment_by_name(self, name: str) -> Optional[_Segment]:
        for seg in self._segments:
            if seg.name == name:
                return seg
        return None

    def _apply_delta_to_segment(self, segment: _Segment, delta: int) -> Optional[tuple[str, int]]:
        if self._value is None:
            return None
        value = self._as_datetime(self._value)
        if segment.name == "year":
            new_year = max(1, min(9999, value.year + delta))
            max_day = monthrange(new_year, value.month)[1]
            value = value.replace(year=new_year, day=min(value.day, max_day))
        elif segment.name == "month":
            total_months = (value.year - 1) * 12 + (value.month - 1) + delta
            total_months = max(0, min(total_months, 9999 * 12 - 1))
            new_year = total_months // 12 + 1
            new_month = total_months % 12 + 1
            max_day = monthrange(new_year, new_month)[1]
            value = value.replace(year=new_year, month=new_month, day=min(value.day, max_day))
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
        elif segment.name in {"tz_sign", "tz_hour", "tz_minute", "utc"}:
            value = self._ensure_timezone(value)
            total_minutes = self._timezone_minutes(value)
            total_minutes = self._adjust_timezone_minutes(segment.name, total_minutes, delta)
            value = value.replace(tzinfo=timezone(timedelta(minutes=total_minutes)))
            return self._rebuild_timezone_segments(value, segment)
        else:
            return None

        replacement = self._format_segment_value(segment.name, value, segment.length)
        if replacement is None:
            return None

        text = self.text()
        new_text = text[: segment.start] + replacement + text[segment.end :]
        self._value = self._restore_type(value)
        self._segments = self._extract_segments(new_text)
        return new_text, segment.start + len(replacement)

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

    def wheelEvent(self, event) -> None:
        if not self.isReadOnly() and self._segments and self._value is not None:
            delta = event.angleDelta().y()
            if delta > 0:
                self.stepUp()
                event.accept()
                return
            if delta < 0:
                self.stepDown()
                event.accept()
                return
        super().wheelEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        if self._validation_state(self.text(), 0) != QValidator.State.Acceptable:
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

    def _rebuild_timezone_segments(self, value: datetime, anchor: _Segment) -> Optional[tuple[str, int]]:
        tz_segments = [seg for seg in self._segments if seg.name in {"tz_sign", "tz_hour", "tz_minute", "utc"}]
        if not tz_segments:
            return None

        text = self.text()
        new_text = text
        cursor = None
        for seg in sorted(tz_segments, key=lambda s: s.start, reverse=True):
            replacement = self._format_segment_value(seg.name, value, seg.length)
            if replacement is None:
                continue
            new_text = new_text[: seg.start] + replacement + new_text[seg.end :]
            if seg is anchor:
                cursor = seg.start + len(replacement)

        self._value = self._restore_type(value)
        self._segments = self._extract_segments(new_text)
        if cursor is None:
            cursor = anchor.start
        return new_text, cursor

    def _ensure_timezone(self, value: datetime) -> datetime:
        if value.tzinfo is not None:
            return value
        return value.replace(tzinfo=timezone.utc)

    def _timezone_minutes(self, value: datetime) -> int:
        offset = value.tzinfo.utcoffset(value) or timedelta()
        return int(offset.total_seconds() // 60)

    def _clamp_timezone_minutes(self, minutes: int) -> int:
        limit = 14 * 60 + 59
        return max(-limit, min(limit, minutes))

    def _adjust_timezone_minutes(self, part: str, total_minutes: int, delta: int) -> int:
        sign, hours, minutes = self._split_timezone(total_minutes)

        if part == "tz_sign":
            if delta > 0:
                sign = 1
            elif delta < 0:
                sign = -1
        elif part == "tz_hour" and delta != 0:
            step = 1 if delta > 0 else -1
            for _ in range(abs(delta)):
                if step > 0:
                    if sign < 0:
                        if hours > 0:
                            hours -= 1
                        else:
                            sign = 1
                    else:
                        if hours < 14:
                            hours += 1
                else:  # step < 0
                    if sign > 0:
                        if hours > 0:
                            hours -= 1
                        else:
                            sign = -1
                            hours = 0 if minutes else 1  # +00:00 becomes -01:00, +00:30 becomes -00:30
                    else:
                        if hours < 14:
                            hours += 1
        elif part == "tz_minute" and delta != 0:
            minutes = (minutes + delta) % 60
        elif part == "utc":
            if hours == 0 and minutes == 0:
                sign = 1 if delta >= 0 else -1
                hours = 0
                minutes = 0
                if delta != 0:
                    hours = min(14, 1)
            else:
                hours = max(0, min(14, hours + (1 if delta > 0 else -1)))
        return self._compose_timezone(sign, hours, minutes)

    def _format_timezone_string(self, minutes: int) -> str:
        sign = "+" if minutes >= 0 else "-"
        minutes = abs(minutes)
        hours = minutes // 60
        minute_part = minutes % 60
        return f"{sign}{hours:02d}:{minute_part:02d}"

    def _format_segment_value(self, name: str, value: datetime, width: int) -> Optional[str]:
        match name:
            case "year":
                text = f"{value.year:04d}"
            case "month":
                text = f"{value.month:02d}"
            case "day":
                text = f"{value.day:02d}"
            case "hour":
                text = f"{value.hour:02d}"
            case "minute":
                text = f"{value.minute:02d}"
            case "second":
                text = f"{value.second:02d}"
            case "microsecond":
                text = f"{value.microsecond:06d}"
            case "tz_sign":
                minutes = self._timezone_minutes(self._ensure_timezone(value))
                text = "+" if minutes >= 0 else "-"
            case "tz_hour":
                minutes = abs(self._timezone_minutes(self._ensure_timezone(value)))
                hours = minutes // 60
                width = width or 2
                text = str(hours).zfill(width)
            case "tz_minute":
                minutes = abs(self._timezone_minutes(self._ensure_timezone(value))) % 60
                width = width or 2
                text = str(minutes).zfill(width)
            case "utc":
                total = self._timezone_minutes(self._ensure_timezone(value))
                text = "Z" if total == 0 else self._format_timezone_string(total)
            case _:
                return None

        if name not in {"tz_sign", "tz_hour", "tz_minute", "utc"} and width > 0 and len(text) < width:
            text = text.zfill(width)
        return text

    def _split_timezone(self, total_minutes: int) -> tuple[int, int, int]:
        sign = 1 if total_minutes >= 0 else -1
        abs_minutes = abs(total_minutes)
        hours = abs_minutes // 60
        minutes = abs_minutes % 60
        return sign, hours, minutes

    def _compose_timezone(self, sign: int, hours: int, minutes: int) -> int:
        sign = 1 if sign >= 0 else -1
        hours = max(0, min(14, hours))
        minutes = max(0, min(59, minutes))
        if hours == 0 and minutes == 0:
            sign = 1
        return self._clamp_timezone_minutes(sign * (hours * 60 + minutes))
