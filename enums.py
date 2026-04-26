import base64
import gzip
import logging
import re
import zlib
from datetime import date, datetime, time
from enum import StrEnum
from typing import Any

import gmpy2

from datetime_editor import parse_datetime_text

LOGGER = logging.getLogger(__name__)
_B64_RE = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")


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
    """Classify *s* within the text-only pseudo-type family."""
    if _looks_like_multiline_text(s):
        return JsonType.TEXT if _contains_non_ascii(s) else JsonType.MULTILINE
    return JsonType.UNICODE if _contains_non_ascii(s) else JsonType.STRING


def parse_json_type(value: Any) -> "JsonType":
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

        case str(s):
            if _looks_like_multiline_text(s):
                return JsonType.TEXT if _contains_non_ascii(s) else JsonType.MULTILINE

            try:
                val = parse_datetime_text(s)
                match val:
                    case datetime(tzinfo=None):
                        return JsonType.DATETIME
                    case datetime():
                        return JsonType.DATETIMEZONE
                    case time():
                        return JsonType.TIME
                    case date():
                        return JsonType.DATE
            except Exception:
                pass

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

    # Multiline Text Format
    MULTILINE = "multiline"
    TEXT = "utf-8 text"

    # Datetime Text Format
    DATE = "date"
    TIME = "time"
    DATETIME = "datetime"
    DATETIMEZONE = "dt+timezone"

    # Advanced Text Encoding
    BYTES = "bytes"  # base64
    ZLIB = "zlib"  # base64+zlib
    GZIP = "gzip"  # base64+gzip
