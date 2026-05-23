from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any

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
            return base.time()
        if dst is JsonType.DATETIME:
            return base
        if dst is JsonType.DATETIMEZONE:
            return base.replace(tzinfo=timezone.utc)
        return base.replace(tzinfo=timezone.utc)

    if src is JsonType.TIME:
        if not isinstance(value, time):
            raise ValueError("TIME conversion expects datetime.time")
        base = datetime.combine(date.today(), value)
        if dst is JsonType.DATE:
            return base.date()
        if dst is JsonType.TIME:
            return value
        if dst is JsonType.DATETIME:
            return base.replace(tzinfo=None)
        if dst is JsonType.DATETIMEZONE:
            return base.replace(tzinfo=timezone.utc)
        return base.replace(tzinfo=timezone.utc)

    if not isinstance(value, datetime):
        raise ValueError("DATETIME conversion expects datetime.datetime")

    if src is JsonType.DATETIME:
        naive = value.replace(tzinfo=None)
        if dst is JsonType.DATE:
            return naive.date()
        if dst is JsonType.TIME:
            return naive.time()
        if dst is JsonType.DATETIME:
            return naive
        if dst in {JsonType.DATETIMEZONE, JsonType.DATETIMEUTC}:
            return naive.replace(tzinfo=timezone.utc)

    if src is JsonType.DATETIMEZONE:
        aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        if dst is JsonType.DATE:
            return aware.date()
        if dst is JsonType.TIME:
            return aware.time()
        if dst is JsonType.DATETIME:
            return aware.replace(tzinfo=None)
        if dst is JsonType.DATETIMEZONE:
            return aware
        if dst is JsonType.DATETIMEUTC:
            return aware.astimezone(timezone.utc)

    if src is JsonType.DATETIMEUTC:
        aware = (value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
        if dst is JsonType.DATE:
            return aware.date()
        if dst is JsonType.TIME:
            return aware.time()
        if dst is JsonType.DATETIME:
            return aware.replace(tzinfo=None)
        if dst is JsonType.DATETIMEZONE:
            return aware
        if dst is JsonType.DATETIMEUTC:
            return aware

    raise ValueError(f"Unsupported datetime conversion: {src} -> {dst}")
