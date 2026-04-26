from datetime import datetime
from zoneinfo import ZoneInfo

from PySide6.QtCore import QDateTime, QTimeZone


def qtdatetime(dt: datetime):
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("tz-aware datetime required for `qtdatetime()`")

    tzid = getattr(dt.tzinfo, "key", None) or getattr(dt.tzinfo, "zone", None)
    tz = QTimeZone(tzid.encode()) if tzid else QTimeZone(int(dt.utcoffset().total_seconds()))

    return QDateTime.fromMSecsSinceEpoch(round(dt.timestamp() * 1000), tz)


def pydatetime(qdt: QDateTime) -> datetime:
    dt: datetime = qdt.toPython()  # may be offset-aware but not named
    tzid = bytes(qdt.timeZone().id().data()).decode() if qdt.timeZone().isValid() else None

    if tzid:
        try:
            return dt.astimezone(ZoneInfo(tzid))  # same instant, with named tz
        except Exception:
            pass

    return dt  # fallback (fixed offset)
