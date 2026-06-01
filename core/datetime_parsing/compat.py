"""Thin adapter layer for datetime type construction.

Centralizes ``pandas.Timestamp`` / ``NanoTime`` / ``datetime.date``
construction so callers don't import pandas directly.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any, Union

import pandas as pd

from core.datetime_parsing.nano_time import NanoTime

TemporalValue = Union[date, NanoTime, pd.Timestamp]


def to_timestamp(value: Any) -> Any:
    """Construct a ``pandas.Timestamp`` from *value*.

    Accepts ISO strings, ``datetime.datetime``, or existing
    ``pandas.Timestamp`` objects.
    """
    if isinstance(value, pd.Timestamp):
        return value
    if isinstance(value, datetime):
        return pd.Timestamp(value)
    if isinstance(value, str):
        return pd.Timestamp(value.replace("_", " "))
    raise TypeError(f"Cannot convert {type(value).__name__} to Timestamp")


def to_nanotime(value: Any) -> NanoTime:
    """Construct a ``NanoTime`` from *value*.

    Accepts ISO strings, ``datetime.time``, or existing ``NanoTime``.
    """
    if isinstance(value, NanoTime):
        return value
    if isinstance(value, time):
        return NanoTime(
            hour=value.hour,
            minute=value.minute,
            second=value.second,
            nanosecond=value.microsecond * 1000,
        )
    if isinstance(value, str):
        return NanoTime.fromisoformat(value)
    raise TypeError(f"Cannot convert {type(value).__name__} to NanoTime")


def to_date(value: Any) -> date:
    """Construct a ``datetime.date`` from *value*."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"Cannot convert {type(value).__name__} to date")


def isoformat(value: Any, category: Any = None) -> str:
    """Format *value* as an ISO string, dispatching by runtime type."""
    if isinstance(value, pd.Timestamp):
        if category is not None and category.name == "DateTimeUTC":
            return (
                value.tz_localize(None).isoformat()
                if value.tz is None
                else value.tz_convert("UTC").isoformat().replace("+00:00", "Z")
            )
        return value.isoformat()
    if isinstance(value, NanoTime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)
