from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QSettings

from settings import APPLICATION_ID, SECRET_WORD_PREFIXES

_KEY = "secret/prefixes"


def _normalize_prefixes(prefixes: Iterable[str]) -> tuple[str, ...]:
    out: list[str] = []
    for raw in prefixes:
        if not isinstance(raw, str):
            continue
        p = raw.strip().lower()
        if not p:
            continue
        if p not in out:
            out.append(p)
    return tuple(out)


def get_secret_word_prefixes() -> tuple[str, ...]:
    settings = QSettings(APPLICATION_ID, "app")
    raw = settings.value(_KEY)
    if isinstance(raw, str):
        value = raw.strip()
        if not value:
            return SECRET_WORD_PREFIXES
        parsed = _normalize_prefixes(value.split("\n"))
        return parsed or SECRET_WORD_PREFIXES
    if isinstance(raw, (list, tuple)):
        parsed = _normalize_prefixes(raw)
        return parsed or SECRET_WORD_PREFIXES
    return SECRET_WORD_PREFIXES


def set_secret_word_prefixes(prefixes: Iterable[str]) -> tuple[str, ...]:
    normalized = _normalize_prefixes(prefixes)
    settings = QSettings(APPLICATION_ID, "app")
    settings.setValue(_KEY, list(normalized))
    return normalized
