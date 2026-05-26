from __future__ import annotations

from typing import Literal, cast

FieldCase = Literal[
    "snake_case",
    "SNAKE_CASE_UPPER",
    "kebab-case",
    "KEBAB-CASE-UPPER",
    "camelCase",
    "PascalCase",
]

FIELD_CASE_ORDER: tuple[FieldCase, ...] = (
    "snake_case",
    "SNAKE_CASE_UPPER",
    "kebab-case",
    "KEBAB-CASE-UPPER",
    "camelCase",
    "PascalCase",
)

FIELD_CASE_LABELS: dict[FieldCase, str] = {
    "snake_case": "snake_case",
    "SNAKE_CASE_UPPER": "SNAKE_CASE_UPPER",
    "kebab-case": "kebab-case",
    "KEBAB-CASE-UPPER": "KEBAB-CASE-UPPER",
    "camelCase": "camelCase",
    "PascalCase": "PascalCase",
}

_STANDARD_SEPARATORS = frozenset({"_", "-"})


def _is_hard_separator(char: str) -> bool:
    return not char.isalpha() and not char.isdigit() and char not in _STANDARD_SEPARATORS


def _split_standard_parts(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    for char in text:
        if char in _STANDARD_SEPARATORS:
            if current:
                parts.append("".join(current))
                current.clear()
            continue
        current.append(char)
    if current:
        parts.append("".join(current))
    return parts


def _split_cased_word(part: str) -> list[str]:
    if not part:
        return []

    words: list[str] = []
    start = 0
    for index in range(1, len(part)):
        prev = part[index - 1]
        char = part[index]
        next_char = part[index + 1] if index + 1 < len(part) else ""
        if not char.isalpha() or not char.isupper():
            continue
        if prev.isalpha() and prev.islower():
            words.append(part[start:index])
            start = index
            continue
        if prev.isdigit() and any(ch.isalpha() for ch in part[start:index]):
            words.append(part[start:index])
            start = index
            continue
        if prev.isalpha() and prev.isupper() and next_char.isalpha() and next_char.islower():
            words.append(part[start:index])
            start = index
    words.append(part[start:])
    return words


def _segment_words(text: str) -> list[str]:
    words: list[str] = []
    for part in _split_standard_parts(text):
        for word in _split_cased_word(part):
            if word:
                words.append(word.lower())
    return words


def _tokenize(name: str) -> list[tuple[str, str | list[str]]]:
    tokens: list[tuple[str, str | list[str]]] = []
    segment_chars: list[str] = []
    separator_chars: list[str] = []

    def flush_segment() -> None:
        nonlocal segment_chars
        if not segment_chars:
            return
        words = _segment_words("".join(segment_chars))
        if words:
            tokens.append(("segment", words))
        segment_chars = []

    def flush_separator() -> None:
        nonlocal separator_chars
        if not separator_chars:
            return
        tokens.append(("separator", "".join(separator_chars)))
        separator_chars = []

    for char in name.strip():
        if _is_hard_separator(char):
            flush_segment()
            separator_chars.append(char)
            continue
        flush_separator()
        segment_chars.append(char)

    flush_segment()
    flush_separator()
    return tokens


def _render_segment(words: list[str], target: FieldCase) -> str:
    if target == "snake_case":
        return "_".join(words)
    if target == "SNAKE_CASE_UPPER":
        return "_".join(words).upper()
    if target == "kebab-case":
        return "-".join(words)
    if target == "KEBAB-CASE-UPPER":
        return "-".join(words).upper()
    if target == "camelCase":
        head, *tail = words
        return head + "".join(word.capitalize() for word in tail)
    return "".join(word.capitalize() for word in words)


def convert_field_name(name: str, target: FieldCase) -> str:
    tokens = _tokenize(name)
    if not any(kind == "segment" for kind, _ in tokens):
        return name

    converted: list[str] = []
    for kind, value in tokens:
        if kind == "separator":
            converted.append(cast(str, value))
            continue
        converted.append(_render_segment(cast(list[str], value), target))
    return "".join(converted)
