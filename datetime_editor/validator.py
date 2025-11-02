from PySide6.QtGui import QValidator

from .regex import DATETIME_RE, PARTIAL_DATETIME_RE


class DateTimeValidator(QValidator):
    def validate(self, input_str: str, pos: int):
        input_str = input_str.strip().upper()

        if not input_str:
            return QValidator.State.Intermediate

        if DATETIME_RE.fullmatch(input_str):
            try:
                # Final check with datetime to catch invalid dates like Feb 30.
                # This is a bit of a cheat, but effective.
                from .regex import parse_datetime_text

                if parse_datetime_text(input_str) is None:
                    return QValidator.State.Invalid

                # Additional check: if there's a separator in the match, ensure there's an hour
                match = DATETIME_RE.fullmatch(input_str)
                parts = match.groupdict()
                separator = parts.get("separator")
                hour = parts.get("hour")

                # If there's a separator but no hour, it's intermediate (still typing)
                if separator and not hour:
                    return QValidator.State.Intermediate

                return QValidator.State.Acceptable
            except ValueError:
                return QValidator.State.Invalid

        match = PARTIAL_DATETIME_RE.fullmatch(input_str)
        if not match:
            return QValidator.State.Invalid

        parts = match.groupdict()

        # Check separator validity
        year = parts.get("year")
        month = parts.get("month")
        day = parts.get("day")
        separator = parts.get("separator")
        hour = parts.get("hour")

        # Separator should only appear if there's a date part before it
        if separator:
            # Separator must be one of the valid characters
            if separator not in ("T", " ", "_"):
                return QValidator.State.Invalid
            # If there's a separator but not a complete date yet, it's still intermediate
            if not (year and month and day and len(month) == 2 and len(day) == 2):
                return QValidator.State.Intermediate
            # If complete date and separator present but hour is missing, consider intermediate (still typing)
            if not hour:
                return QValidator.State.Intermediate

        if month and len(month) == 2 and int(month) > 12:
            return QValidator.State.Invalid
        if day and len(day) == 2 and int(day) > 31:
            return QValidator.State.Invalid

        if hour:
            if int(hour) > 23:
                return QValidator.State.Invalid
        elif separator and year and month and day:
            # This covers cases like '2025-11-02T:34:56' where hour is missing after separator
            return QValidator.State.Intermediate

        minute = parts.get("minute")
        if minute and len(minute) == 2 and int(minute) > 59:
            return QValidator.State.Invalid

        second = parts.get("second")
        if second and len(second) == 2 and int(second) > 59:
            return QValidator.State.Invalid

        # Check if we have a complete enough datetime to be acceptable
        # A complete date (year-month-day) is acceptable
        # A complete time (hour:minute:second) is acceptable
        # A datetime with date + separator + hour:minute is also acceptable
        # BUT: if input ends with : or . then it's intermediate (still typing)

        ends_with_separator = input_str.endswith(":") or input_str.endswith(".")

        has_complete_date = year and month and len(month) == 2 and day and len(day) == 2
        has_complete_time = hour and minute and len(minute) == 2 and second and len(second) == 2
        has_datetime_with_minute = (
            has_complete_date
            and separator
            and hour
            and len(hour) == 2
            and minute
            and len(minute) == 2
            and not second  # no second specified yet
        )
        has_time_with_minute = (
            hour
            and len(hour) == 2
            and minute
            and len(minute) == 2
            and not year  # no date part
            and not second  # no second specified yet
            and not separator  # no separator either
        )

        if ends_with_separator:
            # Still typing, not acceptable yet
            return QValidator.State.Intermediate
        elif has_complete_date and not separator and not hour:
            # Just a date like 2025-11-02
            return QValidator.State.Acceptable
        elif has_complete_time and not year:
            # Just a time like 12:34:56
            return QValidator.State.Acceptable
        elif has_datetime_with_minute or has_time_with_minute:
            # DateTime with just hour:minute like 2025-11-02T12:34 or time like 12:34
            return QValidator.State.Acceptable

        return QValidator.State.Intermediate
