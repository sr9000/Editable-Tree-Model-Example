from datetime import date, timedelta, timezone

import pytest
from pandas import Timestamp

from core.datetime_parsing.enums import DateTimeCategory
from core.datetime_parsing.nano_time import NanoTime
from core.datetime_parsing.regex import parse_datetime_text


@pytest.mark.parametrize(
    "text, category, expected",
    [
        # date only
        ("2025-11-02", DateTimeCategory.Date, date(2025, 11, 2)),
        # time only
        ("12:34:56", DateTimeCategory.Time, NanoTime(12, 34, 56)),
        # time+ms
        ("12:34:56.123", DateTimeCategory.Time, NanoTime(12, 34, 56, 123000000)),
        ("12:34:56.123456", DateTimeCategory.Time, NanoTime(12, 34, 56, 123456000)),
        # datetime
        (
            "2025-11-02 12:34:56",
            DateTimeCategory.DateTime,
            Timestamp("2025-11-02 12:34:56"),
        ),
        # tdatetime
        (
            "2025-11-02T12:34:56",
            DateTimeCategory.DateTime,
            Timestamp("2025-11-02 12:34:56"),
        ),
        # datetime+ms
        (
            "2025-11-02 12:34:56.123",
            DateTimeCategory.DateTime,
            Timestamp("2025-11-02 12:34:56.123"),
        ),
        # tdatetime+ms
        (
            "2025-11-02T12:34:56.123456",
            DateTimeCategory.DateTime,
            Timestamp("2025-11-02 12:34:56.123456"),
        ),
        # datetime+tz
        (
            "2025-11-02 12:34:56+01:00",
            DateTimeCategory.DateTimeWithTZ,
            Timestamp("2025-11-02 12:34:56+0100"),
        ),
        # tdatetime+tz
        (
            "2025-11-02T12:34:56-05:30",
            DateTimeCategory.DateTimeWithTZ,
            Timestamp("2025-11-02 12:34:56-0530"),
        ),
        # datetime+ms+tz
        (
            "2025-11-02 12:34:56.123+01:00",
            DateTimeCategory.DateTimeWithTZ,
            Timestamp("2025-11-02 12:34:56.123+0100"),
        ),
        # tdatetime+ms+tz
        (
            "2025-11-02T12:34:56.123-05:30",
            DateTimeCategory.DateTimeWithTZ,
            Timestamp("2025-11-02 12:34:56.123-0530"),
        ),
        # arbitrary separator
        (
            "2025-11-02_12:34:56",
            DateTimeCategory.DateTime,
            Timestamp("2025-11-02 12:34:56"),
        ),
        # utc
        (
            "2025-11-02T12:34:56Z",
            DateTimeCategory.DateTimeUTC,
            Timestamp("2025-11-02 12:34:56", tz="UTC"),
        ),
        (
            "2025-11-02t12:34:56z",
            DateTimeCategory.DateTimeUTC,
            Timestamp("2025-11-02 12:34:56", tz="UTC"),
        ),
        # invalid
        ("invalid", None, None),
    ],
)
def test_parse_text(text, category, expected):
    result = parse_datetime_text(text, category)
    assert result == expected


def test_utc_category_rejects_offset_form():
    assert parse_datetime_text("2026-05-21T14:33:09+05:00", DateTimeCategory.DateTimeUTC) is None


def test_tz_category_rejects_z_form():
    assert parse_datetime_text("2026-05-21T14:33:09Z", DateTimeCategory.DateTimeWithTZ) is None
