from calendar import monthrange

from PySide6.QtGui import QValidator

from core.datetime_parsing.enums import DateTimeCategory
from core.datetime_parsing.regex import PARTIAL_DATETIME_RE, parse_datetime_text


class DateTimeValidator(QValidator):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.category = None

    def validate(self, input_str: str, pos: int):
        input_str = input_str.upper()

        if not input_str:
            return QValidator.State.Intermediate

        try:
            if parse_datetime_text(input_str, self.category) is not None:
                return QValidator.State.Acceptable
        except:
            pass

        try:
            if self.category == DateTimeCategory.Time and 0 <= int(input_str) <= 23:
                return QValidator.State.Intermediate
        except:
            pass

        match = PARTIAL_DATETIME_RE.fullmatch(input_str)
        if not match:
            return QValidator.State.Invalid

        parts = match.groupdict()

        match self.category:
            case DateTimeCategory.Date:
                only_allowed = {"year", "month", "day"}
            case DateTimeCategory.Time:
                only_allowed = {"hour", "minute", "second", "subsecond"}
            case DateTimeCategory.DateTime:
                only_allowed = {"year", "month", "day", "separator", "hour", "minute", "second", "subsecond"}
            case DateTimeCategory.DateTimeUTC:
                only_allowed = {
                    "year",
                    "month",
                    "day",
                    "separator",
                    "hour",
                    "minute",
                    "second",
                    "subsecond",
                    "utc",
                }
            case _:
                only_allowed = {
                    "year",
                    "month",
                    "day",
                    "separator",
                    "hour",
                    "minute",
                    "second",
                    "subsecond",
                    "tz_sign",
                    "tz_hour",
                    "tz_minute",
                }

        for key, value in parts.items():
            if value is not None and key not in only_allowed:
                return QValidator.State.Invalid

        # Check separator validity
        year = parts.get("year")
        month = parts.get("month")
        day = parts.get("day")

        separator = parts.get("separator")

        hour = parts.get("hour")
        minute = parts.get("minute")
        second = parts.get("second")

        subsecond = parts.get("subsecond")
        tz_sign = parts.get("tz_sign")
        tz_hour = parts.get("tz_hour")
        tz_minute = parts.get("tz_minute")

        if year and int(year) > 9999:
            return QValidator.State.Invalid
        if month and int(month) > 12:
            return QValidator.State.Invalid
        if day and int(day) > 31:
            return QValidator.State.Invalid

        if year and month and day and all(int(x) > 0 for x in (year, month, day)):
            _, month_days = monthrange(int(year), int(month))
            if int(day) >= month_days:
                return QValidator.State.Invalid

        if separator not in ("T", " ", "_", None):
            return QValidator.State.Invalid

        if hour and int(hour) > 23:
            return QValidator.State.Invalid
        if minute and int(minute) > 59:
            return QValidator.State.Invalid
        if second and int(second) > 59:
            return QValidator.State.Invalid
        if subsecond and int(subsecond) > 999999999:
            return QValidator.State.Invalid

        if tz_sign not in ("+", "-", None):
            return QValidator.State.Invalid

        if tz_hour and int(tz_hour) > 23:
            return QValidator.State.Invalid
        if tz_minute and int(tz_minute) > 59:
            return QValidator.State.Invalid

        return QValidator.State.Intermediate
