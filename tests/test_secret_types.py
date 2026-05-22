from tree.types import SECRET_FAMILY, TEXT_FAMILY, JsonType


def test_secret_types_are_exported() -> None:
    assert JsonType.SECRET_LINE.value == "secret_line"
    assert JsonType.SECRET_TEXT.value == "secret_text"


def test_secret_family_contains_both_secret_types() -> None:
    assert SECRET_FAMILY == frozenset({JsonType.SECRET_LINE, JsonType.SECRET_TEXT})


def test_text_family_does_not_include_secret_types() -> None:
    assert JsonType.SECRET_LINE not in TEXT_FAMILY
    assert JsonType.SECRET_TEXT not in TEXT_FAMILY
