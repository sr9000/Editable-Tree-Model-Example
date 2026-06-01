from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any

from pandas import Timestamp

from core.datetime_parsing.nano_time import NanoTime
from tree.types import JsonType


def convert_datetime(value: Any, src: JsonType, dst: JsonType) -> Any:
    """Convert values across the date/time family.

    This is intentionally strict: caller should only use it for members of
    DATETIME_FAMILY.
    """
    if src is dst:
        return value

    if src not in {
        JsonType.DATE,
        JsonType.TIME,
        JsonType.DATETIME,
        JsonType.DATETIMEZONE,
        JsonType.DATETIMEUTC,
    }:
        raise ValueError(f"Unsupported datetime source type: {src}")

    if dst not in {
        JsonType.DATE,
        JsonType.TIME,
        JsonType.DATETIME,
        JsonType.DATETIMEZONE,
        JsonType.DATETIMEUTC,
    }:
        raise ValueError(f"Unsupported datetime target type: {dst}")

    if src is JsonType.DATE:
        if not isinstance(value, date) or isinstance(value, datetime):
            raise ValueError("DATE conversion expects datetime.date")
        base = datetime.combine(value, time(0, 0, 0))
        if dst is JsonType.DATE:
            return value
        if dst is JsonType.TIME:
            return NanoTime(hour=base.hour, minute=base.minute, second=base.second)
        if dst is JsonType.DATETIME:
            return Timestamp(base)
        if dst is JsonType.DATETIMEZONE:
            return Timestamp(base.replace(tzinfo=timezone.utc))
        return Timestamp(base.replace(tzinfo=timezone.utc))

    if src is JsonType.TIME:
        if not isinstance(value, NanoTime):
            raise ValueError("TIME conversion expects NanoTime")
        base = datetime.combine(date.today(), time(value.hour, value.minute, value.second, value.nanosecond // 1000))
        if dst is JsonType.DATE:
            return base.date()
        if dst is JsonType.TIME:
            return value
        if dst is JsonType.DATETIME:
            return Timestamp(base.replace(tzinfo=None))
        if dst is JsonType.DATETIMEZONE:
            return Timestamp(base.replace(tzinfo=timezone.utc))
        return Timestamp(base.replace(tzinfo=timezone.utc))

    if not isinstance(value, Timestamp):
        raise ValueError("DATETIME conversion expects pandas.Timestamp")

    if src is JsonType.DATETIME:
        naive = value.tz_localize(None) if value.tzinfo is not None else value
        if dst is JsonType.DATE:
            return naive.date()
        if dst is JsonType.TIME:
            return NanoTime(
                hour=naive.hour, minute=naive.minute, second=naive.second, nanosecond=naive.microsecond * 1000
            )
        if dst is JsonType.DATETIME:
            return naive
        if dst in {JsonType.DATETIMEZONE, JsonType.DATETIMEUTC}:
            return naive.tz_localize("UTC")

    if src is JsonType.DATETIMEZONE:
        aware = value if value.tzinfo is not None else value.tz_localize("UTC")
        if dst is JsonType.DATE:
            return aware.date()
        if dst is JsonType.TIME:
            return NanoTime(
                hour=aware.hour, minute=aware.minute, second=aware.second, nanosecond=aware.microsecond * 1000
            )
        if dst is JsonType.DATETIME:
            return aware.tz_localize(None)
        if dst is JsonType.DATETIMEZONE:
            return aware
        if dst is JsonType.DATETIMEUTC:
            return aware.tz_convert("UTC")

    if src is JsonType.DATETIMEUTC:
        aware = (value if value.tzinfo is not None else value.tz_localize("UTC")).tz_convert("UTC")
        if dst is JsonType.DATE:
            return aware.date()
        if dst is JsonType.TIME:
            return NanoTime(
                hour=aware.hour, minute=aware.minute, second=aware.second, nanosecond=aware.microsecond * 1000
            )
        if dst is JsonType.DATETIME:
            return aware.tz_localize(None)
        if dst is JsonType.DATETIMEZONE:
            return aware
        if dst is JsonType.DATETIMEUTC:
            return aware

    raise ValueError(f"Unsupported datetime conversion: {src} -> {dst}")
