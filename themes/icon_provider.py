from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

from PySide6.QtGui import QIcon

from themes.spec import ThemeSpec
from tree.types import JsonType

LOGGER = logging.getLogger(__name__)


class IconProvider(Protocol):
    def for_type(self, t: JsonType) -> QIcon: ...

    def for_key(self, key: str) -> QIcon: ...

    def reload(self) -> None: ...


class StubIconProvider:
    """Returns empty icons for all types until icon assets are shipped."""

    def for_type(self, t: JsonType) -> QIcon:
        return QIcon()

    def for_key(self, key: str) -> QIcon:
        return QIcon()

    def reload(self) -> None:
        return None


class FileIconProvider:
    """Resolves logical icon keys from theme type styles against configured search paths."""

    _EXTENSIONS: tuple[str, ...] = (".svg", ".png", ".ico")

    def __init__(self, theme: ThemeSpec) -> None:
        self._theme = theme
        self._cache: dict[JsonType, QIcon] = {}
        self._key_cache: dict[str, QIcon] = {}
        self._warned_missing: set[JsonType] = set()
        self._warned_missing_key: set[str] = set()
        self._logical_keys: dict[str, str] = {
            "affix_prefix": "bank_line",
            "affix_suffix": "ruler_line",
        }

    def for_type(self, t: JsonType) -> QIcon:
        cached = self._cache.get(t)
        if cached is not None:
            return cached

        style = self._theme.types[t]
        key = style.icon
        if key is None:
            icon = QIcon()
            self._cache[t] = icon
            return icon

        path = self._resolve(key)
        if path is None:
            if t not in self._warned_missing:
                LOGGER.warning("Missing icon asset for %s (key=%r)", t.value, key)
                self._warned_missing.add(t)
            icon = QIcon()
            self._cache[t] = icon
            return icon

        icon = QIcon(str(path))
        self._cache[t] = icon
        return icon

    def for_key(self, key: str) -> QIcon:
        cached = self._key_cache.get(key)
        if cached is not None:
            return cached
        icon_key = self._logical_keys.get(key)
        if not icon_key:
            icon = QIcon()
            self._key_cache[key] = icon
            return icon
        path = self._resolve(icon_key)
        if path is None:
            if key not in self._warned_missing_key:
                LOGGER.warning("Missing icon asset for key=%r (icon=%r)", key, icon_key)
                self._warned_missing_key.add(key)
            icon = QIcon()
            self._key_cache[key] = icon
            return icon
        icon = QIcon(str(path))
        self._key_cache[key] = icon
        return icon

    def reload(self) -> None:
        self._cache.clear()
        self._key_cache.clear()

    def _resolve(self, key: str) -> Path | None:
        for base in self._theme.icon_search_paths:
            for ext in self._EXTENSIONS:
                candidate = base / f"{key}{ext}"
                if candidate.exists() and candidate.is_file():
                    return candidate
        return None
