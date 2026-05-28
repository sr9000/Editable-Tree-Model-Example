from __future__ import annotations

import gmpy2

from tree.item import JsonTreeItem
from tree.types import JsonType
from units.number_affix import NumberAffix

_INTEGER_TYPES = frozenset({JsonType.INTEGER, JsonType.INTEGER_CURRENCY, JsonType.INTEGER_UNITS})
_FLOAT_TYPES = frozenset({JsonType.FLOAT, JsonType.PERCENT, JsonType.FLOAT_CURRENCY, JsonType.FLOAT_UNITS})


def is_integer_number_type(json_type: JsonType) -> bool:
    return json_type in _INTEGER_TYPES


def is_float_number_type(json_type: JsonType) -> bool:
    return json_type in _FLOAT_TYPES


def would_drop_fraction_on_type_change(item: JsonTreeItem, target_type: JsonType) -> bool:
    """True when changing *item*'s type to *target_type* discards a fractional part."""
    if not is_integer_number_type(target_type) or not is_float_number_type(item.json_type):
        return False
    source_value = item.value.number if isinstance(item.value, NumberAffix) else item.value
    try:
        q = gmpy2.mpq(str(source_value))
    except (TypeError, ValueError):
        return False
    return q.denominator != 1
