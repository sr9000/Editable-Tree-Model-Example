import re
from datetime import date, time, timezone

from dateutil.parser import isoparse

from .enums import DateTimeCategory

DATETIME_RE = re.compile(
    r"^("
    r"\d{4}-\d{2}-\d{2}"  # Date: YYYY-MM-DD
    r"|\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?"  # Time: hh:mm[:ss[.123456]]
    r"|"  # DateTime:
    r"\d{4}-\d{2}-\d{2}[T _]"  #  YYYY-MM-DD(T _)
    r"\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?"  # hh:mm[:ss[.123456]]
    r"(Z|[+-]\d{2}:\d{2})?"  # [Z|(+-)hh:mm]
    ")$",
    re.IGNORECASE,
)

SEPARATOR_RE = re.compile(r"[T _]", re.IGNORECASE)

# In the partial regex:
# - Year (1-4 digits) only matches if followed by '-', separator, or end-of-string to avoid
#   consuming the hour in inputs like '25:00'.
# - If the time block is present, hour must have at least one digit to prevent
#   matching inputs like ':34' or interpreting '25:00' with an empty hour.
PARTIAL_DATETIME_RE = re.compile(
    r"^(?:(?P<year>\d{0,4})(?=-|[T _]|$)(?:-(?P<month>\d{0,2})(?:-(?P<day>\d{0,2}))?)?)?"
    r"(?:(?P<separator>[T _])?(?P<hour>\d{1,2})?(?::(?P<minute>\d{0,2})(?::(?P<second>\d{0,2}))?)?(?:\.(?P<microsecond>\d*))?)?"
    r"(?:(?P<tz_sign>[+-])(?P<tz_hour>\d{0,2})(?::(?P<tz_minute>\d{0,2}))?|(?P<utc>Z))?$",
    re.IGNORECASE,
)


def parse_datetime_text(text: str, category=None):
    match = DATETIME_RE.fullmatch(text)
    if not match:
        return None

    try:
        match category:
            case DateTimeCategory.Date:
                return date.fromisoformat(text)

            case DateTimeCategory.Time:
                return time.fromisoformat(text)

            case DateTimeCategory.DateTime:
                assert SEPARATOR_RE.search(text)

                dt = isoparse(text)
                assert dt.tzinfo is None

                return dt

            case DateTimeCategory.DateTimeWithTZ:
                assert SEPARATOR_RE.search(text)
                assert not text.upper().endswith("Z")

                dt = isoparse(text)
                assert dt.tzinfo is not None

                return dt

            case DateTimeCategory.DateTimeUTC:
                assert SEPARATOR_RE.search(text)
                assert text.upper().endswith("Z")

                dt = isoparse(text)
                assert dt.tzinfo is not None

                return dt.astimezone(timezone.utc)

            case _ if category is not None:
                return None
    except:
        return None

    try:
        return time.fromisoformat(text)
    except:
        pass

    try:
        return date.fromisoformat(text)
    except:
        pass

    try:
        return isoparse(text)
    except:
        return None
