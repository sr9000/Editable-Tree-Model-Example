from __future__ import annotations

from types import MappingProxyType
from typing import Literal

from PySide6.QtGui import QColor

from themes.spec import Palette, ThemeSpec, TypeStyle, ValidationStyle
from tree.types import PSEUDO_TEXT_PARENT, JsonType


def _c(value: str) -> QColor:
    color = QColor(value)
    if not color.isValid():
        raise ValueError(f"Invalid default color: {value}")
    return color


def _inherit_pseudo_text_styles(styles: dict[JsonType, TypeStyle]) -> dict[JsonType, TypeStyle]:
    """Backfill each pseudo text type with a *copy* of its canonical parent's style.

    Each pseudo (EMPTY_*, WS_*) reuses its parent's fg/bg/bold/italic/icon so
    themes do not need to declare anything extra. A copy is used (not the
    same object) to leave the door open for theme overrides per pseudo later.
    """
    for pseudo, parent in PSEUDO_TEXT_PARENT.items():
        if pseudo in styles:
            continue
        base = styles[parent]
        styles[pseudo] = TypeStyle(
            fg=QColor(base.fg) if base.fg is not None else None,
            bg=QColor(base.bg) if base.bg is not None else None,
            bold=base.bold,
            italic=base.italic,
            icon=base.icon,
        )
    return styles


def _theme(
    name: str,
    mode: Literal["light", "dark"],
    palette: Palette,
    styles: dict[JsonType, TypeStyle],
) -> ThemeSpec:
    return ThemeSpec(
        name=name,
        mode=mode,
        palette=palette,
        types=MappingProxyType(dict(styles)),
        icon_search_paths=(),
    )


_LIGHT_TYPES: dict[JsonType, TypeStyle] = {
    JsonType.INTEGER: TypeStyle(fg=_c("#268bd2")),
    JsonType.FLOAT: TypeStyle(fg=_c("#1f8f89")),
    JsonType.PERCENT: TypeStyle(fg=_c("#1f8f89"), italic=True),
    JsonType.INTEGER_CURRENCY: TypeStyle(fg=_c("#268bd2"), italic=True),
    JsonType.INTEGER_UNITS: TypeStyle(fg=_c("#268bd2"), italic=True),
    JsonType.FLOAT_CURRENCY: TypeStyle(fg=_c("#1f8f89"), italic=True),
    JsonType.FLOAT_UNITS: TypeStyle(fg=_c("#1f8f89"), italic=True),
    JsonType.BOOLEAN: TypeStyle(fg=_c("#d33682")),
    JsonType.STRING: TypeStyle(fg=_c("#657b83")),
    JsonType.UNICODE: TypeStyle(fg=_c("#6f8100")),
    JsonType.MULTILINE: TypeStyle(fg=_c("#6f8100"), italic=True),
    JsonType.TEXT: TypeStyle(fg=_c("#6f8100"), italic=True),
    JsonType.SECRET_LINE: TypeStyle(fg=_c("#cb4b16")),
    JsonType.SECRET_TEXT: TypeStyle(fg=_c("#cb4b16"), italic=True),
    JsonType.DATE: TypeStyle(fg=_c("#946f00")),
    JsonType.TIME: TypeStyle(fg=_c("#946f00")),
    JsonType.DATETIME: TypeStyle(fg=_c("#946f00")),
    JsonType.DATETIMEUTC: TypeStyle(fg=_c("#946f00")),
    JsonType.DATETIMEZONE: TypeStyle(fg=_c("#946f00")),
    JsonType.BYTES: TypeStyle(fg=_c("#cb4b16")),
    JsonType.ZLIB: TypeStyle(fg=_c("#cb4b16"), italic=True),
    JsonType.GZIP: TypeStyle(fg=_c("#cb4b16"), italic=True),
    JsonType.COLOR_RGB: TypeStyle(fg=_c("#6c71c4")),
    JsonType.COLOR_RGBA: TypeStyle(fg=_c("#6c71c4"), italic=True),
    JsonType.NULL: TypeStyle(fg=_c("#7f8c8d"), italic=True),
    JsonType.OBJECT: TypeStyle(fg=_c("#073642"), bold=True),
    JsonType.ARRAY: TypeStyle(fg=_c("#073642"), bold=True),
}

_DARK_TYPES: dict[JsonType, TypeStyle] = {
    JsonType.INTEGER: TypeStyle(fg=_c("#7aa2f7")),
    JsonType.FLOAT: TypeStyle(fg=_c("#73daca")),
    JsonType.PERCENT: TypeStyle(fg=_c("#73daca"), italic=True),
    JsonType.INTEGER_CURRENCY: TypeStyle(fg=_c("#7aa2f7"), italic=True),
    JsonType.INTEGER_UNITS: TypeStyle(fg=_c("#7aa2f7"), italic=True),
    JsonType.FLOAT_CURRENCY: TypeStyle(fg=_c("#73daca"), italic=True),
    JsonType.FLOAT_UNITS: TypeStyle(fg=_c("#73daca"), italic=True),
    JsonType.BOOLEAN: TypeStyle(fg=_c("#f7768e")),
    JsonType.STRING: TypeStyle(fg=_c("#c0caf5")),
    JsonType.UNICODE: TypeStyle(fg=_c("#9ece6a")),
    JsonType.MULTILINE: TypeStyle(fg=_c("#9ece6a"), italic=True),
    JsonType.TEXT: TypeStyle(fg=_c("#9ece6a"), italic=True),
    JsonType.SECRET_LINE: TypeStyle(fg=_c("#ff9e64")),
    JsonType.SECRET_TEXT: TypeStyle(fg=_c("#ff9e64"), italic=True),
    JsonType.DATE: TypeStyle(fg=_c("#e0af68")),
    JsonType.TIME: TypeStyle(fg=_c("#e0af68")),
    JsonType.DATETIME: TypeStyle(fg=_c("#e0af68")),
    JsonType.DATETIMEUTC: TypeStyle(fg=_c("#e0af68")),
    JsonType.DATETIMEZONE: TypeStyle(fg=_c("#e0af68")),
    JsonType.BYTES: TypeStyle(fg=_c("#ff9e64")),
    JsonType.ZLIB: TypeStyle(fg=_c("#ff9e64"), italic=True),
    JsonType.GZIP: TypeStyle(fg=_c("#ff9e64"), italic=True),
    JsonType.COLOR_RGB: TypeStyle(fg=_c("#bb9af7")),
    JsonType.COLOR_RGBA: TypeStyle(fg=_c("#bb9af7"), italic=True),
    JsonType.NULL: TypeStyle(fg=_c("#6b739f"), italic=True),
    JsonType.OBJECT: TypeStyle(fg=_c("#7dcfff"), bold=True),
    JsonType.ARRAY: TypeStyle(fg=_c("#7dcfff"), bold=True),
}


_inherit_pseudo_text_styles(_LIGHT_TYPES)
_inherit_pseudo_text_styles(_DARK_TYPES)


LIGHT_DEFAULT = _theme(
    name="Default Light",
    mode="light",
    palette=Palette(
        base_fg=_c("#22242a"),
        base_bg=_c("#fdf6e3"),
        alternate_bg=_c("#f4ecd6"),
        selection_fg=_c("#fdf6e3"),
        selection_bg=_c("#268bd2"),
        accent=_c("#b58900"),
        affix_text=_c("#7f8c8d"),
        validation=ValidationStyle(
            error_fg=_c("#d13438"),
            warning_fg=_c("#bf6900"),
            error_badge=_c("#d13438"),
            warning_badge=_c("#bf6900"),
        ),
    ),
    styles=_LIGHT_TYPES,
)

DARK_DEFAULT = _theme(
    name="Default Dark",
    mode="dark",
    palette=Palette(
        base_fg=_c("#c0caf5"),
        base_bg=_c("#1a1b26"),
        alternate_bg=_c("#22283a"),
        selection_fg=_c("#1a1b26"),
        selection_bg=_c("#7aa2f7"),
        accent=_c("#e0af68"),
        affix_text=_c("#6b739f"),
        validation=ValidationStyle(
            error_fg=_c("#ff6b6b"),
            warning_fg=_c("#ffb84d"),
            error_badge=_c("#ff6b6b"),
            warning_badge=_c("#ffb84d"),
        ),
    ),
    styles=_DARK_TYPES,
)
