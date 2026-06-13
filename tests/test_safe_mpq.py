from gmpy2 import mpq

from core.safe_mpq import mpq_literal_is_safe, safe_decimal_from_text, safe_mpq_from_text


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
