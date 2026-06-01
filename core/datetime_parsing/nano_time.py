"""NanoTime — time-of-day with nanosecond precision.

Replaces ``datetime.time`` for the TIME category, gaining 9-digit
fractional-second precision instead of the 6-digit (microsecond) limit
of the stdlib type.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2})(?:\.(\d{1,9}))?)?$")


@dataclass(frozen=True)
class NanoTime:
    """Time-of-day with nanosecond precision (replaces ``datetime.time`` for the TIME category).

    The *frac_digits* field controls the format preserved by ``isoformat()``
    when *timespec="auto"*:

    * ``None``  — ``hh:mm``        (no seconds)
    * ``0``     — ``hh:mm:ss``     (seconds, no fraction)
    * ``1``–``9`` — ``hh:mm:ss.s+`` (fractional seconds with that many digits)

    Two NanoTime instances are equal when their *hour*, *minute*, *second*,
    and *nanosecond* match; *frac_digits* is ignored for equality and hashing.
    """

    hour: int = 0
    minute: int = 0
    second: int = 0
    nanosecond: int = 0  # 0–999_999_999
    _frac_digits: Optional[int] = 0  # None=hh:mm, 0=hh:mm:ss, 1-9=hh:mm:ss.s+

    def __post_init__(self) -> None:
        if not (0 <= self.hour <= 23):
            raise ValueError(f"hour must be in 0..23, got {self.hour}")
        if not (0 <= self.minute <= 59):
            raise ValueError(f"minute must be in 0..59, got {self.minute}")
        if not (0 <= self.second <= 59):
            raise ValueError(f"second must be in 0..59, got {self.second}")
        if not (0 <= self.nanosecond <= 999_999_999):
            raise ValueError(f"nanosecond must be in 0..999_999_999, got {self.nanosecond}")
        fd = self._frac_digits
        if fd is not None and not (0 <= fd <= 9):
            raise ValueError(f"frac_digits must be None or 0..9, got {fd}")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NanoTime):
            return NotImplemented
        return (self.hour, self.minute, self.second, self.nanosecond) == (
            other.hour,
            other.minute,
            other.second,
            other.nanosecond,
        )

    def __hash__(self) -> int:
        return hash((self.hour, self.minute, self.second, self.nanosecond))

    @property
    def frac_digits(self) -> Optional[int]:
        """Number of fractional digits preserved (None=hh:mm, 0=hh:mm:ss, 1-9=hh:mm:ss.s+)."""
        return self._frac_digits

    def isoformat(self, timespec: str = "auto") -> str:
        """Return an ISO 8601 time string.

        *timespec* values mirror ``datetime.time.isoformat()``:
        ``"auto"``, ``"hours"``, ``"minutes"``, ``"seconds"``,
        ``"milliseconds"``, ``"microseconds"``, ``"nanoseconds"``.

        When *timespec="auto"*, the output format is controlled by
        ``frac_digits``: ``None`` → ``hh:mm``, ``0`` → ``hh:mm:ss``,
        ``1``–``9`` → ``hh:mm:ss.s+`` with that many fractional digits.
        """
        base_hhmm = f"{self.hour:02d}:{self.minute:02d}"
        if timespec == "hours":
            return base_hhmm
        if timespec == "minutes":
            return base_hhmm

        base_hhmmss = f"{base_hhmm}:{self.second:02d}"
        if timespec == "seconds":
            return base_hhmmss
        if timespec == "milliseconds":
            ms = self.nanosecond // 1_000_000
            return f"{base_hhmmss}.{ms:03d}"
        if timespec == "microseconds":
            us = self.nanosecond // 1_000
            return f"{base_hhmmss}.{us:06d}"
        if timespec == "nanoseconds":
            return f"{base_hhmmss}.{self.nanosecond:09d}"

        # "auto" — use frac_digits to decide format
        fd = self._frac_digits
        if fd is None:
            # hh:mm format
            return base_hhmm
        if fd == 0:
            # hh:mm:ss format
            return base_hhmmss
        # fd is 1–9: hh:mm:ss.s+ with fd fractional digits
        full = f"{self.nanosecond:09d}"
        frac = full[:fd].rstrip("0") or "0"
        return f"{base_hhmmss}.{frac}"

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
            frac_digits = len(frac.rstrip("0")) or 1
        elif m.group(3) is not None:
            ns = 0
            frac_digits = 0
        else:
            ns = 0
            frac_digits = None
        return cls(hour=hour, minute=minute, second=second, nanosecond=ns, _frac_digits=frac_digits)

    def replace(self, **kwargs) -> NanoTime:
        """Return a new NanoTime with specified fields replaced."""
        return NanoTime(
            hour=kwargs.get("hour", self.hour),
            minute=kwargs.get("minute", self.minute),
            second=kwargs.get("second", self.second),
            nanosecond=kwargs.get("nanosecond", self.nanosecond),
            _frac_digits=kwargs.get("_frac_digits", kwargs.get("frac_digits", self._frac_digits)),
        )

    def __str__(self) -> str:
        return self.isoformat()

    def __repr__(self) -> str:
        return f"NanoTime({self.hour}, {self.minute}, {self.second}, {self.nanosecond})"
