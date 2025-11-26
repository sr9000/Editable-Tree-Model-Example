from datetime import date, datetime, timedelta, timezone

import pytest

from datetime_editor.better_dt_editor import BetterDateTimeBuffer
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
