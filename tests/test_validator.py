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
    "source,pattern,accepted",
    [
        ("202*T12:34:56", "5-02-27", {"2025-02-27T12:34:56"}),  # just typing
        ("*7", "202-<5>-<02>2", {"2025-02-27"}),  # move caret
        ("1*6", "2:3:<4>5", {"12:36", "12:34:56"}),  # also move caret
        (
            "12:34:56*",
            ".(123)(456)",
            {"12:34:56.123", "12:34:56.123456"},
        ),  # paste at once
    ],
)
def test_like_manual_input(source, pattern, accepted):
    """
    Extended input syntax:
      - plain chars: typed at caret one by one
      - '(...)': paste the whole chunk at caret as a single step
      - '<', '>': move caret left and right
    All non-final texts must be Intermediate; final must be Acceptable and equal to 'result'.
    """
    # initial text and caret
    caret = source.index("*")
    text = source.replace("*", "")
    validator = DateTimeValidator(None)

    # helper: append new slots created by inserted content and shift existing ones
    def insert_at(chunk: str):
        nonlocal text, caret
        text = text[:caret] + chunk + text[caret:]
        caret += len(chunk)

    # tokenize and simulate
    i = 0
    steps = []  # collect texts after each mutating step
    while i < len(pattern):
        ch = pattern[i]
        i += 1
        match ch:
            case "(":
                j = pattern.index(")", i)
                insert_at(pattern[i:j])
                i = j + 1
            case "<":
                caret -= 1
            case ">":
                caret += 1
            case _:
                insert_at(ch)

        res = validator.validate(text, caret)
        if text in accepted:
            assert (
                res == QValidator.State.Acceptable
            ), f"Expected Acceptable for: {text!r}"
        else:
            assert (
                res == QValidator.State.Intermediate
            ), f"Expected Intermediate for: {text!r}"

    assert text in accepted, f"Result {text!r} is missing in accepted set: {accepted!r}"
