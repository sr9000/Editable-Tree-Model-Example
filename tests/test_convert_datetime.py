from datetime import date, timedelta, timezone

from pandas import Timestamp

from core.datetime_parsing.nano_time import NanoTime
from tree.types import JsonType
from tree.types_datetime import convert_datetime


def test_datetimezone_to_datetimeutc_shifts_clock():
    src = Timestamp("2026-05-21 10:00:00+0500")
    out = convert_datetime(src, JsonType.DATETIMEZONE, JsonType.DATETIMEUTC)
    assert out == Timestamp("2026-05-21 05:00:00+0000")


def test_datetime_to_datetimeutc_keeps_wall_clock():
    src = Timestamp("2026-05-21 10:00:00")
    out = convert_datetime(src, JsonType.DATETIME, JsonType.DATETIMEUTC)
    assert out == Timestamp("2026-05-21 10:00:00", tz="UTC")


def test_datetimeutc_to_datetimezone_stays_utc_offset():
    src = Timestamp("2026-05-21 10:00:00", tz="UTC")
    out = convert_datetime(src, JsonType.DATETIMEUTC, JsonType.DATETIMEZONE)
    assert out.utcoffset() == timedelta(0)
    assert out.hour == 10


def test_supports_all_date_time_switch_pairs():
    seed = {
        JsonType.DATE: date(2026, 5, 21),
        JsonType.TIME: NanoTime(10, 11, 12, 500000000),
        JsonType.DATETIME: Timestamp("2026-05-21 10:11:12.500000"),
        JsonType.DATETIMEZONE: Timestamp("2026-05-21 10:11:12.500000+0300"),
        JsonType.DATETIMEUTC: Timestamp("2026-05-21 10:11:12.500000", tz="UTC"),
    }
    family = tuple(seed.keys())
    for src in family:
        for dst in family:
            out = convert_datetime(seed[src], src, dst)
            assert out is not None


def test_utc_round_trip_through_offsets_is_identity():
    base = Timestamp("2026-05-21 14:33:09.123456", tz="UTC")
    for hours in range(-12, 15):
        tz_dt = base.tz_convert(timezone(timedelta(hours=hours)))
        as_tz = convert_datetime(base, JsonType.DATETIMEUTC, JsonType.DATETIMEZONE)
        # simulate value edited/held with a fixed offset then converted back
        as_tz = as_tz.tz_convert(tz_dt.tzinfo)
        back = convert_datetime(as_tz, JsonType.DATETIMEZONE, JsonType.DATETIMEUTC)
        assert back == base
