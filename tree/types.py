import base64
import gzip
import logging
import re
import zlib
from datetime import date, datetime, time, timezone
from enum import StrEnum
from typing import Any

import gmpy2

from datetime_editor import parse_datetime_text
from units.number_affix import AffixKind, NumberAffix, parse_number_affix

LOGGER = logging.getLogger(__name__)
_B64_RE = re.compile(r"^[A-Za-z0-9+/]{20,}={0,2}$")
_COLOR_RGB_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_COLOR_RGBA_RE = re.compile(r"^#(?:[0-9a-fA-F]{4}|[0-9a-fA-F]{8})$")


def looks_like_color_rgb(s: str) -> bool:
    return bool(_COLOR_RGB_RE.fullmatch(s))


def looks_like_color_rgba(s: str) -> bool:
    return bool(_COLOR_RGBA_RE.fullmatch(s))


def _looks_like_base64(s: str) -> bool:
    """Return True iff *s* is a syntactically valid, non-empty base64 string.

    No content heuristics are applied: any string that decodes cleanly under
    strict base64 rules is treated as ``BYTES``. Callers that need to
    discriminate against short / human-readable strings (e.g. ``"abcd"``)
    must pin the type explicitly via the type editor.
    """
    if not s or len(s) % 4 != 0:
        return False
    if _B64_RE.fullmatch(s) is None:
        return False
    try:
        base64.b64decode(s, validate=True)
    except Exception:
        return False
    return True


def _contains_non_ascii(s: str) -> bool:
    return any(ord(ch) > 127 for ch in s)


def _looks_like_multiline_text(s: str) -> bool:
    return "\n" in s and (s.count("\n") > 1 or len(s) > 80)


def infer_text_json_type(s: str) -> "JsonType":
    """Classify *s* within the text-only pseudo-type family.

    Used by ``parse_json_type`` for fresh inference (file load /
    container conversion). Picks both axes:
    - multiline-ness: ``MULTILINE`` / ``TEXT`` vs ``STRING`` / ``UNICODE``
    - ascii axis: ``UNICODE`` / ``TEXT`` vs ``STRING`` / ``MULTILINE``
    """
    if _looks_like_multiline_text(s):
        return JsonType.TEXT if _contains_non_ascii(s) else JsonType.MULTILINE
    return JsonType.UNICODE if _contains_non_ascii(s) else JsonType.STRING


def text_pseudotype_for(current_type: "JsonType", s: str) -> "JsonType":
    """Pick a text-family type when the *current* field type is text-family.

    This switches **only along the ascii axis**, preserving multiline-ness.
    Allowed transitions:

    - ``STRING`` <-> ``UNICODE``
    - ``MULTILINE`` <-> ``TEXT``

    Any cross-family switch (e.g. ``STRING`` -> ``MULTILINE`` or
    ``UNICODE`` -> ``TEXT``) is intentionally **not** performed here:
    once the user has chosen a single-line vs multiline shape, edits
    keep that shape until the type is changed explicitly.
    """
    non_ascii = _contains_non_ascii(s)
    if current_type in (JsonType.MULTILINE, JsonType.TEXT):
        return JsonType.TEXT if non_ascii else JsonType.MULTILINE
    # STRING / UNICODE (and any other caller-text-family) stay single-line.
    return JsonType.UNICODE if non_ascii else JsonType.STRING


def parse_json_type(value: Any) -> "JsonType":
    match value:
        case NumberAffix(kind=kind, number=number):
            is_int = isinstance(number, int)
            if kind is AffixKind.CURRENCY:
                return JsonType.INTEGER_CURRENCY if is_int else JsonType.FLOAT_CURRENCY
            return JsonType.INTEGER_UNITS if is_int else JsonType.FLOAT_UNITS

        case None:
            return JsonType.NULL

        case bool(_):
            return JsonType.BOOLEAN

        case int(_):
            return JsonType.INTEGER

        case float(x):
            if 0.0 <= x <= 1.0:
                return JsonType.PERCENT
            return JsonType.FLOAT

        case gmpy2.mpq() as q:
            if 0 <= q <= 1:
                return JsonType.PERCENT
            return JsonType.FLOAT

        case str(s):
            if _looks_like_multiline_text(s):
                return JsonType.TEXT if _contains_non_ascii(s) else JsonType.MULTILINE

            if looks_like_color_rgba(s):
                return JsonType.COLOR_RGBA
            if looks_like_color_rgb(s):
                return JsonType.COLOR_RGB

            try:
                val = parse_datetime_text(s)
                match val:
                    case datetime(tzinfo=None):
                        return JsonType.DATETIME
                    case datetime():
                        if s.strip().upper().endswith("Z") and val.utcoffset() == timezone.utc.utcoffset(None):
                            return JsonType.DATETIMEUTC
                        return JsonType.DATETIMEZONE
                    case time():
                        return JsonType.TIME
                    case date():
                        return JsonType.DATE
            except Exception:
                pass

            parsed_affix = parse_number_affix(s)
            if parsed_affix is not None:
                return parse_json_type(parsed_affix)

            if _looks_like_base64(s):
                raw = base64.b64decode(s, validate=True)

                try:
                    zlib.decompress(raw)
                    return JsonType.ZLIB
                except Exception:
                    pass

                try:
                    gzip.decompress(raw)
                    return JsonType.GZIP
                except Exception:
                    pass

                return JsonType.BYTES

            return JsonType.UNICODE if _contains_non_ascii(s) else JsonType.STRING

        case list(_):
            return JsonType.ARRAY

        case dict(_):
            return JsonType.OBJECT

    LOGGER.warning("Unsupported value type for parse_json_type: %s", type(value).__name__)
    return JsonType.STRING


class JsonType(StrEnum):
    # Basic
    INTEGER = "integer"
    FLOAT = "float"
    STRING = "string"
    UNICODE = "utf-8 line"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"
    NULL = "null"

    # Extra Number
    PERCENT = "percent"
    INTEGER_CURRENCY = "int currency"
    INTEGER_UNITS = "int units"
    FLOAT_CURRENCY = "float currency"
    FLOAT_UNITS = "float units"

    # Multiline Text Format
    MULTILINE = "multiline"
    TEXT = "utf-8 text"

    # Datetime Text Format
    DATE = "date"
    TIME = "time"
    DATETIME = "datetime"
    DATETIMEUTC = "datetime utc"
    DATETIMEZONE = "dt+timezone"

    # Advanced Text Encoding
    BYTES = "bytes"  # base64
    ZLIB = "zlib"  # base64+zlib
    GZIP = "gzip"  # base64+gzip

    # Color (HTML hex format with leading #)
    COLOR_RGB = "rgb"  # #rgb / #rrggbb
    COLOR_RGBA = "rgba"  # #rgba / #rrggbbaa


TEXT_FAMILY: frozenset[JsonType] = frozenset({JsonType.STRING, JsonType.UNICODE, JsonType.MULTILINE, JsonType.TEXT})
COLOR_FAMILY: frozenset[JsonType] = frozenset({JsonType.COLOR_RGB, JsonType.COLOR_RGBA})
DATETIME_FAMILY: frozenset[JsonType] = frozenset(
    {JsonType.DATE, JsonType.TIME, JsonType.DATETIME, JsonType.DATETIMEZONE, JsonType.DATETIMEUTC}
)
NUMBER_FAMILY: frozenset[JsonType] = frozenset(
    {
        JsonType.INTEGER,
        JsonType.FLOAT,
        JsonType.PERCENT,
        JsonType.INTEGER_CURRENCY,
        JsonType.INTEGER_UNITS,
        JsonType.FLOAT_CURRENCY,
        JsonType.FLOAT_UNITS,
    }
)
