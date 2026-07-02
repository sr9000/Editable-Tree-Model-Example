from gmpy2 import mpq

from units.number_affix import AffixKind, NumberAffix, format_number_affix, is_integer_core, parse_number_affix


def test_parse_prefix_no_space_int() -> None:
    parsed = parse_number_affix("$1234")
    assert parsed == NumberAffix(AffixKind.CURRENCY, "$", False, 1234)
    assert is_integer_core(parsed)


def test_parse_prefix_with_space_int() -> None:
    parsed = parse_number_affix("$ 1234")
    assert parsed == NumberAffix(AffixKind.CURRENCY, "$", True, 1234, 0, -1)


def test_parse_units_float_no_space() -> None:
    parsed = parse_number_affix("99.95%")
    assert parsed == NumberAffix(AffixKind.UNITS, "%", False, mpq("99.95"))
    assert not is_integer_core(parsed)


def test_parse_units_float_with_space_and_exponent() -> None:
    parsed = parse_number_affix("-3.14e2 m/s")
    assert parsed is not None
    assert parsed.kind == AffixKind.UNITS
    assert parsed.affix == "m/s"
    assert parsed.space is True
    assert parsed.number == mpq("-314")


def test_parse_negative_currency_without_space_rejected() -> None:
    # "abc-1" should be rejected as currency, requires "abc -1"
    assert parse_number_affix("abc-1") is None
    assert parse_number_affix("abc -1") is not None


def test_parse_currency_affix_ending_with_dash_for_zero_padded_int() -> None:
    parsed = parse_number_affix("abc-001")
    assert parsed == NumberAffix(AffixKind.CURRENCY, "abc-", False, 1, 3, -1)
    assert format_number_affix(parsed) == "abc-001"


def test_rejected_examples() -> None:
    for s in ("$1234 USD", "1234", "", " 1234", "$\t1234", "$  1234", "$-1"):
        assert parse_number_affix(s) is None


def test_affix_max_len() -> None:
    assert parse_number_affix("1 abcdefghijklmnopq", max_affix_len=16) is None
    assert parse_number_affix("1 abcdefghijklmnop", max_affix_len=16) is not None


def test_round_trip_samples() -> None:
    samples = (
        "$1234",
        "$ 1234",
        "99.95%",
        "-314 m/s",
        "0.5kg",
        "12 V",
        "xyz 001",
        "abc-001",
        "000123.456000%",
        "$ 0.001",
        "abc -1",
    )
    for s in samples:
        parsed = parse_number_affix(s)
        assert parsed is not None
        assert format_number_affix(parsed) == s
