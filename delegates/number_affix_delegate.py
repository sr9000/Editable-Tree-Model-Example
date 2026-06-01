from __future__ import annotations

from settings import NUMBER_AFFIX_MAX_LEN
from tree.types import JsonType
from units.number_affix import AffixKind, NumberAffix, format_number_affix, parse_number_affix

_AFFIX_TYPES = {
    JsonType.INTEGER_CURRENCY,
    JsonType.INTEGER_UNITS,
    JsonType.FLOAT_CURRENCY,
    JsonType.FLOAT_UNITS,
}


def is_affix_json_type(json_type: JsonType) -> bool:
    return json_type in _AFFIX_TYPES


def kind_for_json_type(json_type: JsonType) -> AffixKind:
    return AffixKind.CURRENCY if json_type in (JsonType.INTEGER_CURRENCY, JsonType.FLOAT_CURRENCY) else AffixKind.UNITS


def is_integer_json_type(json_type: JsonType) -> bool:
    return json_type in (JsonType.INTEGER_CURRENCY, JsonType.INTEGER_UNITS)


def normalize_affix_value(value, json_type: JsonType) -> NumberAffix | None:
    if isinstance(value, NumberAffix):
        return value
    if isinstance(value, str):
        parsed = parse_number_affix(value, max_affix_len=NUMBER_AFFIX_MAX_LEN)
        if parsed is not None:
            return parsed
    return None


def validate_affix_value(value: NumberAffix) -> NumberAffix | None:
    try:
        text = format_number_affix(value)
    except ValueError:
        return None
    return parse_number_affix(text, max_affix_len=NUMBER_AFFIX_MAX_LEN)
