import base64
import gzip
import logging
import re
import zlib
from datetime import date, timezone
from enum import StrEnum
from typing import Any

import gmpy2
from pandas import Timestamp

from core.datetime_parsing import parse_datetime_text
from core.datetime_parsing.nano_time import NanoTime
from core.raw_numeric import RawNumericValue
from settings import INFERENCE_MAX_COLOR_CHARS, NUMBER_AFFIX_MAX_LEN
from tree.inference_limits import base64_syntax_valid
from units.number_affix import AffixKind, NumberAffix, parse_number_affix

LOGGER = logging.getLogger(__name__)
_B64_RE = re.compile(r"^[A-Za-z0-9+/]{20,}={0,2}$")
_COLOR_RGB_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_COLOR_RGBA_RE = re.compile(r"^#(?:[0-9a-fA-F]{4}|[0-9a-fA-F]{8})$")


def looks_like_color_rgb(s: str, *, allow_expensive: bool = False) -> bool:
    if not allow_expensive and len(s) > INFERENCE_MAX_COLOR_CHARS:
        return False
    return bool(_COLOR_RGB_RE.fullmatch(s))


def looks_like_color_rgba(s: str, *, allow_expensive: bool = False) -> bool:
    if not allow_expensive and len(s) > INFERENCE_MAX_COLOR_CHARS:
        return False
    return bool(_COLOR_RGBA_RE.fullmatch(s))


def _looks_like_base64(s: str) -> bool:
    """Return True iff *s* is a syntactically valid, non-empty base64 string.

    Uses ``base64_syntax_valid`` as a cheap pre-check (len mod 4 + alphabet
    regex) before attempting the expensive ``base64.b64decode``. A minimum
    length of 20 chars is required to avoid false positives on short strings.

    No content heuristics are applied: any string that decodes cleanly under
    strict base64 rules is treated as ``BYTES``. Callers that need to
    discriminate against short / human-readable strings (e.g. ``"abcd"``)
    must pin the type explicitly via the type editor.
    """
    if not base64_syntax_valid(s):
        return False
    # Require minimum 20 chars to avoid false positives on short strings
    if len(s) < 20:
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


def _is_ws_only(s: str) -> bool:
    """Return True iff *s* is non-empty and consists entirely of whitespace.

    Uses ``str.isspace`` so it covers ASCII whitespace (SP/TAB/LF/CR/VT/FF)
    as well as Unicode whitespace (NBSP, IDSP, line/paragraph separators…).
    """
    return s != "" and s.isspace()


def _ws_has_newline(s: str) -> bool:
    return "\n" in s or "\r" in s or "\u2028" in s or "\u2029" in s


def _ws_type_for(s: str, *, force_multi: bool = False) -> "JsonType":
    """Pick the appropriate WS_* pseudo for a whitespace-only string *s*."""
    multi = force_multi or _ws_has_newline(s)
    non_ascii = _contains_non_ascii(s)
    if multi:
        return JsonType.WS_TEXT if non_ascii else JsonType.WS_MULTILINE
    return JsonType.WS_UNICODE if non_ascii else JsonType.WS_STRING


def infer_text_json_type(s: str) -> "JsonType":
    """Classify *s* within the text-only pseudo-type family.

    Used by ``parse_json_type`` for fresh inference (file load /
    container conversion). Picks both axes:
    - multiline-ness: ``MULTILINE`` / ``TEXT`` vs ``STRING`` / ``UNICODE``
    - ascii axis: ``UNICODE`` / ``TEXT`` vs ``STRING`` / ``MULTILINE``

    Empty strings are surfaced as ``EMPTY_STRING``; whitespace-only strings
    map to the ``WS_*`` pseudo family.
    """
    if s == "":
        return JsonType.EMPTY_STRING
    if _is_ws_only(s):
        return _ws_type_for(s)
    if _looks_like_multiline_text(s):
        return JsonType.TEXT if _contains_non_ascii(s) else JsonType.MULTILINE
    return JsonType.UNICODE if _contains_non_ascii(s) else JsonType.STRING


def text_pseudotype_for(current_type: "JsonType", s: str) -> "JsonType":
    """Pick a text-family type when the *current* field type is text-family.

    Preserves the single-line vs multiline shape implied by *current_type*
    (so ``STRING`` <-> ``UNICODE``, ``MULTILINE`` <-> ``TEXT``), and
    collapses to the empty/whitespace pseudo-types when content warrants it.

    Empty content yields ``EMPTY_STRING`` or ``EMPTY_MULTILINE`` based on
    the current shape. Whitespace-only content yields ``WS_*`` flavored
    along both axes (shape preserved, but upgraded to multiline if the
    string actually contains a newline).
    """
    is_multi_current = current_type in TEXT_MULTI_FAMILY
    if s == "":
        return JsonType.EMPTY_MULTILINE if is_multi_current else JsonType.EMPTY_STRING
    if _is_ws_only(s):
        return _ws_type_for(s, force_multi=is_multi_current)
    non_ascii = _contains_non_ascii(s)
    if is_multi_current:
        return JsonType.TEXT if non_ascii else JsonType.MULTILINE
    # STRING / UNICODE (and any other caller-text-family) stay single-line.
    return JsonType.UNICODE if non_ascii else JsonType.STRING


def parse_json_type(value: Any) -> "JsonType":
    """Infer a JsonType from raw value content only.

    Name-based secret promotion and secret content coercion are handled by
    model/item hooks, not by this parser.
    """
    match value:
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

        case RawNumericValue():
            return JsonType.RAW_FLOAT

        case str(s):
            if s == "":
                return JsonType.EMPTY_STRING
            if _is_ws_only(s):
                return _ws_type_for(s)

            if _looks_like_multiline_text(s):
                return JsonType.TEXT if _contains_non_ascii(s) else JsonType.MULTILINE

            if looks_like_color_rgba(s):
                return JsonType.COLOR_RGBA
            if looks_like_color_rgb(s):
                return JsonType.COLOR_RGB

            try:
                val = parse_datetime_text(s)
                match val:
                    case Timestamp(tzinfo=None):
                        return JsonType.DATETIME
                    case Timestamp():
                        if s.strip().upper().endswith("Z") and val.utcoffset() == timezone.utc.utcoffset(None):
                            return JsonType.DATETIMEUTC
                        return JsonType.DATETIMEZONE
                    case NanoTime():
                        return JsonType.TIME
                    case date():
                        return JsonType.DATE
            except Exception:
                pass

            parsed_affix = parse_number_affix(s, max_affix_len=NUMBER_AFFIX_MAX_LEN)
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

        case NumberAffix(kind=kind, number=number):
            is_int = isinstance(number, int)
            if kind is AffixKind.CURRENCY:
                return JsonType.INTEGER_CURRENCY if is_int else JsonType.FLOAT_CURRENCY
            return JsonType.INTEGER_UNITS if is_int else JsonType.FLOAT_UNITS

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
    MULTILINE = "multiline"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"
    NULL = "null"

    # Extra Number
    PERCENT = "percent"
    # Raw, unsupported numeric literal preserved as editable text. Pseudo-type:
    # derived from value content, never user-selectable.
    RAW_FLOAT = "raw float"
    INTEGER_UNITS = "int units"
    FLOAT_UNITS = "float units"
    INTEGER_CURRENCY = "int currency"
    FLOAT_CURRENCY = "float currency"

    # Multiline Text Format
    UNICODE = "utf-8 line"
    TEXT = "utf-8 text"
    SECRET_LINE = "secret line"
    SECRET_TEXT = "secret text"

    # Pseudo Text (purely-derived; not user-selectable). Empty / whitespace-only
    # content gets these previewable types so the value column makes the shape
    # visible. Editing behaves identically to the parent text type.
    EMPTY_STRING = "empty string"
    EMPTY_MULTILINE = "empty multiline"
    WS_STRING = "ws string"
    WS_UNICODE = "ws utf-8 line"
    WS_MULTILINE = "ws multiline"
    WS_TEXT = "ws utf-8 text"

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


TEXT_FAMILY: frozenset[JsonType] = frozenset(
    {
        JsonType.STRING,
        JsonType.UNICODE,
        JsonType.MULTILINE,
        JsonType.TEXT,
        JsonType.EMPTY_STRING,
        JsonType.EMPTY_MULTILINE,
        JsonType.WS_STRING,
        JsonType.WS_UNICODE,
        JsonType.WS_MULTILINE,
        JsonType.WS_TEXT,
    }
)
TEXT_LINE_FAMILY: frozenset[JsonType] = frozenset(
    {
        JsonType.STRING,
        JsonType.UNICODE,
        JsonType.EMPTY_STRING,
        JsonType.WS_STRING,
        JsonType.WS_UNICODE,
    }
)
TEXT_MULTI_FAMILY: frozenset[JsonType] = frozenset(
    {
        JsonType.MULTILINE,
        JsonType.TEXT,
        JsonType.EMPTY_MULTILINE,
        JsonType.WS_MULTILINE,
        JsonType.WS_TEXT,
    }
)
EMPTY_FAMILY: frozenset[JsonType] = frozenset({JsonType.EMPTY_STRING, JsonType.EMPTY_MULTILINE})
WS_FAMILY: frozenset[JsonType] = frozenset(
    {JsonType.WS_STRING, JsonType.WS_UNICODE, JsonType.WS_MULTILINE, JsonType.WS_TEXT}
)
PSEUDO_TEXT_FAMILY: frozenset[JsonType] = EMPTY_FAMILY | WS_FAMILY


# Parent (canonical, user-selectable) type for each pseudo text type.
PSEUDO_TEXT_PARENT: dict[JsonType, JsonType] = {
    JsonType.EMPTY_STRING: JsonType.STRING,
    JsonType.EMPTY_MULTILINE: JsonType.MULTILINE,
    JsonType.WS_STRING: JsonType.STRING,
    JsonType.WS_UNICODE: JsonType.UNICODE,
    JsonType.WS_MULTILINE: JsonType.MULTILINE,
    JsonType.WS_TEXT: JsonType.TEXT,
}


def canonical_text_type(json_type: JsonType) -> JsonType:
    """Return the user-selectable parent for a pseudo text type, else *json_type*."""
    return PSEUDO_TEXT_PARENT.get(json_type, json_type)


# Parent (canonical, user-selectable) type for each non-text pseudo type.
# RAW_FLOAT collapses to FLOAT in the type combo so the user sees the type they
# could pick, while editing/coercion keep treating it as raw text.
PSEUDO_NUMERIC_PARENT: dict[JsonType, JsonType] = {
    JsonType.RAW_FLOAT: JsonType.FLOAT,
}


def canonical_type(json_type: JsonType) -> JsonType:
    """Return the user-selectable parent for any pseudo type, else *json_type*."""
    if json_type in PSEUDO_NUMERIC_PARENT:
        return PSEUDO_NUMERIC_PARENT[json_type]
    return PSEUDO_TEXT_PARENT.get(json_type, json_type)


# Non-user-selectable pseudo types (derived purely from content).
PSEUDO_FAMILY: frozenset[JsonType] = PSEUDO_TEXT_FAMILY | frozenset({JsonType.RAW_FLOAT})

# Types the user can pick from the type combobox. Pseudo types are excluded
# because they are derived purely from content.
USER_SELECTABLE_TYPES: tuple[JsonType, ...] = tuple(t for t in JsonType if t not in PSEUDO_FAMILY)
SECRET_FAMILY: frozenset[JsonType] = frozenset({JsonType.SECRET_LINE, JsonType.SECRET_TEXT})
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
