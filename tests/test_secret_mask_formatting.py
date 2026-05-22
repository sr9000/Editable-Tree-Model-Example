from delegates.value_formatting import format_with_type
from settings import SECRET_MASK_CHAR, SECRET_MASK_GLYPHS
from tree.item import JsonTreeItem
from tree.model_roles import tooltip_role_for_value
from tree.types import JsonType


MASK = SECRET_MASK_CHAR * SECRET_MASK_GLYPHS


def test_secret_line_displays_fixed_mask() -> None:
    assert format_with_type("hunter2", JsonType.SECRET_LINE) == MASK


def test_secret_text_displays_fixed_mask() -> None:
    assert format_with_type("line1\nline2", JsonType.SECRET_TEXT) == MASK


def test_secret_empty_string_still_displays_mask() -> None:
    assert format_with_type("", JsonType.SECRET_LINE) == MASK


def test_secret_tooltip_uses_same_mask_without_leaking_value() -> None:
    item = JsonTreeItem(value={"password": "plainsecret"}).child(0)
    assert item.set_data(0, "password")
    assert item.json_type is JsonType.SECRET_LINE

    assert tooltip_role_for_value(item) == MASK
