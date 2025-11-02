import pytest
from PySide6.QtGui import QValidator

from datetime_editor.validator import DateTimeValidator


@pytest.mark.parametrize(
    "text, state",
    [
        # Empty
        ("", QValidator.State.Intermediate),
        # Acceptable
        ("2025-11-02", QValidator.State.Acceptable),
        ("12:34:56", QValidator.State.Acceptable),
        ("2025-11-02 12:34:56", QValidator.State.Acceptable),
        ("2025-11-02T12:34:56", QValidator.State.Acceptable),
        ("2025-11-02T12:34:56.123456", QValidator.State.Acceptable),
        ("2025-11-02T12:34:56Z", QValidator.State.Acceptable),
        ("2025-11-02T12:34:56+01:00", QValidator.State.Acceptable),
        # Intermediate
        ("2025", QValidator.State.Intermediate),
        ("2025-", QValidator.State.Intermediate),
        ("2025-11", QValidator.State.Intermediate),
        ("2025-11-", QValidator.State.Intermediate),
        ("2025-11-0", QValidator.State.Intermediate),
        ("12:", QValidator.State.Intermediate),
        ("12:34:", QValidator.State.Intermediate),
        ("12:34:56.", QValidator.State.Intermediate),
        ("2025-11-02", QValidator.State.Acceptable),
        ("2025-11-02T", QValidator.State.Intermediate),
        ("2025-11-02t1", QValidator.State.Intermediate),
        ("2025-11-02T12", QValidator.State.Intermediate),
        ("2025-11-02T12:", QValidator.State.Intermediate),
        ("2025-11-02T12:3", QValidator.State.Intermediate),
        ("2025-11-02T12:34", QValidator.State.Acceptable),
        ("2025-11-02T12:34:", QValidator.State.Intermediate),
        ("2025-11-02T12:34:5", QValidator.State.Intermediate),
        ("2025-11-02T12:34:56", QValidator.State.Acceptable),
        ("2025-11-02T12:34:56.", QValidator.State.Intermediate),
        ("2025-11-02T12:34:56.1", QValidator.State.Acceptable),
        ("2025-11-02T12:34:56.12", QValidator.State.Acceptable),
        ("2025-11-02T12:34:56.123", QValidator.State.Acceptable),
        ("2025-11-02T12:34:56.1234", QValidator.State.Acceptable),
        ("2025-11-02T12:34:56.12345", QValidator.State.Acceptable),
        ("2025-11-02T12:34:56.123456", QValidator.State.Acceptable),
        ("2025-11-02T12:34:56Z", QValidator.State.Acceptable),
        ("2025-11-02t12:34:56z", QValidator.State.Acceptable),
        ("2025-11-02T12:34:56+01", QValidator.State.Intermediate),
        ("2025-11-02T12:34:56+01:", QValidator.State.Intermediate),
        ("2025-11-02T12:34:56+01:0", QValidator.State.Intermediate),
        ("2025-11-02T12:34:56+01:00", QValidator.State.Acceptable),
        ("2025T12:34:56", QValidator.State.Intermediate),
        ("2025-T12:34:56", QValidator.State.Intermediate),
        ("2025-0T12:34:56", QValidator.State.Intermediate),
        ("2025-02T12:34:56", QValidator.State.Intermediate),
        ("2025-02-T12:34:56", QValidator.State.Intermediate),
        ("2025-02-2T12:34:56", QValidator.State.Intermediate),
        ("2025-02-27T12:34:56", QValidator.State.Acceptable),
        # Invalid
        ("a", QValidator.State.Invalid),
        ("2025-13", QValidator.State.Invalid),
        ("2025-11-32", QValidator.State.Invalid),
        ("25:00", QValidator.State.Invalid),
        ("12:60", QValidator.State.Invalid),
        ("12:34:60", QValidator.State.Invalid),
    ],
)
def test_datetime_validator(text, state):
    validator = DateTimeValidator(None)
    assert validator.validate(text, 0) == state


@pytest.mark.parametrize(
    "pattern",
    [
        "202{5-02-27}T12:34:56",
        "2025-{02}-27T12:34:56",
        "2025-02-{27}T12:34:56",
        "2025-02-27T{12}:34:56",
        "2025-02-27T12:{34}:56",
        "2025-02-27T12:34:{56}",
        "2025-02-27T12:34:56{Z}",
        "2025-02-27T12:34:56{z}",
        "2025-02-27T12:34:56+0{1:00}",
        "2025-02-27T12:34:56-0{8:30}",
        "20{25}-11-02T12:34:56",
        "2025-1{1}-02T12:34:56",
        "2025-11-0{2}T12:34:56",
        "2025-0{2}-27T12:34:56",
        "2025-02-2{7}T12:34:56",
        "12:34:{56}+01:00",
        "2025-02-27T12:34:56+{01:00}",
    ],
)
def test_like_manual_input(pattern):
    """Type chars inside {...} one by one; non-final steps must be Intermediate and final must be Acceptable."""
    start = pattern.index("{")
    end = pattern.index("}", start)
    prefix = pattern[:start]
    chunk = pattern[start + 1 : end]
    suffix = pattern[end + 1 :]

    validator = DateTimeValidator(None)

    # Non-final incremental inputs must be Intermediate
    for i in range(1, len(chunk)):
        s = prefix + chunk[:i] + suffix
        assert validator.validate(s, 0) == QValidator.State.Intermediate, f"Expected Intermediate for: {s!r}"

    # Final full input must be Acceptable
    final = prefix + chunk + suffix
    assert validator.validate(final, 0) == QValidator.State.Acceptable, f"Expected Acceptable for: {final!r}"
