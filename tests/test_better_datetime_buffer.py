from datetime import date, datetime, timedelta, timezone

import pytest

from datetime_editor.better_dt_editor import BetterDateTimeBuffer
from datetime_editor.enums import DateTimeCategory


@pytest.fixture()
def buffer() -> BetterDateTimeBuffer:
    return BetterDateTimeBuffer()


def cursor_position(text: str, marker: str = "^") -> int:
    return 1 + text.index(marker)


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


def test_step_year_clamps_day(buffer: BetterDateTimeBuffer) -> None:
    val = "2024-02-29 00:00:00"
    pos = "^024-02-29 00:00:00"
    exp = "2025-02-28 00:00:00"
    date_exp = datetime.fromisoformat(exp)
    text, _ = buffer.set_value(datetime.fromisoformat(val))
    assert text == val
    new_text, _ = buffer.step(+1, cursor_position(pos))
    assert new_text == exp
    assert buffer.value == date_exp


def test_step_month_wraps_without_year_carry(buffer: BetterDateTimeBuffer) -> None:
    val = "2025-12-15 00:00:00"
    pos = "2025-^2-15 00:00:00"
    exp = "2025-01-15 00:00:00"
    date_exp = datetime.fromisoformat(exp)
    text, _ = buffer.set_value(datetime.fromisoformat(val))
    assert text == val
    new_text, _ = buffer.step(+1, cursor_position(pos))
    assert new_text == exp
    assert buffer.value == date_exp


def test_step_day_wraps_within_same_month(buffer: BetterDateTimeBuffer) -> None:
    val = "2025-01-31 08:00:00"
    pos = "2025-01-^1 08:00:00"
    exp = "2025-01-01 08:00:00"
    date_exp = datetime.fromisoformat(exp)
    text, _ = buffer.set_value(datetime.fromisoformat(val))
    assert text == val
    new_text, _ = buffer.step(+1, cursor_position(pos))
    assert new_text == exp
    assert buffer.value == date_exp


def test_step_hour_changes_value(buffer: BetterDateTimeBuffer) -> None:
    val = "2025-01-01 10:00:00"
    pos = "2025-01-01 ^0:00:00"
    exp = "2025-01-01 11:00:00"
    date_exp = datetime.fromisoformat(exp)
    text, _ = buffer.set_value(datetime.fromisoformat(val))
    assert text == val
    new_text, _ = buffer.step(+1, cursor_position(pos))
    assert new_text == exp
    assert buffer.value == date_exp


def test_step_minute_rolls_over(buffer: BetterDateTimeBuffer) -> None:
    val = "2025-01-01 10:59:00"
    pos = "2025-01-01 10:^9:00"
    exp = "2025-01-01 10:00:00"
    date_exp = datetime.fromisoformat(exp)
    text, _ = buffer.set_value(datetime.fromisoformat(val))
    assert text == val
    new_text, _ = buffer.step(+1, cursor_position(pos))
    assert new_text == exp
    assert buffer.value == date_exp


def test_microsecond_precision_respected(buffer: BetterDateTimeBuffer) -> None:
    val = "2025-01-01T00:00:00.123"
    pos = "2025-01-01T00:00:00.^23"
    exp = "2025-01-01T00:00:00.124"
    date_exp = datetime.fromisoformat(exp)
    buffer.set_category(DateTimeCategory.DateTime, "")
    buffer.accept_text(val)
    new_text, _ = buffer.step(+1, cursor_position(pos))
    assert new_text == exp
    assert buffer.value == date_exp


def test_timezone_hour_cross_zero_preserves_minutes(buffer: BetterDateTimeBuffer) -> None:
    val = "2025-01-01T00:00:00-00:45"
    pos = "2025-01-01T00:00:00-^0:45"
    exp = "2025-01-01T00:00:00+00:45"
    date_exp = datetime.fromisoformat(exp)
    buffer.set_category(DateTimeCategory.DateTimeWithTZ, "")
    buffer.accept_text(val)
    new_text, _ = buffer.step(+1, cursor_position(pos))
    assert new_text == exp
    assert buffer.value.tzinfo.utcoffset(buffer.value) == timedelta(minutes=45)
    assert buffer.value == date_exp


def test_timezone_minute_spin_does_not_touch_hours(buffer: BetterDateTimeBuffer) -> None:
    val = "2025-01-01T00:00:00+02:59"
    pos = "2025-01-01T00:00:00+02:^9"
    exp = "2025-01-01T00:00:00+02:00"
    date_exp = datetime.fromisoformat(exp)
    buffer.set_category(DateTimeCategory.DateTimeWithTZ, "")
    buffer.accept_text(val)
    new_text, _ = buffer.step(+1, cursor_position(pos))
    assert new_text == exp
    assert buffer.value == date_exp
    assert buffer.value.tzinfo.utcoffset(buffer.value) == timedelta(hours=2)


def test_timezone_sign_spin(buffer: BetterDateTimeBuffer) -> None:
    val = "2025-01-01T00:00:00-01:00"
    pos = "2025-01-01T00:00:00^01:00"
    exp = "2025-01-01T00:00:00-01:00"
    date_exp = datetime.fromisoformat(exp)
    buffer.set_category(DateTimeCategory.DateTimeWithTZ, "")
    buffer.accept_text(val)
    new_text, _ = buffer.step(+1, cursor_position(pos))
    assert new_text == exp
    assert buffer.value == date_exp
    assert buffer.value.tzinfo.utcoffset(buffer.value) == timedelta(hours=-1)


def test_timezone_utc_segment(buffer: BetterDateTimeBuffer) -> None:
    val = "2025-01-01T00:00:00Z"
    pos = "2025-01-01T00:00:00^"
    exp = "2025-01-01T00:00:01Z"
    date_exp = datetime.fromisoformat(exp)
    buffer.set_category(DateTimeCategory.DateTimeWithTZ, "")
    buffer.accept_text(val)
    new_text, _ = buffer.step(+1, cursor_position(pos))
    assert new_text == exp
    assert buffer.value == date_exp


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
