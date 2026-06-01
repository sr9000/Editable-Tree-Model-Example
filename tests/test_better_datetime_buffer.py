from datetime import date, datetime, timedelta

import pytest
from pandas import Timestamp

from core.datetime_parsing.enums import DateTimeCategory
from core.datetime_parsing.nano_time import NanoTime
from editors.inline.datetime.better_dt_editor import BetterDateTimeBuffer


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
    date_exp = Timestamp(datetime_text)
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
        ("2024-0*1-31 00:00:00", 10, "2024-04-30 00:00:00"),
        ("2024-01-01 00:00:00.12*3000", 1, "2024-01-01 00:00:00.123001"),
    ],
)
def test_step_with_set_value(buffer: BetterDateTimeBuffer, val_str: str, inc: int, exp_str: str) -> None:
    clr = val_str.replace("*", "")
    val = Timestamp(datetime.fromisoformat(clr))
    exp_val = Timestamp(datetime.fromisoformat(exp_str))
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
    exp_val = Timestamp(exp_str)
    buffer.set_category(ctg, "")
    buffer.accept_text(val_str.replace("*", ""))
    new_text, _ = buffer.step(inc, val_str.index("*"))
    assert buffer.value == exp_val
    assert new_text == exp_str
    if exp_offset_minutes is not None:
        assert buffer.value.tzinfo.utcoffset(buffer.value) == timedelta(minutes=exp_offset_minutes)


def test_utc_category_rejects_timezone_step(buffer: BetterDateTimeBuffer) -> None:
    buffer.set_category(DateTimeCategory.DateTimeUTC, "")
    buffer.accept_text("2025-01-01T00:00:00Z")
    assert buffer.step(1, cursor_pos=len("2025-01-01T00:00:00Z")) is None


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
    val = Timestamp(2024, 5, 6, 7, 8, 9)
    text, _ = buffer.set_value(val)
    result = buffer.step(+1, cursor_pos=len(text) + 5)
    assert result is not None
    new_text, cursor = result
    assert new_text == "2024-05-06 07:08:10"
    assert cursor == len(new_text)


def test_segment_helpers_return_none(buffer: BetterDateTimeBuffer) -> None:
    buffer.set_value(Timestamp(2024, 1, 1, 0, 0, 0))
    assert buffer._segment_at_cursor(10_000) is None
    assert buffer._segment_by_name("tz_sign") is None


def test_format_value_and_as_datetime_type_errors() -> None:
    with pytest.raises(TypeError):
        BetterDateTimeBuffer._format_value(object())
    with pytest.raises(TypeError):
        BetterDateTimeBuffer._as_datetime(object())
