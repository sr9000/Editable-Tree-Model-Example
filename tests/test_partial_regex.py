import pytest

from core.datetime_parsing.regex import PARTIAL_DATETIME_RE


@pytest.mark.parametrize(
    "text, expected",
    [
        # Year only
        ("2", {"year": "2"}),
        ("20", {"year": "20"}),
        ("202", {"year": "202"}),
        ("2025", {"year": "2025"}),
        # Year with separator but no month/day yet
        ("2025-", {"year": "2025", "month": ""}),
        ("2025-1", {"year": "2025", "month": "1"}),
        ("2025-11", {"year": "2025", "month": "11"}),
        ("2025-11-", {"year": "2025", "month": "11", "day": ""}),
        ("2025-11-0", {"year": "2025", "month": "11", "day": "0"}),
        # Time only
        ("12:", {"hour": "12", "minute": ""}),
        ("12:3", {"hour": "12", "minute": "3"}),
        ("12:34", {"hour": "12", "minute": "34"}),
        ("12:34:", {"hour": "12", "minute": "34", "second": ""}),
        ("12:34:5", {"hour": "12", "minute": "34", "second": "5"}),
        ("12:34:56", {"hour": "12", "minute": "34", "second": "56"}),
        (
            "12:34:56.",
            {"hour": "12", "minute": "34", "second": "56", "microsecond": ""},
        ),
        (
            "12:34:56.1",
            {"hour": "12", "minute": "34", "second": "56", "microsecond": "1"},
        ),
        # Date and time
        (
            "2025-11-02 12:34",
            {"year": "2025", "month": "11", "day": "02", "hour": "12", "minute": "34"},
        ),
        (
            "2025-11-02T12:34:56",
            {
                "year": "2025",
                "month": "11",
                "day": "02",
                "hour": "12",
                "minute": "34",
                "second": "56",
            },
        ),
        # Timezone partials
        (
            "2025-11-02T12:34+",
            {
                "year": "2025",
                "month": "11",
                "day": "02",
                "hour": "12",
                "minute": "34",
                "tz_sign": "+",
            },
        ),
        (
            "2025-11-02T12:34+0",
            {
                "year": "2025",
                "month": "11",
                "day": "02",
                "hour": "12",
                "minute": "34",
                "tz_sign": "+",
                "tz_hour": "0",
            },
        ),
        (
            "2025-11-02T12:34+01",
            {
                "year": "2025",
                "month": "11",
                "day": "02",
                "hour": "12",
                "minute": "34",
                "tz_sign": "+",
                "tz_hour": "01",
            },
        ),
        (
            "2025-11-02T12:34+01:",
            {
                "year": "2025",
                "month": "11",
                "day": "02",
                "hour": "12",
                "minute": "34",
                "tz_sign": "+",
                "tz_hour": "01",
                "tz_minute": "",
            },
        ),
        (
            "2025-11-02T12:34+01:0",
            {
                "year": "2025",
                "month": "11",
                "day": "02",
                "hour": "12",
                "minute": "34",
                "tz_sign": "+",
                "tz_hour": "01",
                "tz_minute": "0",
            },
        ),
        (
            "2025-11-02T12:34Z",
            {
                "year": "2025",
                "month": "11",
                "day": "02",
                "hour": "12",
                "minute": "34",
                "utc": "Z",
            },
        ),
        # Critical case: time-only '25:00' must be hour/minute, not year/minute
        ("25:00", {"hour": "25", "minute": "00"}),
        # Edge cases
        ("--T::.+:", {}),  # all empty groups
        ("2025--T::.+:", {"year": "2025"}),  # year only
        ("-12-T::.+:", {"month": "12"}),  # month only
        ("--22T::.+:", {"day": "22"}),  # day only
        ("--T09::.+:", {"hour": "09"}),  # hour only
        ("--T:08:.+:", {"minute": "08"}),  # minute only
        ("--T::07.+:", {"second": "07"}),  # second only
        ("--T::.123456+:", {"microsecond": "123456"}),  # micro only
        ("--T::.+10:", {"tz_hour": "10"}),  # tz_hour only
        ("--T::.+:20", {"tz_minute": "20"}),  # tz_minute only
    ],
)
def test_partial_regex_groups(text, expected):
    m = PARTIAL_DATETIME_RE.fullmatch(text)
    if expected is None:
        assert m is None
        return
    assert m is not None, f"Expected a match for '{text}'"
    gd = {k: v for k, v in m.groupdict().items() if v is not None}
    for k, v in expected.items():
        assert gd.get(k) == v, f"For '{text}', expected {k}={v!r} but got {gd.get(k)!r}"


@pytest.mark.parametrize(
    "text",
    [
        # Clearly invalid partials that should not match the structure
        ":::",  # triple colons
        "2025TT",  # double separator
    ],
)
def test_partial_regex_no_match(text):
    assert PARTIAL_DATETIME_RE.fullmatch(text) is None
