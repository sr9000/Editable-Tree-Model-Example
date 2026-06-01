from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Union

from pandas import Timedelta, Timestamp
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFocusEvent, QKeyEvent, QValidator
from PySide6.QtWidgets import QLineEdit

from core.datetime_parsing.enums import DateTimeCategory
from core.datetime_parsing.nano_time import NanoTime
from core.datetime_parsing.regex import PARTIAL_DATETIME_RE, parse_datetime_text

from .validator import DateTimeValidator

ValueType = Union[date, NanoTime, Timestamp, None]


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


class BetterDateTimeBuffer:
    def __init__(self):
        self._category: Optional[DateTimeCategory] = None
        self._value: ValueType = None
        self._text: str = ""
        self._last_valid_text: str = ""
        self._segments: list[_Segment] = []

    # ------------------------------------------------------------------
    # Basic state management
    @property
    def category(self) -> Optional[DateTimeCategory]:
        return self._category

    @property
    def value(self) -> ValueType:
        return self._value

    @property
    def last_valid_text(self) -> str:
        return self._last_valid_text

    def set_value(self, value: ValueType) -> tuple[str, Optional[DateTimeCategory]]:
        text, category = self._format_value(value)
        self._category = category
        self._value = value
        self._text = text
        self._last_valid_text = text
        self._segments = self._extract_segments(text)
        return text, category

    def set_category(self, category: Optional[DateTimeCategory], text: str) -> None:
        self._category = category
        self._sync_text(text)

    def accept_text(self, text: str) -> Optional[ValueType]:
        self._text = text
        self._segments = self._extract_segments(text)
        parsed = parse_datetime_text(text, self._category)
        if parsed is not None:
            self._value = parsed
            self._last_valid_text = text
            return parsed
        return None

    def intermediate_text(self, text: str) -> None:
        self._text = text
        self._segments = self._extract_segments(text)

    def revert_text(self) -> str:
        self._text = self._last_valid_text
        self._segments = self._extract_segments(self._text)
        return self._text

    def step(self, delta: int, cursor_pos: int) -> Optional[tuple[str, int]]:
        if not self._segments or self._value is None or delta == 0:
            return None
        segment = self._segment_at_cursor(cursor_pos)
        if segment is None:
            segment = self._segments[-1]
        return self._apply_delta_to_segment(segment, delta)

    def _sync_text(self, text: str) -> None:
        self._text = text
        self._segments = self._extract_segments(text)
        parsed = parse_datetime_text(text, self._category)
        if parsed is not None:
            self._value = parsed

    # ------------------------------------------------------------------
    # Segment helpers
    def _segment_at_cursor(self, cursor: int) -> Optional[_Segment]:
        for seg in self._segments:
            if seg.start <= cursor <= seg.end:
                return seg
        return None

    def _segment_by_name(self, name: str) -> Optional[_Segment]:
        for seg in self._segments:
            if seg.name == name:
                return seg
        return None

    def _apply_delta_to_segment(self, segment: _Segment, delta: int) -> Optional[tuple[str, int]]:
        value = self._value
        if value is None:
            return None
        dt_value = self._as_datetime(value)

        if segment.name == "year":
            new_year = max(1, min(9999, dt_value.year + delta))
            max_day = monthrange(new_year, dt_value.month)[1]
            dt_value = dt_value.replace(year=new_year, day=min(dt_value.day, max_day))
        elif segment.name == "month":
            if abs(delta) > 3:
                delta = 3 * (delta // abs(delta))
            new_month = ((dt_value.month - 1) + delta) % 12 + 1
            max_day = monthrange(dt_value.year, new_month)[1]
            dt_value = dt_value.replace(month=new_month, day=min(dt_value.day, max_day))
        elif segment.name == "day":
            days_in_month = monthrange(dt_value.year, dt_value.month)[1]
            day = 1 + (dt_value.day - 1 + delta) % days_in_month
            dt_value = dt_value.replace(day=day)
        elif segment.name == "hour":
            dt_value = dt_value.replace(hour=(dt_value.hour + delta) % 24)
        elif segment.name == "minute":
            dt_value = dt_value.replace(minute=(dt_value.minute + delta) % 60)
        elif segment.name == "second":
            dt_value = dt_value.replace(second=(dt_value.second + delta) % 60)
        elif segment.name == "subsecond":
            dt_value = self._apply_subsecond_delta(dt_value, segment, delta)
        elif segment.name in {"tz_sign", "tz_hour", "tz_minute", "utc"}:
            if self._category is DateTimeCategory.DateTimeUTC:
                return None
            dt_value = self._ensure_timezone(dt_value)
            total_minutes = self._timezone_minutes(dt_value)
            total_minutes = self._adjust_timezone_minutes(segment.name, total_minutes, delta)
            new_tz = timezone(timedelta(minutes=total_minutes))
            dt_value = dt_value.tz_localize(None).tz_localize(new_tz)
            return self._rebuild_timezone_segments(dt_value, segment)
        else:
            return None

        text = self._text
        if segment.name in {"month", "year"}:
            day_segment = self._segment_by_name("day")
            if day_segment:
                replacement = self._format_segment_value("day", dt_value, day_segment.length)
                if replacement:
                    text = text[: day_segment.start] + replacement + text[day_segment.end :]

        replacement = self._format_segment_value(segment.name, dt_value, segment.length)
        if replacement is None:
            return None

        new_text = text[: segment.start] + replacement + text[segment.end :]
        self._value = self._restore_type(dt_value, self._category)
        self._text = new_text
        self._segments = self._extract_segments(new_text)
        return new_text, segment.start + len(replacement)

    def _rebuild_timezone_segments(self, value: Timestamp, anchor: _Segment) -> Optional[tuple[str, int]]:
        tz_segments = [seg for seg in self._segments if seg.name in {"tz_sign", "tz_hour", "tz_minute", "utc"}]
        if not tz_segments:
            return None

        new_text = self._text
        cursor = None
        for seg in sorted(tz_segments, key=lambda s: s.start, reverse=True):
            replacement = self._format_segment_value(seg.name, value, seg.length)
            if replacement is None:
                continue
            new_text = new_text[: seg.start] + replacement + new_text[seg.end :]
            if seg is anchor:
                cursor = seg.start + len(replacement)

        self._value = self._restore_type(value, self._category)
        self._text = new_text
        self._segments = self._extract_segments(new_text)
        if cursor is None:
            cursor = anchor.start
        return new_text, cursor

    # ------------------------------------------------------------------
    # Static helpers
    @staticmethod
    def _format_value(value: ValueType) -> tuple[str, Optional[DateTimeCategory]]:
        if value is None:
            return "", None
        if isinstance(value, Timestamp):
            if value.tzinfo is not None:
                if value.tzinfo == timezone.utc:
                    return (
                        value.tz_convert("UTC").isoformat().replace("+00:00", "Z"),
                        DateTimeCategory.DateTimeUTC,
                    )
                return value.isoformat(), DateTimeCategory.DateTimeWithTZ
            return value.isoformat(sep=" "), DateTimeCategory.DateTime
        if isinstance(value, date):
            return value.isoformat(), DateTimeCategory.Date
        if isinstance(value, NanoTime):
            return value.isoformat(), DateTimeCategory.Time
        raise TypeError("Unsupported value type")

    @staticmethod
    def _as_datetime(value: ValueType) -> Timestamp:
        if isinstance(value, Timestamp):
            return value
        if isinstance(value, date):
            return Timestamp(value)
        if isinstance(value, NanoTime):
            return Timestamp(
                datetime.combine(
                    date.today(), datetime.time(value.hour, value.minute, value.second, value.nanosecond // 1000)
                )
            )
        raise TypeError("Unsupported value type")

    @staticmethod
    def _restore_type(value: Timestamp, category: Optional[DateTimeCategory]) -> ValueType:
        match category:
            case DateTimeCategory.Date:
                return value.date()
            case DateTimeCategory.Time:
                return NanoTime(
                    hour=value.hour, minute=value.minute, second=value.second, nanosecond=value.microsecond * 1000
                )
            case DateTimeCategory.DateTime:
                return value.tz_localize(None) if value.tzinfo is not None else value
            case DateTimeCategory.DateTimeWithTZ:
                return value if value.tzinfo is not None else value.tz_localize("UTC")
            case DateTimeCategory.DateTimeUTC:
                return value.tz_localize("UTC") if value.tzinfo is None else value.tz_convert("UTC")
            case _:
                return value

    @staticmethod
    def _extract_segments(text: str) -> list[_Segment]:
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

    @staticmethod
    def _apply_subsecond_delta(value: Timestamp, segment: _Segment, delta: int) -> Timestamp:
        digits = max(1, min(segment.length, 9))
        step = 10 ** (9 - digits)
        return value + Timedelta(delta * step)

    @staticmethod
    def _format_subsecond(nanosecond: int, width: int) -> str:
        digits = max(1, min(width or 9, 9))
        full = f"{nanosecond:09d}"
        return full[:digits] if digits < 9 else full

    @staticmethod
    def _ensure_timezone(value: Timestamp) -> Timestamp:
        if value.tzinfo is not None:
            return value
        return value.tz_localize("UTC")

    @staticmethod
    def _timezone_minutes(value: Timestamp) -> int:
        offset = value.tzinfo.utcoffset(value) or timedelta()
        return int(offset.total_seconds() // 60)

    @staticmethod
    def _clamp_timezone_minutes(minutes: int) -> int:
        limit = 14 * 60 + 59
        return max(-limit, min(limit, minutes))

    @staticmethod
    def _split_timezone(total_minutes: int) -> tuple[int, int, int]:
        sign = 1 if total_minutes >= 0 else -1
        abs_minutes = abs(total_minutes)
        hours = abs_minutes // 60
        minutes = abs_minutes % 60
        return sign, hours, minutes

    @staticmethod
    def _compose_timezone(sign: int, hours: int, minutes: int) -> int:
        sign = 1 if sign >= 0 else -1
        hours = max(0, min(14, hours))
        minutes = max(0, min(59, minutes))
        if hours == 0 and minutes == 0:
            sign = 1
        return BetterDateTimeBuffer._clamp_timezone_minutes(sign * (hours * 60 + minutes))

    @staticmethod
    def _adjust_timezone_minutes(part: str, total_minutes: int, delta: int) -> int:
        if delta == 0:
            return total_minutes

        sign, hours, minutes = BetterDateTimeBuffer._split_timezone(total_minutes)
        step = 1 - 2 * (delta < 0)

        if part == "tz_sign":
            sign = step
        elif part == "tz_hour" and delta != 0:
            for _ in range(abs(delta)):
                if sign * step > 0:
                    hours += 1
                elif hours:
                    hours -= 1
                else:
                    sign *= -1
                    hours = 1 if sign < 0 and minutes == 0 else hours
        elif part == "tz_minute" and delta != 0:
            minutes = (minutes + delta) % 60
        elif part == "utc" and delta != 0:
            sign = step
            hours, minutes = abs(delta), 0

        return BetterDateTimeBuffer._compose_timezone(sign, hours, minutes)

    @staticmethod
    def _format_timezone_string(minutes: int) -> str:
        sign = "+" if minutes >= 0 else "-"
        minutes = abs(minutes)
        hours = minutes // 60
        minute_part = minutes % 60
        return f"{sign}{hours:02d}:{minute_part:02d}"

    @staticmethod
    def _format_segment_value(name: str, value: Timestamp, width: int) -> Optional[str]:
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
            case "subsecond":
                nanosecond = value.microsecond * 1000 + value.nanosecond
                text = BetterDateTimeBuffer._format_subsecond(nanosecond, width)
            case "tz_sign":
                minutes = BetterDateTimeBuffer._timezone_minutes(BetterDateTimeBuffer._ensure_timezone(value))
                text = "+" if minutes >= 0 else "-"
            case "tz_hour":
                minutes = abs(BetterDateTimeBuffer._timezone_minutes(BetterDateTimeBuffer._ensure_timezone(value)))
                hours = minutes // 60
                width = width or 2
                text = str(hours).zfill(width)
            case "tz_minute":
                minutes = abs(BetterDateTimeBuffer._timezone_minutes(BetterDateTimeBuffer._ensure_timezone(value))) % 60
                width = width or 2
                text = str(minutes).zfill(width)
            case "utc":
                total = BetterDateTimeBuffer._timezone_minutes(BetterDateTimeBuffer._ensure_timezone(value))
                text = "Z" if total == 0 else BetterDateTimeBuffer._format_timezone_string(total)
            case _:
                return None
        if name not in {"tz_sign", "tz_hour", "tz_minute", "utc"} and width > 0 and len(text) < width:
            text = text.zfill(width)
        return text


class BetterDateTimeEditor(QLineEdit):
    """Qt widget wrapper around BetterDateTimeBuffer."""

    valueChanged = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._validator = DateTimeValidator(self)
        self.setValidator(self._validator)
        self._buffer = BetterDateTimeBuffer()
        self.textChanged.connect(self._handle_text_changed)

    # ------------------------------------------------------------------
    # Public API
    def category(self) -> Optional[DateTimeCategory]:
        return self._buffer.category

    def setCategory(self, category: Optional[DateTimeCategory]) -> None:
        self._buffer.set_category(category, self.text())
        self._validator.category = category

    def value(self) -> ValueType:
        return self._buffer.value

    def setValue(self, value: ValueType) -> None:
        text, category = self._buffer.set_value(value)
        self._validator.category = category
        self._set_text_safely(text)

    # ------------------------------------------------------------------
    # Text/validation handling
    def _handle_text_changed(self, text: str) -> None:
        state = self._validation_state(text, self.cursorPosition())
        if state == QValidator.State.Acceptable:
            parsed = self._buffer.accept_text(text)
            if parsed is not None:
                self.valueChanged.emit(parsed)
        elif state == QValidator.State.Intermediate:
            self._buffer.intermediate_text(text)
        else:
            restored = self._buffer.revert_text()
            self._set_text_safely(restored)
            self.setCursorPosition(len(restored))

    def _set_text_safely(self, text: str) -> None:
        self.blockSignals(True)
        self.setText(text)
        self.blockSignals(False)

    def _validation_state(self, text: str, pos: int) -> QValidator.State:
        validator = self.validator()
        if validator is None:
            return QValidator.State.Acceptable
        result = validator.validate(text, pos)
        if isinstance(result, tuple):
            return result[0]
        return result

    # ------------------------------------------------------------------
    # Increment/decrement behavior
    def stepUp(self):
        self._apply_step(+1)

    def stepDown(self):
        self._apply_step(-1)

    def _apply_step(self, delta: int, repeat: int = 1) -> None:
        for _ in range(max(1, repeat)):
            result = self._buffer.step(delta, self.cursorPosition())
            if not result:
                break
            text, cursor = result
            self.setText(text)
            self.setCursorPosition(min(cursor, len(text)))

    # ------------------------------------------------------------------
    # Event handling
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Up:
            self.stepUp()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Down:
            self.stepDown()
            event.accept()
            return
        if event.key() == Qt.Key.Key_PageUp:
            self._apply_step(+10)
            event.accept()
            return
        if event.key() == Qt.Key.Key_PageDown:
            self._apply_step(-10)
            event.accept()
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event) -> None:
        if not self.isReadOnly() and self._buffer.value is not None:
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
            restored = self._buffer.revert_text()
            self._set_text_safely(restored)
        super().focusOutEvent(event)
