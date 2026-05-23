from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Mapping

from PySide6.QtGui import QColor

from tree.types import JsonType


def _color_key(value: QColor | None) -> tuple[int, int, int, int] | None:
    if value is None:
        return None
    return value.red(), value.green(), value.blue(), value.alpha()


@dataclass(frozen=True)
class TypeStyle:
    fg: QColor | None = None
    bg: QColor | None = None
    bold: bool = False
    italic: bool = False
    icon: str | None = None

    def __hash__(self) -> int:
        return hash((_color_key(self.fg), _color_key(self.bg), self.bold, self.italic, self.icon))


@dataclass(frozen=True)
class ValidationStyle:
    """Colors used for in-tree severity badges and tints."""

    error_fg: QColor | None = None
    warning_fg: QColor | None = None
    error_badge: QColor | None = None  # drawn circle; falls back to hard-coded red
    warning_badge: QColor | None = None  # drawn circle; falls back to hard-coded amber

    def __hash__(self) -> int:
        return hash(
            (
                _color_key(self.error_fg),
                _color_key(self.warning_fg),
                _color_key(self.error_badge),
                _color_key(self.warning_badge),
            )
        )


@dataclass(frozen=True)
class Palette:
    base_fg: QColor
    base_bg: QColor
    selection_fg: QColor
    selection_bg: QColor
    accent: QColor
    affix_text: QColor | None = None
    validation: ValidationStyle = field(default_factory=ValidationStyle)

    def __hash__(self) -> int:
        return hash(
            (
                _color_key(self.base_fg),
                _color_key(self.base_bg),
                _color_key(self.selection_fg),
                _color_key(self.selection_bg),
                _color_key(self.accent),
                _color_key(self.affix_text),
                self.validation,
            )
        )


@dataclass(frozen=True)
class ThemeSpec:
    name: str
    mode: Literal["light", "dark"]
    palette: Palette
    types: Mapping[JsonType, TypeStyle]
    icon_search_paths: tuple[Path, ...]

    def __hash__(self) -> int:
        type_items = tuple((json_type, self.types[json_type]) for json_type in JsonType)
        return hash((self.name, self.mode, self.palette, type_items, self.icon_search_paths))
