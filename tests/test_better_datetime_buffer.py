from datetime import date, datetime, time, timedelta, timezone

import pytest

from datetime_editor.better_dt_editor import BetterDateTimeBuffer, _Segment
from datetime_editor.enums import DateTimeCategory


@pytest.fixture()
def buffer() -> BetterDateTimeBuffer:
    return BetterDateTimeBuffer()


def test_set_value_round_trip(buffer: BetterDateTimeBuffer) -> None:
    date_text = "2025-01-02"
    date_exp = date.fromisoformat(date_text)
    text, category = buffer.set_value(date_exp)
    assert text == date_text
    assert category == DateTimeCategory.Date
    assert buffer.value == date_exp


def test_accept_text_updates_value_and_segments(buffer: BetterDateTimeBuffer) -> None:
    datetime_text = "2025-01-02T03:04:05"
    date_exp = datetime.fromisoformat(datetime_text)
    buffer.set_category(DateTimeCategory.DateTime, "")
    parsed = buffer.accept_text(datetime_text)
    assert parsed == date_exp
    assert buffer.value == date_exp
    assert buffer.last_valid_text == datetime_text
    assert {seg.name for seg in buffer._segments} >= {"year", "month", "day", "hour", "minute", "second"}


def test_revert_text_restores_last_valid(buffer: BetterDateTimeBuffer) -> None:
    date_text = "2025-01-02"
    date_exp = date.fromisoformat(date_text)
    buffer.set_value(date_exp)
    buffer.intermediate_text("2025-0")
    restored = buffer.revert_text()
    assert restored == date_text
    assert buffer.value == date_exp


@pytest.mark.parametrize(
    "val_str, inc, exp_str",
    [
        ("2*024-02-29 00:00:00", 1, "2025-02-28 00:00:00"),
        ("2025-1*2-15 00:00:00", 1, "2025-01-15 00:00:00"),
        ("2025-01-3*1 08:00:00", 1, "2025-01-01 08:00:00"),
        ("2025-01-01 1*0:00:00", 1, "2025-01-01 11:00:00"),
        ("2025-01-01 10:5*9:00", 1, "2025-01-01 10:00:00"),
    ],
)
def test_step_with_set_value(buffer: BetterDateTimeBuffer, val_str: str, inc: int, exp_str: str) -> None:
    clr = val_str.replace("*", "")
    val = datetime.fromisoformat(clr)
    exp_val = datetime.fromisoformat(exp_str)
    text, _ = buffer.set_value(val)
    assert text == clr
    new_text, _ = buffer.step(inc, val_str.index("*"))
    assert new_text == exp_str
    assert buffer.value == exp_val


@pytest.mark.parametrize(
    "ctg, val_str, inc, exp_str, exp_offset_minutes",
    [
        (DateTimeCategory.DateTime, "2025-01-01T00:00:00.1*23", 1, "2025-01-01T00:00:00.124", None),
        (DateTimeCategory.DateTimeWithTZ, "2025-01-01T00:00:00-0*0:45", 1, "2025-01-01T00:00:00+00:45", 45),
        (DateTimeCategory.DateTimeWithTZ, "2025-01-01T00:00:00+02:5*9", 1, "2025-01-01T00:00:00+02:00", 120),
        (DateTimeCategory.DateTimeWithTZ, "2025-01-01T00:00:00-*01:00", 1, "2025-01-01T00:00:00+01:00", 60),
        (DateTimeCategory.DateTimeWithTZ, "2025-01-01T00:00:00Z*", 1, "2025-01-01T00:00:00+01:00", 60),
        (DateTimeCategory.DateTimeWithTZ, "2025-01-01T00:00:00+0*0:30", -1, "2025-01-01T00:00:00-00:30", -30),
        (DateTimeCategory.DateTimeWithTZ, "2025-01-01T00:00:00-02:1*5", 1, "2025-01-01T00:00:00-02:16", -136),
    ],
)
def test_step_with_accept_text(
    buffer: BetterDateTimeBuffer,
    ctg: DateTimeCategory,
    val_str: str,
    inc: int,
    exp_str: str,
    exp_offset_minutes: int | None,
) -> None:
    exp_val = datetime.fromisoformat(exp_str)
    buffer.set_category(ctg, "")
    buffer.accept_text(val_str.replace("*", ""))
    new_text, _ = buffer.step(inc, val_str.index("*"))
    assert buffer.value == exp_val
    assert new_text == exp_str
    if exp_offset_minutes is not None:
        assert buffer.value.tzinfo.utcoffset(buffer.value) == timedelta(minutes=exp_offset_minutes)


def test_step_returns_none_without_value(buffer: BetterDateTimeBuffer) -> None:
    placeholder_text = "2025-"
    buffer.set_category(DateTimeCategory.DateTime, "")
    buffer.intermediate_text(placeholder_text)
    result = buffer.step(+1, cursor_pos=5)
    assert result is None
    assert buffer._text == placeholder_text
    assert buffer.value is None


def test_revert_after_invalid_input(buffer: BetterDateTimeBuffer) -> None:
    val = "2025-05-04"
    updated_text = "2025-05-05"
    date_val = date.fromisoformat(val)
    updated_value = date.fromisoformat(updated_text)
    buffer.set_value(date_val)
    buffer.accept_text(updated_text)
    buffer.intermediate_text("invalid")
    restored = buffer.revert_text()
    assert restored == updated_text
    assert buffer.value == updated_value


def test_buffer_category_and_invalid_accept(buffer: BetterDateTimeBuffer) -> None:
    assert buffer.category is None
    assert buffer.value is None
    assert buffer.last_valid_text == ""
    valid_text = "2024-02-29"
    buffer.set_category(DateTimeCategory.Date, valid_text)
    assert buffer.category == DateTimeCategory.Date
    assert buffer.value == date.fromisoformat(valid_text)
    assert buffer.last_valid_text == ""
    rejected = buffer.accept_text("not-a-date")
    assert rejected is None
    assert buffer.last_valid_text == ""


def test_step_uses_last_segment_when_cursor_outside(buffer: BetterDateTimeBuffer) -> None:
    val = datetime(2024, 5, 6, 7, 8, 9)
    text, _ = buffer.set_value(val)
    result = buffer.step(+1, cursor_pos=len(text) + 5)
    assert result is not None
    new_text, cursor = result
    assert new_text == "2024-05-06 07:08:10"
    assert cursor == len(new_text)


def test_segment_helpers_return_none(buffer: BetterDateTimeBuffer) -> None:
    buffer.set_value(datetime(2024, 1, 1, 0, 0, 0))
    assert buffer._segment_at_cursor(10_000) is None
    assert buffer._segment_by_name("tz_sign") is None


def test_apply_delta_requires_value(buffer: BetterDateTimeBuffer) -> None:
    segment = _Segment(name="year", start=0, end=4, text="2024")
    buffer._segments = [segment]
    buffer._value = None
    assert buffer._apply_delta_to_segment(segment, 1) is None


def test_apply_delta_unknown_segment(buffer: BetterDateTimeBuffer) -> None:
    buffer.set_value(datetime(2024, 1, 1, 0, 0, 0))
    unknown = _Segment(name="unknown", start=0, end=0, text="")
    assert buffer._apply_delta_to_segment(unknown, 1) is None


def test_month_delta_is_clamped(buffer: BetterDateTimeBuffer) -> None:
    val = datetime(2024, 1, 31, 0, 0, 0)
    buffer.set_value(val)
    month_segment = buffer._segment_by_name("month")
    assert month_segment is not None
    buffer.step(10, month_segment.start)
    assert buffer.value.month == 4
    assert buffer.value.day == 30


def test_microsecond_delta_and_formatting(buffer: BetterDateTimeBuffer) -> None:
    val = datetime(2024, 5, 6, 7, 8, 9, microsecond=321000)
    buffer.set_value(val)
    micro_segment = buffer._segment_by_name("microsecond")
    assert micro_segment is not None
    buffer.step(1, micro_segment.start)
    assert buffer.value.microsecond == 321001
    assert BetterDateTimeBuffer._format_microsecond(123456, 3) == "123"
    assert BetterDateTimeBuffer._format_microsecond(7, 0) == "000007"


def test_rebuild_timezone_segments_without_segments(buffer: BetterDateTimeBuffer) -> None:
    buffer.set_value(datetime(2024, 1, 1, 1, 2, 3))
    anchor = buffer._segment_by_name("second")
    assert anchor is not None
    assert buffer._rebuild_timezone_segments(datetime(2024, 1, 1, tzinfo=timezone.utc), anchor) is None


def test_rebuild_timezone_segments_cursor_fallback(monkeypatch, buffer: BetterDateTimeBuffer) -> None:
    val = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone(timedelta(hours=1, minutes=15)))
    buffer.set_value(val)
    anchor = buffer._segment_by_name("tz_hour")
    assert anchor is not None

    original = BetterDateTimeBuffer._format_segment_value

    def fake_format(name: str, value: datetime, width: int):
        if name == "tz_hour":
            return None
        return original(name, value, width)

    monkeypatch.setattr(BetterDateTimeBuffer, "_format_segment_value", staticmethod(fake_format))
    new_text, cursor = buffer._rebuild_timezone_segments(val, anchor)
    assert new_text.endswith("+01:15")
    assert cursor == anchor.start


def test_format_value_and_restore_type_variants() -> None:
    naive_dt = datetime(2024, 6, 1, 12, 30, 15)
    text, category = BetterDateTimeBuffer._format_value(naive_dt)
    assert text == "2024-06-01 12:30:15"
    assert category == DateTimeCategory.DateTime
    aware_dt = naive_dt.replace(tzinfo=timezone.utc)
    tz_text, tz_category = BetterDateTimeBuffer._format_value(aware_dt)
    assert tz_text.endswith("+00:00")
    assert tz_category == DateTimeCategory.DateTimeWithTZ
    d_val = date(2024, 6, 1)
    d_text, d_category = BetterDateTimeBuffer._format_value(d_val)
    assert d_text == d_val.isoformat()
    assert d_category == DateTimeCategory.Date
    t_val = time(10, 11, 12)
    t_text, t_category = BetterDateTimeBuffer._format_value(t_val)
    assert t_text == t_val.isoformat()
    assert t_category == DateTimeCategory.Time

    base = datetime(2024, 6, 1, 12, 30, 15, tzinfo=timezone(timedelta(hours=2)))
    assert BetterDateTimeBuffer._restore_type(base, DateTimeCategory.Date) == base.date()
    assert BetterDateTimeBuffer._restore_type(base, DateTimeCategory.Time) == base.time()
    assert BetterDateTimeBuffer._restore_type(base, DateTimeCategory.DateTime).tzinfo is None
    assert (
        BetterDateTimeBuffer._restore_type(base.replace(tzinfo=None), DateTimeCategory.DateTimeWithTZ).tzinfo
        == timezone.utc
    )
    assert BetterDateTimeBuffer._restore_type(base, None) == base


def test_format_value_and_as_datetime_type_errors() -> None:
    with pytest.raises(TypeError):
        BetterDateTimeBuffer._format_value(object())
    with pytest.raises(TypeError):
        BetterDateTimeBuffer._as_datetime(object())


def test_timezone_helper_adjustments() -> None:
    assert BetterDateTimeBuffer._compose_timezone(-1, 20, 45) == -(14 * 60)
    assert BetterDateTimeBuffer._compose_timezone(-1, 0, 0) == 0
    assert BetterDateTimeBuffer._adjust_timezone_minutes("tz_hour", 0, 0) == 0
    assert BetterDateTimeBuffer._adjust_timezone_minutes("tz_hour", 0, 2) == 120
    assert BetterDateTimeBuffer._adjust_timezone_minutes("tz_hour", -120, 1) == -60
    assert BetterDateTimeBuffer._adjust_timezone_minutes("tz_hour", 0, -1) == -60
    assert BetterDateTimeBuffer._adjust_timezone_minutes("tz_minute", 60, 10) == 70
    assert BetterDateTimeBuffer._adjust_timezone_minutes("tz_minute", 60, -90) == 90
    assert BetterDateTimeBuffer._adjust_timezone_minutes("tz_sign", -60, 1) == 60
    assert BetterDateTimeBuffer._adjust_timezone_minutes("utc", -120, 2) == 120
    assert BetterDateTimeBuffer._format_timezone_string(90) == "+01:30"
    assert BetterDateTimeBuffer._format_timezone_string(-90) == "-01:30"


def test_format_segment_value_timezone_padding() -> None:
    naive = datetime(2024, 1, 1, 2, 3, 4, microsecond=5)
    assert BetterDateTimeBuffer._format_segment_value("minute", naive, 3) == "003"
    assert BetterDateTimeBuffer._format_segment_value("second", naive, 2) == "04"
    assert BetterDateTimeBuffer._format_segment_value("microsecond", naive, 3) == "000"
    assert BetterDateTimeBuffer._format_segment_value("tz_sign", naive, 1) == "+"
    assert BetterDateTimeBuffer._format_segment_value("tz_hour", naive, 0) == "00"
    assert BetterDateTimeBuffer._format_segment_value("tz_minute", naive, 0) == "00"
    assert BetterDateTimeBuffer._format_segment_value("utc", naive, 0) == "Z"

    offset = naive.replace(tzinfo=timezone(-timedelta(hours=5, minutes=30)))
    assert BetterDateTimeBuffer._format_segment_value("tz_sign", offset, 1) == "-"
    assert BetterDateTimeBuffer._format_segment_value("tz_hour", offset, 0) == "05"
    assert BetterDateTimeBuffer._format_segment_value("tz_minute", offset, 0) == "30"
    assert BetterDateTimeBuffer._format_segment_value("utc", offset, 0) == "-05:30"
