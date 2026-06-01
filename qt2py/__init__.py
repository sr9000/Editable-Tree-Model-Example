from datetime import datetime
from zoneinfo import ZoneInfo

from pandas import Timestamp
from PySide6.QtCore import QDateTime, QTimeZone

from app.runtime_compat import tz_name


def qtdatetime(dt: Timestamp | datetime):
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("tz-aware datetime required for `qtdatetime()`")

    tzid = tz_name(dt)
    tz = QTimeZone(tzid.encode()) if tzid else QTimeZone(int(dt.utcoffset().total_seconds()))

    return QDateTime.fromMSecsSinceEpoch(round(dt.timestamp() * 1000), tz)


def pydatetime(qdt: QDateTime) -> Timestamp:
    dt: datetime = qdt.toPython()  # may be offset-aware but not named
    tzid = bytes(qdt.timeZone().id().data()).decode() if qdt.timeZone().isValid() else None

    if tzid:
        try:
            return Timestamp(dt.astimezone(ZoneInfo(tzid)))  # same instant, with named tz
        except Exception:
            pass

    return Timestamp(dt)  # fallback (fixed offset)
