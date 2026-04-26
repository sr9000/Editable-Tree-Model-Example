import base64
import binascii
import gzip
import zlib
from typing import Any

from gmpy2 import mpq

from tree.types import JsonType


def normalize_value_for_type(json_type: JsonType, value: Any) -> Any:
    if json_type in (JsonType.STRING, JsonType.UNICODE) and not isinstance(value, str):
        return repr(value)
    return value


def coerce_value_for_type(json_type: JsonType, value: Any, strict: bool) -> tuple[bool, Any]:
    match json_type:
        case JsonType.NULL:
            return True, None
        case JsonType.BOOLEAN:
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in ("true", "1", "yes", "y"):
                    return True, True
                if normalized in ("false", "0", "no", "n"):
                    return True, False
                return (False, None) if strict else (True, False)
            return True, bool(value)
        case JsonType.INTEGER:
            try:
                return True, int(value)
            except Exception:
                return (False, None) if strict else (True, 0)
        case JsonType.FLOAT:
            try:
                return True, mpq(str(value))
            except Exception:
                return (False, None) if strict else (True, mpq(0))
        case JsonType.PERCENT:
            try:
                v = mpq(str(value))
            except Exception:
                return (False, None) if strict else (True, mpq(0))
            if 0 <= v <= 1:
                return True, v
            return (False, None) if strict else (True, mpq(0))
        case JsonType.STRING:
            return True, "" if value is None else str(value)
        case JsonType.UNICODE:
            return True, "" if value is None else str(value)
        case JsonType.MULTILINE:
            return True, "" if value is None else str(value)
        case JsonType.TEXT:
            return True, "" if value is None else str(value)
        case JsonType.DATE:
            return True, "1970-01-01" if value is None else str(value)
        case JsonType.TIME:
            return True, "00:00" if value is None else str(value)
        case JsonType.DATETIME:
            return True, "1970-01-01T00:00" if value is None else str(value)
        case JsonType.DATETIMEZONE:
            return True, "1970-01-01T00:00:00+00:00" if value is None else str(value)
        case JsonType.BYTES | JsonType.ZLIB | JsonType.GZIP:
            if value is None:
                return True, ""
            if not isinstance(value, str):
                return (False, None) if strict else (True, "")
            if not value:
                return True, ""
            try:
                raw = base64.b64decode(value, validate=True)
                if json_type is JsonType.ZLIB:
                    zlib.decompress(raw)
                elif json_type is JsonType.GZIP:
                    gzip.decompress(raw)
                return True, value
            except Exception:
                return (False, None) if strict else (True, "")
        case JsonType.ARRAY:
            if isinstance(value, list):
                return True, value
            return (False, None) if strict else (True, [])
        case JsonType.OBJECT:
            if isinstance(value, dict):
                return True, value
            return (False, None) if strict else (True, {})


def compute_editable(json_type: JsonType, value: Any, editable_blob_limit: int) -> bool:
    if json_type in (JsonType.NULL, JsonType.ARRAY, JsonType.OBJECT):
        return False

    try:
        match json_type:
            case JsonType.STRING | JsonType.UNICODE | JsonType.MULTILINE | JsonType.TEXT:
                return len(value) <= editable_blob_limit
            case JsonType.BYTES:
                raw = base64.b64decode(value, validate=True)
                return len(raw) <= editable_blob_limit
            case JsonType.ZLIB:
                raw = base64.b64decode(value, validate=True)
                return len(zlib.decompress(raw)) <= editable_blob_limit
            case JsonType.GZIP:
                raw = base64.b64decode(value, validate=True)
                return len(gzip.decompress(raw)) <= editable_blob_limit
            case _:
                return True
    except (binascii.Error, zlib.error, OSError, ValueError, TypeError):
        return False
