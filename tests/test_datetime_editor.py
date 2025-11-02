from datetime import date, datetime, time, timedelta, timezone

import pytest

from datetime_editor.enums import DateTimeCategory
from datetime_editor.regex import parse_datetime_text


@pytest.mark.parametrize(
    "text, category, expected",
    [
        # date only
        ("2025-11-02", DateTimeCategory.Date, date(2025, 11, 2)),
        # time only
        ("12:34:56", DateTimeCategory.Time, time(12, 34, 56)),
        # time+ms
        ("12:34:56.123", DateTimeCategory.Time, time(12, 34, 56, 123000)),
        ("12:34:56.123456", DateTimeCategory.Time, time(12, 34, 56, 123456)),
        ("12:34:56.123456789", DateTimeCategory.Time, time(12, 34, 56, 123456)),
        # datetime
        (
            "2025-11-02 12:34:56",
            DateTimeCategory.DateTime,
            datetime(2025, 11, 2, 12, 34, 56),
        ),
        # tdatetime
        (
            "2025-11-02T12:34:56",
            DateTimeCategory.DateTime,
            datetime(2025, 11, 2, 12, 34, 56),
        ),
        # datetime+ms
        (
            "2025-11-02 12:34:56.123",
            DateTimeCategory.DateTime,
            datetime(2025, 11, 2, 12, 34, 56, 123000),
        ),
        # tdatetime+ms
        (
            "2025-11-02T12:34:56.123456",
            DateTimeCategory.DateTime,
            datetime(2025, 11, 2, 12, 34, 56, 123456),
        ),
        # datetime+tz
        (
            "2025-11-02 12:34:56+01:00",
            DateTimeCategory.DateTimeWithTZ,
            datetime(2025, 11, 2, 12, 34, 56, tzinfo=timezone(timedelta(hours=1))),
        ),
        # tdatetime+tz
        (
            "2025-11-02T12:34:56-05:30",
            DateTimeCategory.DateTimeWithTZ,
            datetime(
                2025,
                11,
                2,
                12,
                34,
                56,
                tzinfo=timezone(timedelta(hours=-5, minutes=-30)),
            ),
        ),
        # datetime+ms+tz
        (
            "2025-11-02 12:34:56.123+01:00",
            DateTimeCategory.DateTimeWithTZ,
            datetime(
                2025, 11, 2, 12, 34, 56, 123000, tzinfo=timezone(timedelta(hours=1))
            ),
        ),
        # tdatetime+ms+tz
        (
            "2025-11-02T12:34:56.123-05:30",
            DateTimeCategory.DateTimeWithTZ,
            datetime(
                2025,
                11,
                2,
                12,
                34,
                56,
                123000,
                tzinfo=timezone(timedelta(hours=-5, minutes=-30)),
            ),
        ),
        # arbitrary separator
        (
            "2025-11-02_12:34:56",
            DateTimeCategory.DateTime,
            datetime(2025, 11, 2, 12, 34, 56),
        ),
        # utc
        (
            "2025-11-02T12:34:56Z",
            DateTimeCategory.DateTimeWithTZ,
            datetime(2025, 11, 2, 12, 34, 56, tzinfo=timezone.utc),
        ),
        (
            "2025-11-02t12:34:56z",
            DateTimeCategory.DateTimeWithTZ,
            datetime(2025, 11, 2, 12, 34, 56, tzinfo=timezone.utc),
        ),
        # invalid
        ("invalid", None, None),
    ],
)
def test_parse_text(text, category, expected):
    assert parse_datetime_text(text, category) == expected
