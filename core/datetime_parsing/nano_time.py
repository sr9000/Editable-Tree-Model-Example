"""NanoTime — time-of-day with nanosecond precision.

Replaces ``datetime.time`` for the TIME category, gaining 9-digit
fractional-second precision instead of the 6-digit (microsecond) limit
of the stdlib type.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2})(?:\.(\d{1,9}))?)?$")


@dataclass(frozen=True)
class NanoTime:
    """Time-of-day with nanosecond precision (replaces ``datetime.time`` for the TIME category)."""

    hour: int = 0
    minute: int = 0
    second: int = 0
    nanosecond: int = 0  # 0–999_999_999

    def __post_init__(self) -> None:
        if not (0 <= self.hour <= 23):
            raise ValueError(f"hour must be in 0..23, got {self.hour}")
        if not (0 <= self.minute <= 59):
            raise ValueError(f"minute must be in 0..59, got {self.minute}")
        if not (0 <= self.second <= 59):
            raise ValueError(f"second must be in 0..59, got {self.second}")
        if not (0 <= self.nanosecond <= 999_999_999):
            raise ValueError(f"nanosecond must be in 0..999_999_999, got {self.nanosecond}")

    def isoformat(self, timespec: str = "auto") -> str:
        """Return an ISO 8601 time string.

        *timespec* values mirror ``datetime.time.isoformat()``:
        ``"auto"``, ``"hours"``, ``"minutes"``, ``"seconds"``,
        ``"milliseconds"``, ``"microseconds"``, ``"nanoseconds"``.
        """
        base = f"{self.hour:02d}:{self.minute:02d}"
        if timespec == "hours":
            return base
        base = f"{base}:{self.second:02d}"
        if timespec == "minutes":
            return f"{self.hour:02d}:{self.minute:02d}"
        if timespec == "seconds":
            return base
        if timespec == "milliseconds":
            ms = self.nanosecond // 1_000_000
            return f"{base}.{ms:03d}"
        if timespec == "microseconds":
            us = self.nanosecond // 1_000
            return f"{base}.{us:06d}"
        if timespec == "nanoseconds":
            return f"{base}.{self.nanosecond:09d}"
        # "auto" — emit only the digits needed
        if self.nanosecond:
            # Strip trailing zeros but keep at least one digit
            ns_str = f"{self.nanosecond:09d}".rstrip("0")
            return f"{base}.{ns_str}"
        return base

    @classmethod
    def fromisoformat(cls, text: str) -> NanoTime:
        """Parse an ISO 8601 time string (``hh:mm[:ss[.nnnnnnnnn]]``)."""
        m = _TIME_RE.fullmatch(text.strip())
        if m is None:
            raise ValueError(f"Invalid ISO time string: {text!r}")
        hour = int(m.group(1))
        minute = int(m.group(2))
        second = int(m.group(3)) if m.group(3) is not None else 0
        frac = m.group(4)
        if frac is not None:
            # Pad to 9 digits to convert fractional seconds → nanoseconds
            ns = int(frac.ljust(9, "0")[:9])
        else:
            ns = 0
        return cls(hour=hour, minute=minute, second=second, nanosecond=ns)

    def replace(self, **kwargs) -> NanoTime:
        """Return a new NanoTime with specified fields replaced."""
        return NanoTime(
            hour=kwargs.get("hour", self.hour),
            minute=kwargs.get("minute", self.minute),
            second=kwargs.get("second", self.second),
            nanosecond=kwargs.get("nanosecond", self.nanosecond),
        )

    def __str__(self) -> str:
        return self.isoformat()

    def __repr__(self) -> str:
        return f"NanoTime({self.hour}, {self.minute}, {self.second}, {self.nanosecond})"
