from PySide6.QtGui import QValidator

from .regex import DATETIME_RE, PARTIAL_DATETIME_RE


class DateTimeValidator(QValidator):
    def validate(self, input_str: str, pos: int):
        if not input_str:
            return QValidator.State.Intermediate

        if DATETIME_RE.fullmatch(input_str):
            try:
                # Final check with datetime to catch invalid dates like Feb 30.
                # This is a bit of a cheat, but effective.
                from .regex import parse_datetime_text

                if parse_datetime_text(input_str) is None:
                    return QValidator.State.Invalid
                return QValidator.State.Acceptable
            except ValueError:
                return QValidator.State.Invalid

        match = PARTIAL_DATETIME_RE.fullmatch(input_str)
        if not match:
            return QValidator.State.Invalid

        parts = match.groupdict()
        month = parts.get("month")
        if month and int(month) > 12:
            return QValidator.State.Invalid

        day = parts.get("day")
        if day and int(day) > 31:
            return QValidator.State.Invalid

        hour = parts.get("hour")
        if hour and int(hour) > 23:
            return QValidator.State.Invalid
        elif hour and len(hour) == 2 and parts.get("minute") is None:
            # if we are entering time, we might have "2" then "25"
            if int(hour) > 23:
                return QValidator.State.Invalid

        minute = parts.get("minute")
        if minute and int(minute) > 59:
            return QValidator.State.Invalid

        second = parts.get("second")
        if second and int(second) > 59:
            return QValidator.State.Invalid

        return QValidator.State.Intermediate
