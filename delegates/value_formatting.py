from gmpy2 import mpq
from PySide6.QtGui import QBrush, QPalette
from PySide6.QtWidgets import QStyleOptionViewItem

from delegates.bytes_codec import decode_bytes
from mpq2py import mpq_serialization
from themes.spec import TypeStyle
from tree.types import JsonType
from units import format_bytes

_PREVIEW_LIMIT = 80
_PREVIEW_CHILDREN = 5
_MULTILINE_SEPARATOR = " | "


def format_default(value, *, max_text_len: int | None = 80) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, mpq):
        return str(mpq_serialization(value)[0])
    if isinstance(value, bytes):
        return f"<{format_bytes(len(value))}>"
    if isinstance(value, str) and max_text_len is not None and len(value) > max_text_len:
        return value[:max_text_len] + "…"
    return str(value)


def _elide(text: str, limit: int = _PREVIEW_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _container_meta(json_type: JsonType, count: int) -> str:
    if json_type is JsonType.ARRAY:
        noun = "item" if count == 1 else "items"
        return f"[{count} {noun}]"
    noun = "key" if count == 1 else "keys"
    return f"{{{count} {noun}}}"


def _container_child_preview(child) -> str:
    if child.json_type is JsonType.ARRAY:
        return "[...]"
    if child.json_type is JsonType.OBJECT:
        return "{...}"
    value = child.value
    if isinstance(value, str):
        value = value.replace("\r\n", "\n").replace("\r", "\n").replace("\n", _MULTILINE_SEPARATOR)
    return format_default(value, max_text_len=None)


def _format_container_preview(item, json_type: JsonType, *, show_preview: bool) -> str:
    count = item.child_count()
    header = _container_meta(json_type, count)
    if count == 0 or not show_preview:
        return header

    children = item.child_items[:_PREVIEW_CHILDREN]
    if json_type is JsonType.ARRAY:
        preview = ", ".join(_container_child_preview(child) for child in children)
    else:
        preview = ", ".join(
            f"{child.name if child.name is not None else '<no name>'}: {_container_child_preview(child)}"
            for child in children
        )

    if not preview:
        return header
    return _elide(f"{header}  {preview}")


def format_with_type(value, json_type: JsonType | None, *, item=None, show_preview: bool = True) -> str:
    if item is not None and json_type in (JsonType.ARRAY, JsonType.OBJECT):
        return _format_container_preview(item, json_type, show_preview=show_preview)

    if json_type is JsonType.PERCENT:
        try:
            q = value if isinstance(value, mpq) else mpq(str(value))
            return f"{float(q * 100):g}%"
        except (TypeError, ValueError):
            return format_default(value)

    if json_type in (JsonType.BYTES, JsonType.ZLIB, JsonType.GZIP):
        try:
            raw = decode_bytes(value, json_type) if isinstance(value, str) else bytes(value)
            return f"<{format_bytes(len(raw))}>"
        except Exception:
            return format_default(value)

    return format_default(value)


def _apply_type_style(
    option: QStyleOptionViewItem,
    style: TypeStyle,
    *,
    selected: bool,
    allow_background: bool,
) -> None:
    font = option.font
    font.setBold(style.bold)
    font.setItalic(style.italic)
    option.font = font

    if selected:
        return

    if style.fg is not None:
        option.palette.setColor(QPalette.ColorRole.Text, style.fg)
        option.palette.setColor(QPalette.ColorRole.WindowText, style.fg)

    if allow_background and style.bg is not None:
        option.backgroundBrush = QBrush(style.bg)
