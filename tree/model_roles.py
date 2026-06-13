from typing import Any, Final

import gmpy2
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from core.safe_mpq import safe_mpq_from_any
from mpq2py import mpq_serialization
from settings import SECRET_MASK_CHAR, SECRET_MASK_GLYPHS
from tree.types import SECRET_FAMILY, JsonType

JSON_TYPE_ROLE = Qt.ItemDataRole.UserRole + 1
VALIDATION_SEVERITY_ROLE: Final = Qt.ItemDataRole.UserRole + 2  # "error" | "warning" | None


def font_role_for_name(item, is_root_item: bool) -> QFont | None:
    if is_root_item:
        return None
    if isinstance(item.name, str) and any(ord(ch) > 127 for ch in item.name):
        font = QFont()
        font.setItalic(True)
        return font
    return None


def tooltip_role_for_value(item) -> str | None:
    if item.json_type in SECRET_FAMILY:
        return SECRET_MASK_CHAR * SECRET_MASK_GLYPHS

    raw = item.data(2)
    text = "" if raw is None else str(raw)
    if len(text) <= 80:
        return None
    return text[:4096] + ("…" if len(text) > 4096 else "")


def edit_role_value(item, column: int, is_root_item: bool) -> Any:
    if is_root_item and column == 0:
        return "<root>"
    return item.data(column)


def display_role_value(item, column: int, is_root_item: bool) -> str:
    if is_root_item and column == 0:
        return "<root>"

    data = item.data(column)
    if column == 2 and item.json_type is JsonType.PERCENT:
        q = data if isinstance(data, gmpy2.mpq) else safe_mpq_from_any(data)
        if q is not None:
            return f"{float(q * 100):g}%"

    match data:
        case bool():
            return "true" if data else "false"
        case gmpy2.mpq():
            data = mpq_serialization(data)[0]
        case None:
            return "null"

    return str(data)
