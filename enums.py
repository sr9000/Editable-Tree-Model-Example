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
    if len(s) < 16 or len(s) % 4 != 0:
        return False
    if _B64_RE.fullmatch(s) is None:
        return False
    try:
        raw = base64.b64decode(s, validate=True)
    except Exception:
        return False
    if not raw:
        return False
    text_ratio = sum(32 <= b < 127 for b in raw) / len(raw)
    return text_ratio < 0.85


def parse_json_type(value: Any) -> "JsonType":
    match value:
        case None:
            return JsonType.NULL

        case bool(_):
            return JsonType.BOOLEAN

        case int(_):
            return JsonType.INTEGER

        case float(x):
            return JsonType.FLOAT

        case gmpy2.mpq():
            return JsonType.FLOAT

        case str(s):
            if "\n" in s and (s.count("\n") > 1 or len(s) > 80):
                return JsonType.MULTILINE

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

            return JsonType.STRING

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
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"
    NULL = "null"

    # Extra Number
    PERCENT = "percent"

    # Multiline Text Format
    MULTILINE = "multiline"

    # Datetime Text Format
    DATE = "date"
    TIME = "time"
    DATETIME = "datetime"
    DATETIMEZONE = "dt+timezone"

    # Advanced Text Encoding
    BYTES = "bytes"  # base64
    ZLIB = "zlib"  # base64+zlib
    GZIP = "gzip"  # base64+gzip
