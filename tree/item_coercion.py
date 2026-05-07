import base64
import binascii
import datetime
import gzip
import zlib
from typing import Any

from gmpy2 import mpq

from tree.stubs import stub_bytes_raw, stub_float, stub_integer, stub_multiline, stub_percent, stub_string
from tree.types import JsonType

# ---------------------------------------------------------------------------
# Bytes / text helpers
# ---------------------------------------------------------------------------


def _is_printable_text(s: str) -> bool:
    """True iff *s* contains no control chars except \\t, \\n, \\r."""
    if not s:
        return True
    return all(ch in "\t\n\r" or ch.isprintable() for ch in s)


def _bytes_to_printable_string(raw: bytes) -> str | None:
    """Decode *raw* as UTF-8 and return it if printable; otherwise None."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if _is_printable_text(text):
        return text
    return None


# ---------------------------------------------------------------------------
# Temporal helpers (3.2, 3.3)
# ---------------------------------------------------------------------------


def _now_for_type(json_type: JsonType) -> str:
    """Return a sensible 'now' ISO string for the given temporal type."""
    now = datetime.datetime.now(tz=datetime.timezone.utc).astimezone()
    match json_type:
        case JsonType.DATE:
            return now.date().isoformat()
        case JsonType.TIME:
            return now.time().replace(microsecond=0).isoformat(timespec="minutes")
        case JsonType.DATETIME:
            return now.replace(microsecond=0, tzinfo=None).isoformat(timespec="minutes")
        case JsonType.DATETIMEZONE:
            return now.replace(microsecond=0).isoformat(timespec="seconds")


def _try_parse_temporal(json_type: JsonType, value: Any) -> str | None:
    """Convert *value* to a canonical ISO string for *json_type*.

    Handles Python date/time/datetime objects, int epoch seconds (≥ 10^12 →
    milliseconds), and ISO strings.  Returns ``None`` when the value cannot
    be sensibly mapped to *json_type*.
    """
    # datetime must be tested before date (bool ⊂ int but fine here)
    if isinstance(value, datetime.datetime):
        match json_type:
            case JsonType.DATE:
                return value.date().isoformat()
            case JsonType.TIME:
                return value.time().replace(microsecond=0).isoformat(timespec="minutes")
            case JsonType.DATETIME:
                return value.replace(microsecond=0, tzinfo=None).isoformat(timespec="minutes")
            case JsonType.DATETIMEZONE:
                if value.tzinfo is None:
                    value = value.replace(tzinfo=datetime.timezone.utc)
                return value.replace(microsecond=0).isoformat(timespec="seconds")
        return None

    if isinstance(value, datetime.date):
        match json_type:
            case JsonType.DATE:
                return value.isoformat()
            case JsonType.DATETIME:
                return datetime.datetime(value.year, value.month, value.day).isoformat(timespec="minutes")
            case JsonType.DATETIMEZONE:
                return datetime.datetime(value.year, value.month, value.day, tzinfo=datetime.timezone.utc).isoformat(
                    timespec="seconds"
                )
        return None

    if isinstance(value, datetime.time):
        if json_type is JsonType.TIME:
            return value.replace(microsecond=0).isoformat(timespec="minutes")
        return None

    # int → epoch seconds (≥ 10^12 treated as milliseconds)
    if isinstance(value, int) and not isinstance(value, bool):
        if json_type is JsonType.TIME:
            return None  # no meaningful epoch-to-time mapping
        ts = value / 1000.0 if abs(value) >= 10**12 else float(value)
        try:
            dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
            return _try_parse_temporal(json_type, dt)
        except (ValueError, OSError):
            pass
        return None

    # str round-trip
    if isinstance(value, str) and value:
        # Try time first (time strings are not valid datetime strings)
        try:
            return _try_parse_temporal(json_type, datetime.time.fromisoformat(value))
        except ValueError:
            pass
        # dateutil handles full datetime/date/tz strings
        try:
            from dateutil.parser import isoparse

            return _try_parse_temporal(json_type, isoparse(value))
        except Exception:
            pass

    return None


# ---------------------------------------------------------------------------
# Bytes helpers (3.4)
# ---------------------------------------------------------------------------


def _looks_valid_for(json_type: JsonType, value: str) -> bool:
    """Return True iff *value* is a valid encoded representation for *json_type*."""
    from delegates.bytes_codec import decode_bytes

    try:
        decode_bytes(value, json_type)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def normalize_value_for_type(json_type: JsonType, value: Any) -> Any:
    if json_type in (JsonType.STRING, JsonType.UNICODE) and not isinstance(value, str):
        return repr(value)
    return value


def coerce_value_for_type(
    json_type: JsonType,
    value: Any,
    strict: bool,
    old_type: JsonType | None = None,
) -> tuple[bool, Any]:
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
                # Saint coercion: arbitrary strings → truthiness of the string.
                return (False, None) if strict else (True, bool(value))
            if value is None:
                return (False, None) if strict else (True, False)
            return True, bool(value)

        case JsonType.INTEGER:
            # 3.3: datetime objects → epoch seconds for round-trip
            if isinstance(value, datetime.datetime):
                return True, int(value.timestamp())
            if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
                epoch = datetime.datetime(value.year, value.month, value.day, tzinfo=datetime.timezone.utc)
                return True, int(epoch.timestamp())
            # bytes-family → decoded length is a meaningful integer
            if isinstance(value, str) and old_type in (JsonType.BYTES, JsonType.ZLIB, JsonType.GZIP):
                from delegates.bytes_codec import decode_bytes

                try:
                    return True, len(decode_bytes(value, old_type))
                except Exception:
                    pass
            try:
                return True, int(value)
            except (ValueError, TypeError):
                pass
            # Float-as-string ("3.14") → truncate to int
            try:
                return True, int(float(value))
            except (ValueError, TypeError):
                pass
            return (False, None) if strict else (True, stub_integer())

        case JsonType.FLOAT:
            try:
                return True, mpq(str(value))
            except (ValueError, TypeError):
                pass
            return (False, None) if strict else (True, stub_float())

        case JsonType.PERCENT:
            try:
                v = mpq(str(value))
                if 0 <= v <= 1:
                    return True, v
            except (ValueError, TypeError):
                pass
            return (False, None) if strict else (True, stub_percent())

        # 3.1: bool → lowercase "true"/"false" instead of Python's "True"/"False"
        case JsonType.STRING | JsonType.UNICODE | JsonType.MULTILINE | JsonType.TEXT:
            if value is None:
                # Saint coercion: empty box of nothing → friendly placeholder.
                if strict:
                    return True, ""
                return True, stub_multiline() if json_type in (JsonType.MULTILINE, JsonType.TEXT) else stub_string()
            if isinstance(value, bool):
                return True, "true" if value else "false"
            # Bytes-family → decode and surface the underlying text when printable.
            if isinstance(value, str) and old_type in (JsonType.BYTES, JsonType.ZLIB, JsonType.GZIP):
                from delegates.bytes_codec import decode_bytes

                try:
                    raw = decode_bytes(value, old_type)
                except Exception:
                    raw = None
                if raw is not None:
                    text = _bytes_to_printable_string(raw)
                    if text is not None:
                        return True, text
                    # Non-printable: keep the base64 representation (better than nothing).
                    return True, value
            if isinstance(value, (bytes, bytearray, memoryview)):
                text = _bytes_to_printable_string(bytes(value))
                if text is not None:
                    return True, text
                # Fallback: base64-encode raw bytes so the user can still see/edit them.
                return True, base64.b64encode(bytes(value)).decode("ascii")
            return True, str(value)

        # 3.2: fall back to "now" instead of epoch-zero when value is unparseable
        case JsonType.DATE | JsonType.TIME | JsonType.DATETIME | JsonType.DATETIMEZONE:
            parsed = _try_parse_temporal(json_type, value)
            if parsed is not None:
                return True, parsed
            return True, _now_for_type(json_type)

        # 3.4: encode-on-switch; use old_type for lossless cross-format re-encoding
        case JsonType.BYTES | JsonType.ZLIB | JsonType.GZIP:
            from delegates.bytes_codec import decode_bytes, encode_bytes

            if value is None:
                return (True, "") if strict else (True, encode_bytes(stub_bytes_raw(), json_type))
            # 1) already a valid encoded string for the requested kind → keep
            if isinstance(value, str) and _looks_valid_for(json_type, value):
                return True, value
            # 2) re-encode from the known old bytes-like kind (cross-format switch)
            if isinstance(value, str) and value and old_type in (JsonType.BYTES, JsonType.ZLIB, JsonType.GZIP):
                try:
                    raw = decode_bytes(value, old_type)
                    return True, encode_bytes(raw, json_type)
                except Exception:
                    pass
            # 3) raw bytes → encode
            if isinstance(value, (bytes, bytearray, memoryview)):
                return True, encode_bytes(bytes(value), json_type)
            # 4) fallback: encode text representation as UTF-8
            if isinstance(value, str):
                if not value:
                    return (True, "") if strict else (True, encode_bytes(stub_bytes_raw(), json_type))
                return True, encode_bytes(value.encode("utf-8"), json_type)
            return True, encode_bytes(str(value).encode("utf-8"), json_type)

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
