from gmpy2 import mpq

from core.raw_numeric import (
    REASON_INVALID_FORMAT,
    REASON_NON_FINITE,
    REASON_OVERFLOW,
    REASON_PRECISION_LIMIT,
    REASON_UNDERFLOW,
)
from core.safe_mpq import mpq_literal_is_safe, parse_mpq, safe_decimal_from_text, safe_mpq_from_text


def test_safe_mpq_accepts_regular_decimal_and_rational_literals() -> None:
    assert safe_mpq_from_text("3.14") == mpq("3.14")
    assert safe_mpq_from_text("10/4") == mpq("5/2")
    assert safe_mpq_from_text("1e309") == mpq("1e309")


def test_safe_mpq_rejects_underflow_and_overflow_exponents() -> None:
    assert safe_mpq_from_text("31e-327018450730") is None
    assert safe_mpq_from_text("1e327018450730") is None


def test_safe_mpq_rejects_too_many_significant_digits_but_allows_trailing_zeros() -> None:
    assert safe_mpq_from_text("9" * 4300) == mpq("9" * 4300)
    assert safe_mpq_from_text("9" * 4301) is None
    assert safe_mpq_from_text("1." + "0" * 5000) == mpq(1)


def test_safe_mpq_rational_requires_integer_sides_and_nonzero_denominator() -> None:
    assert safe_mpq_from_text("1.5/2") is None
    assert safe_mpq_from_text("1/0") is None
    assert safe_mpq_from_text("1/2/3") is None


def test_safe_decimal_and_literal_is_safe_helpers() -> None:
    assert safe_decimal_from_text("3.14") is not None
    assert safe_decimal_from_text("not-a-number") is None
    assert safe_decimal_from_text("nan") is None
    assert mpq_literal_is_safe("7/3")
    assert not mpq_literal_is_safe("31e-327018450730")


def test_parse_mpq_reports_success_and_value() -> None:
    result = parse_mpq("3.14")
    assert result.ok is True
    assert result.value == mpq("3.14")
    assert result.reason is None


def test_parse_mpq_reports_overflow_reason() -> None:
    result = parse_mpq("1e327018450730")
    assert result.value is None
    assert result.reason == REASON_OVERFLOW


def test_parse_mpq_reports_underflow_reason() -> None:
    result = parse_mpq("31e-327018450730")
    assert result.value is None
    assert result.reason == REASON_UNDERFLOW


def test_parse_mpq_reports_non_finite_reason() -> None:
    for literal in (".inf", "-.inf", ".nan", "inf", "nan", "Infinity"):
        result = parse_mpq(literal)
        assert result.value is None
        assert result.reason == REASON_NON_FINITE


def test_parse_mpq_reports_precision_limit_reason() -> None:
    result = parse_mpq("9" * 4301)
    assert result.value is None
    assert result.reason == REASON_PRECISION_LIMIT


def test_parse_mpq_reports_invalid_format_reason() -> None:
    for literal in ("not-a-number", "", "1/0", "1.5/2"):
        result = parse_mpq(literal)
        assert result.value is None
        assert result.reason == REASON_INVALID_FORMAT
