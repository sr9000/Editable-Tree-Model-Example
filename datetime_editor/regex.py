from datetime import date, time, datetime, timezone, timedelta
import re

from .enums import DateTimeCategory

DATETIME_RE = re.compile(
    r"^(?:(?:(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2}))(?:[T _])?)?"
    r"(?:(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})(?:\.(?P<microsecond>\d+))?)?"
    r"(?:(?:(?P<tz_sign>[+-])(?P<tz_hour>\d{2}):(?P<tz_minute>\d{2}))|(?P<utc>[Zz]))?$"
)

# In the partial regex:
# - Year (1-4 digits) only matches if followed by '-' or end-of-string to avoid
#   consuming the hour in inputs like '25:00'.
# - If the time block is present, hour must have at least one digit to prevent
#   matching inputs like ':34' or interpreting '25:00' with an empty hour.
PARTIAL_DATETIME_RE = re.compile(
    r"^(?:(?P<year>\d{1,4})(?=(?:-|$))(?:-(?P<month>\d{0,2})(?:-(?P<day>\d{0,2}))?)?)?"
    r"(?:[T _]?(?P<hour>\d{1,2})(?::(?P<minute>\d{0,2})(?::(?P<second>\d{0,2})(?:\.(?P<microsecond>\d*))?)?)?)?"
    r"(?:(?:(?P<tz_sign>[+-])(?P<tz_hour>\d{0,2})(?::(?P<tz_minute>\d{0,2}))?)|(?P<utc>[Zz]?))?$"
)


def parse_datetime_text(text, category=None):
    match = DATETIME_RE.match(text)
    if not match:
        return None

    parts = match.groupdict()
    year = int(parts["year"]) if parts["year"] else None
    month = int(parts["month"]) if parts["month"] else None
    day = int(parts["day"]) if parts["day"] else None
    hour = int(parts["hour"]) if parts["hour"] else None
    minute = int(parts["minute"]) if parts["minute"] else None
    second = int(parts["second"]) if parts["second"] else None
    microsecond = int(parts["microsecond"].ljust(6, "0")[:6]) if parts["microsecond"] else 0

    tz_sign = parts["tz_sign"]
    tz_hour = int(parts["tz_hour"]) if parts["tz_hour"] else 0
    tz_minute = int(parts["tz_minute"]) if parts["tz_minute"] else 0
    utc = parts["utc"]

    tz = None
    if utc:
        tz = timezone.utc
    elif tz_sign:
        offset = timedelta(hours=tz_hour, minutes=tz_minute)
        if tz_sign == "-":
            offset = -offset
        tz = timezone(offset)

    if category == DateTimeCategory.Date:
        return date(year, month, day)
    elif category == DateTimeCategory.Time:
        return time(hour, minute, second, microsecond, tzinfo=tz)
    elif category == DateTimeCategory.DateTime:
        return datetime(year, month, day, hour, minute, second, microsecond)
    elif category == DateTimeCategory.DateTimeWithTZ:
        return datetime(year, month, day, hour, minute, second, microsecond, tzinfo=tz)

    if year is not None and hour is not None:
        return datetime(year, month, day, hour, minute, second, microsecond, tzinfo=tz)
    elif year is not None:
        return date(year, month, day)
    elif hour is not None:
        return time(hour, minute, second, microsecond, tzinfo=tz)
    return None
