from datetime import date, datetime, timedelta, timezone

import pytest

from datetime_editor.better_dt_editor import BetterDateTimeBuffer
from datetime_editor.enums import DateTimeCategory


def cursor_from_mask(text: str, mask: str) -> int:
    assert len(text) == len(mask), "mask must match text length"
    assert mask.count("*") == 1, "mask must contain exactly one '*'"
    index = mask.index("*")
    return index


def mask_at(text: str, index: int) -> str:
    return " " * index + "*" + " " * (len(text) - index - 1)


@pytest.fixture()
def buffer() -> BetterDateTimeBuffer:
    return BetterDateTimeBuffer()


def test_set_value_round_trip(buffer: BetterDateTimeBuffer) -> None:
    text, category = buffer.set_value(date(2025, 1, 2))
    assert text == "2025-01-02"
    assert category == DateTimeCategory.Date
    assert buffer.value == date(2025, 1, 2)


def test_accept_text_updates_value_and_segments(buffer: BetterDateTimeBuffer) -> None:
    buffer.set_category(DateTimeCategory.DateTime, "")
    parsed = buffer.accept_text("2025-01-02T03:04:05")
    assert parsed == datetime(2025, 1, 2, 3, 4, 5)
    assert buffer.last_valid_text == "2025-01-02T03:04:05"
    assert {seg.name for seg in buffer._segments} >= {"year", "month", "day", "hour", "minute", "second"}


def test_revert_text_restores_last_valid(buffer: BetterDateTimeBuffer) -> None:
    buffer.set_value(date(2025, 1, 2))
    buffer.intermediate_text("2025-0")
    restored = buffer.revert_text()
    assert restored == "2025-01-02"
    assert buffer.value == date(2025, 1, 2)


def test_step_year_clamps_day(buffer: BetterDateTimeBuffer) -> None:
    text, _ = buffer.set_value(datetime(2024, 2, 29, 0, 0, 0))
    mask = mask_at(text, 0)
    cursor = cursor_from_mask(text, mask)
    new_text, _ = buffer.step(+1, cursor)
    assert new_text.startswith("2025-02-28")
    assert buffer.value == datetime(2025, 2, 28, 0, 0, 0)


def test_step_month_wraps_without_year_carry(buffer: BetterDateTimeBuffer) -> None:
    text, _ = buffer.set_value(datetime(2025, 12, 15, 0, 0, 0))
    idx = text.index("12")
    mask = mask_at(text, idx)
    cursor = cursor_from_mask(text, mask)
    buffer.step(+1, cursor)
    assert buffer.value == datetime(2025, 1, 15, 0, 0, 0)


def test_step_day_wraps_within_same_month(buffer: BetterDateTimeBuffer) -> None:
    text, _ = buffer.set_value(datetime(2025, 1, 31, 8, 0, 0))
    assert text == "2025-01-31 08:00:00"
    idx = text.index("31")
    mask = mask_at(text, idx)
    cursor = cursor_from_mask(text, mask)
    buffer.step(+1, cursor)
    assert buffer.value == datetime(2025, 1, 1, 8, 0, 0)


def test_step_hour_changes_value(buffer: BetterDateTimeBuffer) -> None:
    text, _ = buffer.set_value(datetime(2025, 1, 1, 10, 0, 0))
    idx = text.index("10")
    mask = mask_at(text, idx)
    cursor = cursor_from_mask(text, mask)
    buffer.step(+1, cursor)
    assert buffer.value == datetime(2025, 1, 1, 11, 0, 0)


def test_step_minute_rolls_over(buffer: BetterDateTimeBuffer) -> None:
    text, _ = buffer.set_value(datetime(2025, 1, 1, 10, 59, 0))
    idx = text.index("59")
    cursor = cursor_from_mask(text, mask_at(text, idx))
    buffer.step(+1, cursor)
    assert buffer.value == datetime(2025, 1, 1, 10, 0, 0)


def test_microsecond_precision_respected(buffer: BetterDateTimeBuffer) -> None:
    date_str = "2025-01-01T00:00:00.123"
    buffer.set_category(DateTimeCategory.DateTime, "")
    buffer.accept_text(date_str)
    idx = date_str.index(".") + 1
    mask = mask_at(date_str, idx)
    cursor = cursor_from_mask(date_str, mask)
    new_text, _ = buffer.step(+1, cursor)
    assert new_text.endswith(".124")
    assert buffer.value.microsecond == 124000


def test_timezone_hour_cross_zero_preserves_minutes(buffer: BetterDateTimeBuffer) -> None:
    date_str = "2025-01-01T00:00:00-00:45"
    buffer.set_category(DateTimeCategory.DateTimeWithTZ, "")
    buffer.accept_text(date_str)
    idx = date_str.rfind("-00:45") + 1
    mask = mask_at(date_str, idx)
    cursor = cursor_from_mask(date_str, mask)
    new_text, _ = buffer.step(+1, cursor)
    assert new_text.endswith("+00:45")
    assert buffer.value.tzinfo.utcoffset(buffer.value) == timedelta(minutes=45)


def test_timezone_minute_spin_does_not_touch_hours(buffer: BetterDateTimeBuffer) -> None:
    date_str = "2025-01-01T00:00:00+02:59"
    buffer.set_category(DateTimeCategory.DateTimeWithTZ, "")
    buffer.accept_text(date_str)
    idx = date_str.rfind(":") + 1
    mask = mask_at(date_str, idx)
    cursor = cursor_from_mask(date_str, mask)
    new_text, _ = buffer.step(+1, cursor)
    assert new_text.endswith("+02:00")
    assert buffer.value.tzinfo.utcoffset(buffer.value) == timedelta(hours=2)


def test_timezone_sign_spin(buffer: BetterDateTimeBuffer) -> None:
    date_str = "2025-01-01T00:00:00-01:00"
    mask = "      *              "
    buffer.set_category(DateTimeCategory.DateTimeWithTZ, "")
    buffer.accept_text(date_str)
    mask = mask.ljust(len(date_str))
    cursor = cursor_from_mask(date_str, mask)
    new_text, _ = buffer.step(+1, cursor)
    assert new_text.endswith("-01:00")
    assert buffer.value.tzinfo.utcoffset(buffer.value) == timedelta(hours=-1)


def test_timezone_utc_segment(buffer: BetterDateTimeBuffer) -> None:
    date_str = "2025-01-01T00:00:00Z"
    buffer.set_category(DateTimeCategory.DateTimeWithTZ, "")
    buffer.accept_text(date_str)
    idx = date_str.rfind("Z")
    mask = mask_at(date_str, idx)
    cursor = cursor_from_mask(date_str, mask)
    new_text, _ = buffer.step(+1, cursor)
    assert new_text.endswith("Z")
    assert buffer.value == datetime(2025, 1, 1, 0, 0, 1, tzinfo=timezone.utc)


def test_step_returns_none_without_value(buffer: BetterDateTimeBuffer) -> None:
    buffer.set_category(DateTimeCategory.DateTime, "")
    buffer.intermediate_text("2025-")
    assert buffer.step(+1, cursor_pos=5) is None


def test_revert_after_invalid_input(buffer: BetterDateTimeBuffer) -> None:
    buffer.set_value(date(2025, 5, 4))
    buffer.accept_text("2025-05-05")
    buffer.intermediate_text("invalid")
    restored = buffer.revert_text()
    assert restored == "2025-05-05"
    assert buffer.value == date(2025, 5, 5)
