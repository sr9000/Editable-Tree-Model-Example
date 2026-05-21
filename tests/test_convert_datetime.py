from datetime import date, datetime, time, timedelta, timezone

from tree.types import JsonType
from tree.types_datetime import convert_datetime


def test_datetimezone_to_datetimeutc_shifts_clock():
    src = datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone(timedelta(hours=5)))
    out = convert_datetime(src, JsonType.DATETIMEZONE, JsonType.DATETIMEUTC)
    assert out == datetime(2026, 5, 21, 5, 0, 0, tzinfo=timezone.utc)


def test_datetime_to_datetimeutc_keeps_wall_clock():
    src = datetime(2026, 5, 21, 10, 0, 0)
    out = convert_datetime(src, JsonType.DATETIME, JsonType.DATETIMEUTC)
    assert out == datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone.utc)


def test_datetimeutc_to_datetimezone_stays_utc_offset():
    src = datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone.utc)
    out = convert_datetime(src, JsonType.DATETIMEUTC, JsonType.DATETIMEZONE)
    assert out.utcoffset() == timedelta(0)
    assert out.hour == 10


def test_supports_all_date_time_switch_pairs():
    seed = {
        JsonType.DATE: date(2026, 5, 21),
        JsonType.TIME: time(10, 11, 12, 500000),
        JsonType.DATETIME: datetime(2026, 5, 21, 10, 11, 12, 500000),
        JsonType.DATETIMEZONE: datetime(2026, 5, 21, 10, 11, 12, 500000, tzinfo=timezone(timedelta(hours=3))),
        JsonType.DATETIMEUTC: datetime(2026, 5, 21, 10, 11, 12, 500000, tzinfo=timezone.utc),
    }
    family = tuple(seed.keys())
    for src in family:
        for dst in family:
            out = convert_datetime(seed[src], src, dst)
            assert out is not None


def test_utc_round_trip_through_offsets_is_identity():
    base = datetime(2026, 5, 21, 14, 33, 9, 123456, tzinfo=timezone.utc)
    for hours in range(-12, 15):
        tz_dt = base.astimezone(timezone(timedelta(hours=hours)))
        as_tz = convert_datetime(base, JsonType.DATETIMEUTC, JsonType.DATETIMEZONE)
        # simulate value edited/held with a fixed offset then converted back
        as_tz = as_tz.astimezone(tz_dt.tzinfo)
        back = convert_datetime(as_tz, JsonType.DATETIMEZONE, JsonType.DATETIMEUTC)
        assert back == base
