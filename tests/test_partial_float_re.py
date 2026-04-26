import pytest

from qmpq_spinbox import PARTIAL_FLOAT


def m(s: str) -> bool:
    return PARTIAL_FLOAT.fullmatch(s) is not None


@pytest.mark.parametrize(
    "s",
    [
        # signs and empty/dot forms
        "",
        "+",
        "-",
        ".",
        "+.",
        "-.",
        # integers
        "0",
        "-0",
        "+0",
        "123",
        "-123",
        "+123",
        "000",
        # decimals (with and without leading zero)
        "0.",
        "123.",
        "-0.",
        "+0.",
        ".0",
        ".000",
        ".123",
        "-.5",
        "+.5",
        "0.0",
        "1.23",
        "-0.000",
        "123.456",
        "000.000",
        # scientific (lowercase 'e' only)
        "1e",
        "1e+",
        "1e-",
        "1e10",
        "1e-10",
        "1e+10",
        "1.e",
        "1.e+",
        "1.e-",
        "1.e10",
        ".5e",
        ".5e+",
        ".5e-",
        ".5e10",
        "-.5e+3",
        "0e0",
        "0.e0",
        ".0e0",
        # your “trailing zeros are partial” examples: regex matches (validator will decide)
        "1.23000e+17",
        "1.0",
        "+.0",
        "-.0",
        "000.000e000",
    ],
)
def test_partial_float_matches(s):
    assert m(s)


@pytest.mark.parametrize(
    "s",
    [
        # multiple dots
        "1..2",
        "1.2.3",
        # malformed exponent payloads
        "1e1.0",
        "1.2e1.2",
        "1.2e+3.4",
        # multiple exponent signs/operators
        "1e++10",
        "1e--10",
        "1e+-10",
        "1e-+10",
        # non-decimal tokens
        "NaN",
        "Inf",
        "-Inf",
        "infinity",
        # forbidden rational notation
        "1/3",
        "1//2",
        # whitespace
        " 1",
        "1 ",
        "1 e10",
        "1e 10",
        "1e- 2",
    ],
)
def test_partial_float_rejects_invalid(s):
    assert not m(s)


# Known false POSITIVES (the regex matches these, but they’re likely undesirable)
@pytest.mark.parametrize(
    "s",
    [
        "e",
        "e10",
        "+e",
        "+e10",
        "+e-10",
        "-e10",
        ".e",
        ".e10",
        "-.e",
        "-.e10",
        # trailing sign without exponent
        "1+",
        "1-",
        # bunch of signs
        ".+",
        ".-",
        "++",
        "--",
        "-.+",
        "+.+",
        # doubled leading signs (no mantissa, only exponent)
        "++1",
        "+-1",
        "-+1",
        "--1",
    ],
)
def test_partial_float_false_positives(s):
    """Regex is too permissive: allows exponent/sign without mantissa or 'e'."""
    assert m(s)


# case are ignored
@pytest.mark.parametrize(
    "s",
    [
        "1E10",
        "1.E+10",
        ".5E-3",
        "1.0E0",
    ],
)
def test_partial_float_upper_case(s):
    assert m(s)
