import pytest

from core.datetime_parsing.enums import DateTimeCategory
from delegates.formatting.value_formatting import format_with_type
from editors.inline.datetime.better_dt_editor import BetterDateTimeBuffer
from tree.types import JsonType


def test_datetime_format_preservation():
    """
    Checks that the original formatting of the datetime strings (e.g. arbitrary
    separators like '_') is preserved during DATETIMEUTC value formatting.
    """
    # format_with_type returns the string unaffected for DATETIMEUTC
    text = "2026-05-21_14:33:09.123456789Z"
    formatted = format_with_type(text, JsonType.DATETIMEUTC)
    assert formatted == text

    text_t = "2026-05-21T14:33:09Z"
    formatted_t = format_with_type(text_t, JsonType.DATETIMEUTC)
    assert formatted_t == text_t


@pytest.fixture()
def buffer() -> BetterDateTimeBuffer:
    return BetterDateTimeBuffer()


@pytest.mark.parametrize(
    "val_str, inc, exp_str",
    [
        ("2026-05-21T10:00:00.12345678*9", 1, "2026-05-21T10:00:00.123456790"),
        ("2026-05-21 10:00:00.1234567*80", -1, "2026-05-21 10:00:00.123456779"),
    ],
)
def test_datetime_nanosecond_precision_step(buffer: BetterDateTimeBuffer, val_str: str, inc: int, exp_str: str):
    """
    Checks datetime nanosecond precision (step up/down).
    """
    buffer.set_category(DateTimeCategory.DateTime, "")
    clean_val = val_str.replace("*", "")
    assert buffer.accept_text(clean_val) is not None

    new_text, _ = buffer.step(inc, val_str.index("*"))
    assert new_text == exp_str


@pytest.mark.parametrize(
    "val_str, inc, exp_str",
    [
        ("12:34:56.12345678*9", 1, "12:34:56.123456790"),
        ("12:34:56.1234567*80", -1, "12:34:56.123456779"),
    ],
)
def test_time_nanosecond_precision_step(buffer: BetterDateTimeBuffer, val_str: str, inc: int, exp_str: str):
    """
    Checks time nanosecond precision (step up/down).
    """
    buffer.set_category(DateTimeCategory.Time, "")
    clean_val = val_str.replace("*", "")
    assert buffer.accept_text(clean_val) is not None

    new_text, _ = buffer.step(inc, val_str.index("*"))
    assert new_text == exp_str


@pytest.mark.parametrize(
    "val_str, inc, exp_str",
    [
        # 1-digit fraction
        ("2025-01-01T00:00:00.*1", 1, "2025-01-01T00:00:00.2"),
        # 2-digits fraction
        ("2025-01-01T00:00:00.1*2", -1, "2025-01-01T00:00:00.11"),
        # 4-digits fraction
        ("2025-01-01T00:00:00.123*4", 1, "2025-01-01T00:00:00.1235"),
        # 6-digits fraction
        ("12:34:56.12345*6", -1, "12:34:56.123455"),
        # 9-digits fraction
        ("12:34:56.12345678*9", 1, "12:34:56.123456790"),
        # 9-digits fraction stepping down
        ("12:34:56.12345678*0", -1, "12:34:56.123456779"),
    ],
)
def test_arbitrary_fraction_precision_preservation(buffer: BetterDateTimeBuffer, val_str: str, inc: int, exp_str: str):
    """
    Checks arbitrary fraction precision preservation (1-9 digits).
    The step operations should maintain the required padding / precision length as parsed,
    unless inherently zero-padded up.
    """
    # Category fallback depends on the presence of date in string
    category = DateTimeCategory.DateTime if "T" in val_str else DateTimeCategory.Time
    buffer.set_category(category, "")

    clean_val = val_str.replace("*", "")
    assert buffer.accept_text(clean_val) is not None

    new_text, _ = buffer.step(inc, val_str.index("*"))
    assert new_text == exp_str
