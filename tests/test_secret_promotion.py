from tree.item import JsonTreeItem
from tree.types import JsonType


def _object_with_child(name: str, value: str) -> JsonTreeItem:
    root = JsonTreeItem(value={name: value})
    return root.child(0)


def test_rename_string_comment_to_password_promotes_secret_line() -> None:
    child = _object_with_child("comment", "plainsecret")

    assert child.json_type is JsonType.STRING
    assert child.set_data(0, "password")
    assert child.json_type is JsonType.SECRET_LINE


def test_rename_string_comment_to_private_key_with_pem_promotes_secret_text() -> None:
    pem = "-----BEGIN KEY-----\nabc\n-----END KEY-----"
    child = _object_with_child("comment", pem)

    assert child.set_data(0, "private_key")
    assert child.json_type is JsonType.SECRET_TEXT


def test_rename_secret_line_to_comment_stays_sticky_secret_line() -> None:
    child = _object_with_child("comment", "plainsecret")
    assert child.set_data(0, "password")
    assert child.json_type is JsonType.SECRET_LINE

    assert child.set_data(0, "comment")
    assert child.json_type is JsonType.SECRET_LINE


def test_creating_new_api_key_field_without_value_promotes_secret_line() -> None:
    obj = JsonTreeItem(value={})

    assert obj.insert_children(0, 1, 3)
    child = obj.child(0)
    assert child is not None

    assert child.set_data(0, "api_key")
    assert child.json_type is JsonType.SECRET_LINE


def test_pasting_multiline_value_into_secret_line_upgrades_to_secret_text() -> None:
    child = _object_with_child("comment", "plainsecret")
    assert child.set_data(0, "password")
    assert child.json_type is JsonType.SECRET_LINE

    assert child.set_data(2, "line1\nline2")
    assert child.json_type is JsonType.SECRET_TEXT


def test_removing_newlines_from_secret_text_stays_secret_text() -> None:
    child = _object_with_child("comment", "line1\nline2")
    assert child.set_data(0, "private_key")
    assert child.json_type is JsonType.SECRET_TEXT

    assert child.set_data(2, "single-line")
    assert child.json_type is JsonType.SECRET_TEXT
