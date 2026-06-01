import pytest
from PySide6.QtGui import QValidator

from core.datetime_parsing.enums import DateTimeCategory
from editors.inline.datetime.validator import DateTimeValidator

ALL_CATEGORIES = {None} | set(DateTimeCategory)
PURE_CATEGORIES = {DateTimeCategory.Date, DateTimeCategory.Time}
INCOMPLETE_CATEGORIES = set(DateTimeCategory) - {DateTimeCategory.DateTimeWithTZ, DateTimeCategory.DateTimeUTC}
UTC_INVALID_CATEGORIES = INCOMPLETE_CATEGORIES | {DateTimeCategory.DateTimeWithTZ}
OFFSET_INVALID_CATEGORIES = INCOMPLETE_CATEGORIES | {DateTimeCategory.DateTimeUTC}


@pytest.mark.parametrize(
    "text, invalid, accepted",
    [
        # Empty
        ("", {}, {}),
        # Acceptable
        ("2025-11-02", {DateTimeCategory.Time}, {DateTimeCategory.Date}),
        ("12:34:56", {DateTimeCategory.Date}, {DateTimeCategory.Time}),
        ("2025-11-02 12:34:56", PURE_CATEGORIES, {DateTimeCategory.DateTime}),
        ("2025-11-02T12:34:56", PURE_CATEGORIES, {DateTimeCategory.DateTime}),
        ("2025-11-02T12:34:56.123456", PURE_CATEGORIES, {DateTimeCategory.DateTime}),
        ("2025-11-02T12:34:56Z", UTC_INVALID_CATEGORIES, {DateTimeCategory.DateTimeUTC}),
        ("2025-11-02T12:34:56+01:00", OFFSET_INVALID_CATEGORIES, {DateTimeCategory.DateTimeWithTZ}),
        # Intermediate
        ("20", {}, {}),
        ("-12", {DateTimeCategory.Time}, {}),
        ("-20", ALL_CATEGORIES, {}),  # month cannot be 20
        ("--20", {DateTimeCategory.Time}, {}),
        ("2025", {DateTimeCategory.Time}, {}),
        ("2025-", {DateTimeCategory.Time}, {}),
        ("2025-11", {DateTimeCategory.Time}, {}),
        ("2025-11-", {DateTimeCategory.Time}, {}),
        ("2025-11-0", {DateTimeCategory.Time}, {}),
        ("12:", {DateTimeCategory.Date}, {}),
        ("12:3", {DateTimeCategory.Date}, {}),
        ("12:34", {DateTimeCategory.Date}, {DateTimeCategory.Time}),
        ("12:34:", {DateTimeCategory.Date}, {}),
        ("12:34:5", {DateTimeCategory.Date}, {}),
        ("12:34:56", {DateTimeCategory.Date}, {DateTimeCategory.Time}),
        ("12:34:56.", {DateTimeCategory.Date}, {}),
        ("12:34:56.123456", {DateTimeCategory.Date}, {DateTimeCategory.Time}),
        ("T12:34:56.123456", PURE_CATEGORIES, {}),
        ("2025-11-0", {DateTimeCategory.Time}, {}),
        ("2025-11-02", {DateTimeCategory.Time}, {DateTimeCategory.Date}),
        ("2025-11-02T", PURE_CATEGORIES, {}),
        ("2025-11-02t1", PURE_CATEGORIES, {}),
        ("2025-11-02T12", PURE_CATEGORIES, {}),
        ("2025-11-02T12:", PURE_CATEGORIES, {}),
        ("2025-11-02T12:3", PURE_CATEGORIES, {}),
        ("2025-11-02T12:34", PURE_CATEGORIES, {DateTimeCategory.DateTime}),
        ("2025-11-02T12:34:", PURE_CATEGORIES, {}),
        ("2025-11-02T12:34:5", PURE_CATEGORIES, {}),
        ("2025-11-02T12:34:56", PURE_CATEGORIES, {DateTimeCategory.DateTime}),
        ("2025-11-02T12:34:56.", PURE_CATEGORIES, {}),
        ("2025-11-02T12:34:56.1", PURE_CATEGORIES, {DateTimeCategory.DateTime}),
        ("2025-11-02T12:34:56.12", PURE_CATEGORIES, {DateTimeCategory.DateTime}),
        ("2025-11-02T12:34:56.123", PURE_CATEGORIES, {DateTimeCategory.DateTime}),
        ("2025-11-02T12:34:56.1234", PURE_CATEGORIES, {DateTimeCategory.DateTime}),
        ("2025-11-02T12:34:56.12345", PURE_CATEGORIES, {DateTimeCategory.DateTime}),
        ("2025-11-02T12:34:56.123456", PURE_CATEGORIES, {DateTimeCategory.DateTime}),
        ("2025-11-02T12:34:56Z", UTC_INVALID_CATEGORIES, {DateTimeCategory.DateTimeUTC}),
        ("2025-11-02t12:34:56z", UTC_INVALID_CATEGORIES, {DateTimeCategory.DateTimeUTC}),
        ("2025-11-02T12:34:56+01", OFFSET_INVALID_CATEGORIES, {}),
        ("2025-11-02T12:34:56+01:", OFFSET_INVALID_CATEGORIES, {}),
        ("2025-11-02T12:34:56+01:0", OFFSET_INVALID_CATEGORIES, {}),
        ("2025-11-02T12:34:56+01:00", OFFSET_INVALID_CATEGORIES, {DateTimeCategory.DateTimeWithTZ}),
        ("2025T12:34:56", PURE_CATEGORIES, {}),
        ("2025-T12:34:56", PURE_CATEGORIES, {}),
        ("2025-0T12:34:56", PURE_CATEGORIES, {}),
        ("2025-02T12:34:56", PURE_CATEGORIES, {}),
        ("2025-02-T12:34:56", PURE_CATEGORIES, {}),
        ("2025-02-2T12:34:56", PURE_CATEGORIES, {}),
        ("2025-02-27T12:34:56", PURE_CATEGORIES, {DateTimeCategory.DateTime}),
        ("2025-02-27T", PURE_CATEGORIES, {}),
        ("2025-02-27T:", PURE_CATEGORIES, {}),
        ("2025-02-27T::", PURE_CATEGORIES, {}),
        ("2025-02-27T::5", PURE_CATEGORIES, {}),
        ("2025-02-27T::56", PURE_CATEGORIES, {}),
        ("2025-02-27T:3:56", PURE_CATEGORIES, {}),
        ("2025-02-27T:34:56", PURE_CATEGORIES, {}),
        ("2025-02-27T1:34:56", PURE_CATEGORIES, {}),
        ("2025-02-27T12:34:56", PURE_CATEGORIES, {DateTimeCategory.DateTime}),
        # Invalid
        ("a", ALL_CATEGORIES, {}),
        ("2025-13", ALL_CATEGORIES, {}),
        ("2025-11-32", ALL_CATEGORIES, {}),
        ("25:00", ALL_CATEGORIES, {}),
        ("12:60", ALL_CATEGORIES, {}),
        ("12:34:60", ALL_CATEGORIES, {}),
        ("2024-06-3T33:33:33+00:00", ALL_CATEGORIES, {}),
    ],
)
def test_datetime_validator(text, invalid, accepted):
    if accepted:
        accepted.add(None)

    validator = DateTimeValidator(None)
    for ct in ALL_CATEGORIES:
        validator.category = ct
        if ct in invalid:
            assert (
                validator.validate(text, 0) == QValidator.State.Invalid
            ), f"Expected Invalid for category {ct} and text: {text!r}"
        elif ct in accepted:
            assert (
                validator.validate(text, 0) == QValidator.State.Acceptable
            ), f"Expected Acceptable for category {ct} and text: {text!r}"
        else:
            assert (
                validator.validate(text, 0) == QValidator.State.Intermediate
            ), f"Expected Intermediate for category {ct} and text: {text!r}"


@pytest.mark.parametrize(
    "source,pattern,accepted",
    [
        ("202*T12:34:56", "5-02-27", {"2025-02-27T12:34:56"}),  # just typing
        ("*7", "202-<5>-<02>2", {"2025-02-27"}),  # move caret
        ("1*6", "2:3:<4>5", {"12:36", "12:34:56"}),  # also move caret
        (
            "12:34:56*",
            ".(123)(456)",  # paste at once
            {"12:34:56.123", "12:34:56.123456"},
        ),
        ("2025-11-02T12:34:56*", "+01:00", {"2025-11-02T12:34:56+01:00"}),  # timezone
        (
            "2025-11-02T12:3*",
            "4:56Z",  # UTC timezone
            {"2025-11-02T12:34", "2025-11-02T12:34:56", "2025-11-02T12:34:56Z"},
        ),
        (
            "*",
            "2025-11-02T12:34:56.(123456)Z",  # full typing
            {
                "2025-11-02",
                "2025-11-02T12:34",
                "2025-11-02T12:34:56",
                "2025-11-02T12:34:56.123456",
                "2025-11-02T12:34:56.123456Z",
            },
        ),
        ("2025-1*2T12:34:56", "-0<<1", {"2025-11-02T12:34:56"}),  # insert in middle
        (
            "12:34*",
            ":56.0<<<<<<<<<<T<2025-11-02>>>>>>>>>>>+11:33",  # complex
            {
                "12:34:56",
                "12:34:56.0",
                "2025-11-02T12:34:56.0",
                "2025-11-02T12:34:56.0+11:33",
            },
        ),
    ],
)
def test_like_manual_input(source, pattern, accepted):
    """
    Extended input syntax:
      - '*': initial caret position in source text
      - plain chars: typed at caret one by one (moving caret forward)
      - '(...)': paste the whole chunk at caret as a single step (moving caret forward)
      - '<', '>': move caret left and right
    All non-final texts must be Intermediate except listed in an `accepted` set.
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
    res = None
    while i < len(pattern):
        if res == QValidator.State.Acceptable:
            accepted.discard(text)

        match pattern[(i := i + 1) - 1]:  # that is an absolute dirty hack for an inline lookahead
            case "(":
                j = pattern.index(")", i)
                insert_at(pattern[i:j])
                i = j + 1
            case "<":
                caret -= 1
                continue  # no changes are made
            case ">":
                caret += 1
                continue  # no changes are made
            case ch:
                insert_at(ch)

        res = validator.validate(text, caret)
        if text in accepted:
            assert res == QValidator.State.Acceptable, f"Expected Acceptable for: {text!r}"
        else:
            assert res == QValidator.State.Intermediate, f"Expected Intermediate for: {text!r}"

    assert text in accepted, f"Result {text!r} is missing in accepted set: {accepted!r}"
    assert len(accepted) == 1, f"Some extra strings weren't accepted: {accepted!r}"
