from typing import Any

from enums import JsonType


def unique_child_name(child_items, base: str = "new_key", used_names: set[str] | None = None) -> str:
    used = {child.name for child in child_items if isinstance(child.name, str)}
    if used_names is not None:
        used |= used_names

    if base not in used:
        return base

    i = 2
    while f"{base}_{i}" in used:
        i += 1
    return f"{base}_{i}"


def validated_child_name(parent_item, current_item, value: Any) -> str | None:
    if parent_item is None:
        return None
    if parent_item.json_type is JsonType.ARRAY:
        return None
    if not isinstance(value, str):
        return None

    candidate = value.strip()
    if not candidate:
        return None

    if parent_item.json_type is JsonType.OBJECT:
        siblings = {
            child.name for child in parent_item.child_items if child is not current_item and isinstance(child.name, str)
        }
        if candidate in siblings:
            return None

    return candidate
