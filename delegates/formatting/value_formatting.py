from datetime import datetime, timezone

from gmpy2 import mpq
from pandas import Timestamp
from PySide6.QtGui import QBrush, QPalette
from PySide6.QtWidgets import QStyleOptionViewItem

from core.safe_mpq import safe_mpq_from_any
from mpq2py import mpq_serialization
from settings import SECRET_MASK_CHAR, SECRET_MASK_GLYPHS
from themes.spec import TypeStyle
from tree.codecs.bytes_codec import decode_bytes
from tree.types import EMPTY_FAMILY, SECRET_FAMILY, WS_FAMILY, JsonType
from units import format_bytes
from units.number_affix import NumberAffix, format_number_affix

_PREVIEW_LIMIT = 80
_PREVIEW_CHILDREN = 5
_MULTILINE_SEPARATOR = " | "
_SECRET_MASK = SECRET_MASK_CHAR * SECRET_MASK_GLYPHS

# Whitespace preview map: every char that can appear in a WS_* value is rendered
# as a named escape so the user can see the actual shape of the data. Anything
# str.isspace()-true that isn't named below falls back to ``<??>``.
_WS_PREVIEW_MAP: dict[str, str] = {
    " ": "<SP>",
    "\t": "<TAB>",
    "\n": "<LF>",
    "\r": "<CR>",
    "\x0b": "<VT>",
    "\x0c": "<FF>",
    "\x85": "<NEL>",
    "\xa0": "<NBSP>",
    "\u1680": "<OGSP>",
    "\u2000": "<ENQ>",
    "\u2001": "<EMQ>",
    "\u2002": "<ENSP>",
    "\u2003": "<EMSP>",
    "\u2004": "<3MSP>",
    "\u2005": "<4MSP>",
    "\u2006": "<6MSP>",
    "\u2007": "<FIGSP>",
    "\u2008": "<PUNSP>",
    "\u2009": "<THINSP>",
    "\u200a": "<HAIRSP>",
    "\u2028": "<LS>",
    "\u2029": "<PS>",
    "\u202f": "<NNBSP>",
    "\u205f": "<MMSP>",
    "\u3000": "<IDSP>",
}


def _format_ws_preview(value: str) -> str:
    return "".join(_WS_PREVIEW_MAP.get(ch, "<??>") for ch in value)


def _single_line_preview_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").replace("\n", _MULTILINE_SEPARATOR)


def format_default(value: object, *, max_text_len: int | None = 80) -> str:
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


def _format_number_affix_for_display(value: NumberAffix) -> str:
    try:
        return format_number_affix(value)
    except ValueError:
        # Type switching intentionally creates a temporary empty-affix wrapper
        # when no per-document MRU exists yet.  The value editor will require a
        # valid affix before committing, but painting must remain non-throwing.
        if not value.affix:
            return format_default(value.number, max_text_len=None)
        return format_default(value, max_text_len=None)


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
        value = _single_line_preview_text(value)
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

    if json_type in SECRET_FAMILY:
        return _SECRET_MASK

    if json_type in EMPTY_FAMILY:
        return "<empty>"

    if json_type in WS_FAMILY and isinstance(value, str):
        return _elide(_format_ws_preview(value))

    if json_type in (JsonType.MULTILINE, JsonType.TEXT) and isinstance(value, str):
        return format_default(_single_line_preview_text(value))

    if json_type is JsonType.PERCENT:
        try:
            q = value if isinstance(value, mpq) else safe_mpq_from_any(value)
            if q is None:
                raise ValueError
            return f"{float(q * 100):g}%"
        except (TypeError, ValueError):
            return format_default(value)

    if json_type in (
        JsonType.INTEGER_CURRENCY,
        JsonType.INTEGER_UNITS,
        JsonType.FLOAT_CURRENCY,
        JsonType.FLOAT_UNITS,
    ):
        if isinstance(value, NumberAffix):
            return _format_number_affix_for_display(value)
        return format_default(value)

    if json_type in (JsonType.BYTES, JsonType.ZLIB, JsonType.GZIP):
        try:
            raw = decode_bytes(value, json_type) if isinstance(value, str) else bytes(value)
            preview = " ".join(f"{byte:02X}" for byte in raw[:16])
            if len(raw) > 20:
                preview += "..."
            printable_str = "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in raw[:16])
            return f"<{format_bytes(len(raw))}> | {preview} (`{printable_str}`)"
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
