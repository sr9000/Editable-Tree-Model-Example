from gmpy2 import mpq

from delegates.formatting.value_formatting import format_with_type
from tree.types import JsonType
from units.number_affix import AffixKind, NumberAffix, format_number_affix


def test_affix_types_render_via_number_affix_formatter() -> None:
    samples = [
        (JsonType.INTEGER_CURRENCY, NumberAffix(AffixKind.CURRENCY, "$", False, 1234)),
        (JsonType.INTEGER_UNITS, NumberAffix(AffixKind.UNITS, "%", True, 12)),
        (JsonType.FLOAT_CURRENCY, NumberAffix(AffixKind.CURRENCY, "$", True, mpq("7/2"))),
        (JsonType.FLOAT_UNITS, NumberAffix(AffixKind.UNITS, "rad", False, mpq("157/50"))),
    ]
    for json_type, value in samples:
        assert format_with_type(value, json_type) == format_number_affix(value)


def test_empty_affix_transitional_value_renders_without_raising() -> None:
    value = NumberAffix(AffixKind.CURRENCY, "", False, 1234)

    assert format_with_type(value, JsonType.INTEGER_CURRENCY) == "1234"
