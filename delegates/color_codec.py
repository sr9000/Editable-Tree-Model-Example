"""Helpers for parsing / formatting HTML hex color strings.

We deliberately avoid Qt's ``QColor.name(HexArgb)`` because that returns
``#AARRGGBB`` while HTML / CSS use ``#RRGGBBAA``. All canonical strings
produced here use lowercase hex with a leading ``#``.
"""

from __future__ import annotations

from PySide6.QtGui import QColor

from tree.types import JsonType, looks_like_color_rgb, looks_like_color_rgba


def _expand_short(hex_part: str) -> str:
    """``abc`` -> ``aabbcc``; ``abcd`` -> ``aabbccdd``; longer left untouched."""
    if len(hex_part) in (3, 4):
        return "".join(ch * 2 for ch in hex_part)
    return hex_part


def parse_color(value: str) -> QColor | None:
    """Return a QColor for an HTML hex string, or None if not parseable."""
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s.startswith("#"):
        return None
    hex_part = _expand_short(s[1:])
    if len(hex_part) == 6:
        try:
            r = int(hex_part[0:2], 16)
            g = int(hex_part[2:4], 16)
            b = int(hex_part[4:6], 16)
        except ValueError:
            return None
        c = QColor(r, g, b, 255)
        return c if c.isValid() else None
    if len(hex_part) == 8:
        try:
            r = int(hex_part[0:2], 16)
            g = int(hex_part[2:4], 16)
            b = int(hex_part[4:6], 16)
            a = int(hex_part[6:8], 16)
        except ValueError:
            return None
        c = QColor(r, g, b, a)
        return c if c.isValid() else None
    return None


def color_to_html(color: QColor, json_type: JsonType) -> str:
    """Render *color* as ``#rrggbb`` or ``#rrggbbaa`` per *json_type*."""
    r, g, b, a = color.red(), color.green(), color.blue(), color.alpha()
    if json_type is JsonType.COLOR_RGBA:
        return f"#{r:02x}{g:02x}{b:02x}{a:02x}"
    return f"#{r:02x}{g:02x}{b:02x}"


def normalize_color_string(value: str, json_type: JsonType) -> str | None:
    """Normalize *value* (any short/long hex form) to the canonical form for *json_type*.

    Returns ``None`` when *value* is not a recognizable color string.
    """
    color = parse_color(value)
    if color is None:
        return None
    return color_to_html(color, json_type)


def is_color_text(value: str, json_type: JsonType) -> bool:
    if json_type is JsonType.COLOR_RGB:
        return looks_like_color_rgb(value)
    if json_type is JsonType.COLOR_RGBA:
        return looks_like_color_rgba(value)
    return False
