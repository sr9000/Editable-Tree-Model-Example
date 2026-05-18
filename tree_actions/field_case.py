from __future__ import annotations

import re
from typing import Literal

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

_TOKEN_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z]|$)|[A-Z]?[a-z]+|\d+")


def _words(name: str) -> list[str]:
    # Normalize known separators first, then split camel/pascal/acronym runs.
    parts = [p for p in re.split(r"[-_\s]+", name.strip()) if p]
    words: list[str] = []
    for part in parts:
        for token in _TOKEN_RE.findall(part):
            words.append(token.lower())
    return words


def convert_field_name(name: str, target: FieldCase) -> str:
    words = _words(name)
    if not words:
        return name

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
        return head + "".join(w.capitalize() for w in tail)
    return "".join(w.capitalize() for w in words)
