import base64
import binascii
import datetime
import gzip
import zlib
from typing import Any

import gmpy2
from gmpy2 import mpq
from pandas import Timestamp

from core.datetime_parsing.enums import DateTimeCategory
from core.datetime_parsing.nano_time import NanoTime
from core.datetime_parsing.regex import parse_datetime_text
from core.raw_numeric import RawNumericValue
from core.safe_mpq import safe_mpq_from_any
from mpq2py import mpq_serialization
from settings import NUMBER_AFFIX_MAX_LEN
from tree.codecs.bytes_codec import decode_bytes, encode_bytes
from tree.codecs.color_codec import normalize_color_string
from tree.stubs import (
    stub_bytes_raw,
    stub_color_rgb,
    stub_color_rgba,
    stub_float,
    stub_integer,
    stub_multiline,
    stub_percent,
    stub_string,
)
from tree.types import TEXT_FAMILY, TEXT_MULTI_FAMILY, JsonType
from units.number_affix import AffixKind, NumberAffix, format_number_affix, parse_number_affix

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
    now = Timestamp.now(tz="UTC").tz_convert(None).tz_localize(datetime.timezone.utc).to_pydatetime().astimezone()
    match json_type:
        case JsonType.DATE:
            return now.date().isoformat()
        case JsonType.TIME:
            return NanoTime(hour=now.hour, minute=now.minute).isoformat(timespec="minutes")
        case JsonType.DATETIME:
            naive = now.replace(microsecond=0, tzinfo=None)
            return naive.isoformat(sep=" ", timespec="minutes")
        case JsonType.DATETIMEZONE:
            return now.replace(microsecond=0).isoformat(timespec="seconds")
        case JsonType.DATETIMEUTC:
            return (
                now.astimezone(datetime.timezone.utc)
                .replace(microsecond=0)
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z")
            )
    raise ValueError(f"Unsupported temporal JsonType: {json_type}")


def _timespec_for_clock(second: int, subsecond: int) -> str:
    if subsecond:
        return "microseconds"
    if second:
        return "seconds"
    return "minutes"


def _category_for_temporal_type(json_type: JsonType) -> DateTimeCategory | None:
    match json_type:
        case JsonType.DATE:
            return DateTimeCategory.Date
        case JsonType.TIME:
            return DateTimeCategory.Time
        case JsonType.DATETIME:
            return DateTimeCategory.DateTime
        case JsonType.DATETIMEZONE:
            return DateTimeCategory.DateTimeWithTZ
        case JsonType.DATETIMEUTC:
            return DateTimeCategory.DateTimeUTC
    return None


def _is_temporal_type(json_type: JsonType | None) -> bool:
    return json_type in (JsonType.DATE, JsonType.TIME, JsonType.DATETIME, JsonType.DATETIMEZONE, JsonType.DATETIMEUTC)


def _epoch_seconds_from_temporal(
    value: Any, hinted_type: JsonType | None = None, *, allow_expensive: bool = False
) -> mpq | None:
    """Convert temporal-like input to epoch seconds.

    DATETIME/DATE are Unix epoch seconds (UTC for naive values).
    TIME is seconds since day start.
    """

    def _seconds_since_midnight(t: NanoTime) -> mpq:
        return mpq(t.hour * 3600 + t.minute * 60 + t.second) + mpq(t.nanosecond, 1_000_000_000)

    # Timestamp must be checked before datetime (it's a subclass)
    if isinstance(value, Timestamp):
        dt = value.to_pydatetime()
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return mpq(int(dt.timestamp() * 1_000_000), 1_000_000)

    if isinstance(value, datetime.datetime):
        dt = value if value.tzinfo is not None else value.replace(tzinfo=datetime.timezone.utc)
        return mpq(int(dt.timestamp() * 1_000_000), 1_000_000)

    if isinstance(value, datetime.date):
        dt = datetime.datetime(value.year, value.month, value.day, tzinfo=datetime.timezone.utc)
        return mpq(int(dt.timestamp()))

    if isinstance(value, NanoTime):
        return _seconds_since_midnight(value)

    if isinstance(value, str) and value:
        raw = value.strip()
        categories: list[DateTimeCategory] = []
        hinted = _category_for_temporal_type(hinted_type) if hinted_type is not None else None
        if hinted is not None:
            categories.append(hinted)
        categories.extend(
            [
                DateTimeCategory.DateTimeUTC,
                DateTimeCategory.DateTimeWithTZ,
                DateTimeCategory.DateTime,
                DateTimeCategory.Date,
                DateTimeCategory.Time,
            ]
        )

        for category in categories:
            parsed = parse_datetime_text(raw, category, allow_expensive=allow_expensive)
            if parsed is None:
                continue
            if isinstance(parsed, Timestamp):
                dt = parsed.to_pydatetime()
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=datetime.timezone.utc)
                return mpq(int(dt.timestamp() * 1_000_000), 1_000_000)
            if isinstance(parsed, datetime.date):
                dt = datetime.datetime(parsed.year, parsed.month, parsed.day, tzinfo=datetime.timezone.utc)
                return mpq(int(dt.timestamp()))
            if isinstance(parsed, NanoTime):
                return _seconds_since_midnight(parsed)
    return None


def _try_parse_temporal(json_type: JsonType, value: Any, *, allow_expensive: bool = False) -> str | None:
    """Convert *value* to a canonical ISO string for *json_type*.

    Handles Python date/Timestamp/NanoTime objects, int epoch seconds (≥ 10^12 →
    milliseconds), and ISO strings.  Returns ``None`` when the value cannot
    be sensibly mapped to *json_type*.
    """
    # Timestamp must be tested before datetime (subclass)
    if isinstance(value, Timestamp):
        match json_type:
            case JsonType.DATE:
                return value.date().isoformat()
            case JsonType.TIME:
                t = NanoTime(
                    hour=value.hour, minute=value.minute, second=value.second, nanosecond=value.microsecond * 1000
                )
                return t.isoformat(timespec=_timespec_for_clock(t.second, t.nanosecond))
            case JsonType.DATETIME:
                naive = value.tz_localize(None) if value.tzinfo is not None else value
                return naive.isoformat(sep=" ", timespec=_timespec_for_clock(naive.second, naive.microsecond))
            case JsonType.DATETIMEZONE:
                aware = value if value.tzinfo is not None else value.tz_localize("UTC")
                return aware.isoformat(timespec=_timespec_for_clock(aware.second, aware.microsecond))
            case JsonType.DATETIMEUTC:
                utc = (value if value.tzinfo is not None else value.tz_localize("UTC")).tz_convert("UTC")
                return utc.isoformat(timespec=_timespec_for_clock(utc.second, utc.microsecond)).replace("+00:00", "Z")
        return None

    if isinstance(value, datetime.datetime):
        match json_type:
            case JsonType.DATE:
                return value.date().isoformat()
            case JsonType.TIME:
                t = NanoTime(
                    hour=value.hour, minute=value.minute, second=value.second, nanosecond=value.microsecond * 1000
                )
                return t.isoformat(timespec=_timespec_for_clock(t.second, t.nanosecond))
            case JsonType.DATETIME:
                naive = value.replace(tzinfo=None)
                return naive.isoformat(sep=" ", timespec=_timespec_for_clock(naive.second, naive.microsecond))
            case JsonType.DATETIMEZONE:
                if value.tzinfo is None:
                    value = value.replace(tzinfo=datetime.timezone.utc)
                return value.isoformat(timespec=_timespec_for_clock(value.second, value.microsecond))
            case JsonType.DATETIMEUTC:
                utc = (value if value.tzinfo is not None else value.replace(tzinfo=datetime.timezone.utc)).astimezone(
                    datetime.timezone.utc
                )
                return utc.isoformat(timespec=_timespec_for_clock(utc.second, utc.microsecond)).replace("+00:00", "Z")
        return None

    if isinstance(value, datetime.date):
        match json_type:
            case JsonType.DATE:
                return value.isoformat()
            case JsonType.DATETIME:
                return datetime.datetime(value.year, value.month, value.day).isoformat(sep=" ", timespec="minutes")
            case JsonType.DATETIMEZONE:
                return datetime.datetime(value.year, value.month, value.day, tzinfo=datetime.timezone.utc).isoformat(
                    timespec="seconds"
                )
            case JsonType.DATETIMEUTC:
                return (
                    datetime.datetime(value.year, value.month, value.day, tzinfo=datetime.timezone.utc)
                    .isoformat(timespec="seconds")
                    .replace("+00:00", "Z")
                )
        return None

    if isinstance(value, NanoTime):
        if json_type is JsonType.TIME:
            return value.isoformat(timespec=_timespec_for_clock(value.second, value.nanosecond))
        return None

    # Number → Unix epoch seconds (DATE/DATETIME/DATETIMEZONE) or seconds since
    # day start (TIME). Epoch numbers keep the historical milliseconds heuristic.
    if isinstance(value, (int, float, gmpy2.mpq)) and not isinstance(value, bool):
        try:
            numeric = float(value)
        except (TypeError, ValueError, OverflowError):
            numeric = None

        if numeric is None:
            return None

        if json_type is JsonType.TIME:
            if not (0.0 <= numeric < 24 * 60 * 60):
                return None
            whole_seconds = int(numeric)
            nanos = int(round((numeric - whole_seconds) * 1_000_000_000))
            if nanos >= 1_000_000_000:
                whole_seconds += 1
                nanos -= 1_000_000_000
            if whole_seconds >= 24 * 60 * 60:
                return None
            hour, rem = divmod(whole_seconds, 3600)
            minute, second = divmod(rem, 60)
            parsed_time = NanoTime(hour=hour, minute=minute, second=second, nanosecond=nanos)
            return _try_parse_temporal(json_type, parsed_time, allow_expensive=allow_expensive)

        ts = numeric / 1000.0 if isinstance(value, int) and abs(value) >= 10**12 else numeric
        try:
            dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
            return _try_parse_temporal(json_type, dt, allow_expensive=allow_expensive)
        except (ValueError, OSError, OverflowError):
            pass
        return None

    # str round-trip
    if isinstance(value, str) and value:
        raw = value.strip()
        category = _category_for_temporal_type(json_type)
        if category is not None and parse_datetime_text(raw, category, allow_expensive=allow_expensive) is not None:
            # Keep exactly what user entered so optional parts (seconds/microseconds)
            # can be added/removed dynamically without being rewritten away.
            return raw

        # Try time first (time strings are not valid datetime strings)
        try:
            return _try_parse_temporal(json_type, NanoTime.fromisoformat(raw), allow_expensive=allow_expensive)
        except ValueError:
            pass
        # dateutil handles full datetime/date/tz strings
        try:
            from dateutil.parser import isoparse

            return _try_parse_temporal(json_type, isoparse(raw), allow_expensive=allow_expensive)
        except Exception:
            pass

    return None


# ---------------------------------------------------------------------------
# Bytes helpers (3.4)
# ---------------------------------------------------------------------------


def _looks_valid_for(json_type: JsonType, value: str) -> bool:
    """Return True iff *value* is a valid encoded representation for *json_type*."""

    try:
        decode_bytes(value, json_type)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def normalize_value_for_type(json_type: JsonType, value: Any) -> Any:
    if isinstance(value, RawNumericValue):
        return value
    if (json_type in TEXT_FAMILY or json_type in (JsonType.SECRET_LINE, JsonType.SECRET_TEXT)) and not isinstance(
        value, str
    ):
        return repr(value)
    return value


def coerce_value_for_type(
    json_type: JsonType,
    value: Any,
    strict: bool,
    old_type: JsonType | None = None,
    *,
    allow_expensive: bool = False,
) -> tuple[bool, Any]:
    def _to_mpq_or_none(raw: Any) -> mpq | None:
        return safe_mpq_from_any(raw)

    def _int_from_exact(raw: Any) -> int | None:
        if isinstance(raw, int):
            return raw
        q = _to_mpq_or_none(raw)
        if q is None or q.denominator != 1:
            return None
        return int(q)

    def _int_from_truncated(raw: Any) -> int | None:
        if isinstance(raw, int):
            return raw
        q = _to_mpq_or_none(raw)
        if q is not None:
            return int(q)
        try:
            return int(float(raw))
        except (ValueError, TypeError):
            return None

    def _affix_kind_for(target: JsonType) -> AffixKind:
        if target in (JsonType.INTEGER_CURRENCY, JsonType.FLOAT_CURRENCY):
            return AffixKind.CURRENCY
        return AffixKind.UNITS

    def _rebuild_affix(parsed: NumberAffix, *, kind: AffixKind, number: int | mpq) -> NumberAffix:
        return NumberAffix(
            kind=kind,
            affix=parsed.affix,
            space=parsed.space,
            number=number,
            integral_digits=parsed.integral_digits,
            fractional_digits=parsed.fractional_digits,
            explicit_plus=parsed.explicit_plus,
        )

    # Targeting the RAW_FLOAT pseudo-type: always keep the value as a raw
    # numeric literal (this path is only reachable programmatically; the type
    # is not user-selectable).
    if json_type is JsonType.RAW_FLOAT:
        if isinstance(value, RawNumericValue):
            return True, value
        return True, RawNumericValue(raw="" if value is None else str(value))

    # Raw, unsupported numeric literals: keep them as raw text on numeric
    # targets when still unparseable (the model redirects to RAW_FLOAT). For
    # any other target, fall back to the exact raw string so conversion never
    # silently substitutes a numeric stub for the user's data.
    if isinstance(value, RawNumericValue):
        recovered = safe_mpq_from_any(value.raw)
        if recovered is not None:
            value = recovered
        elif json_type in (JsonType.FLOAT, JsonType.PERCENT):
            return True, value
        else:
            value = value.raw

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
            if isinstance(value, NumberAffix):
                truncated = _int_from_truncated(value.number)
                if truncated is None:
                    return False, None
                return True, truncated
            temporal_epoch = _epoch_seconds_from_temporal(value, hinted_type=old_type, allow_expensive=allow_expensive)
            if temporal_epoch is not None:
                return True, int(temporal_epoch)
            if _is_temporal_type(old_type):
                # Keep temporal transitions safe: if temporal parsing fails,
                # use the normal fallback path instead of reinterpreting raw digits.
                return (False, None) if strict else (True, stub_integer())
            # bytes-family → decoded length is a meaningful integer
            if isinstance(value, str) and old_type in (JsonType.BYTES, JsonType.ZLIB, JsonType.GZIP):

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
            if isinstance(value, NumberAffix):
                q = _to_mpq_or_none(value.number)
                if q is None:
                    return False, None
                return True, q
            temporal_epoch = _epoch_seconds_from_temporal(value, hinted_type=old_type, allow_expensive=allow_expensive)
            if temporal_epoch is not None:
                return True, temporal_epoch
            if _is_temporal_type(old_type):
                # Same safety rule as INTEGER for non-applicable temporal transitions.
                return (False, None) if strict else (True, stub_float())
            q = _to_mpq_or_none(value)
            if q is not None:
                return True, q
            return (False, None) if strict else (True, stub_float())

        case JsonType.PERCENT:
            v = _to_mpq_or_none(value)
            if v is not None and 0 <= v <= 1:
                return True, v
            return (False, None) if strict else (True, stub_percent())

        case JsonType.INTEGER_CURRENCY | JsonType.INTEGER_UNITS:
            kind = _affix_kind_for(json_type)
            if isinstance(value, str):
                parsed = parse_number_affix(value, max_affix_len=NUMBER_AFFIX_MAX_LEN, allow_expensive=allow_expensive)
                if parsed is not None:
                    truncated = _int_from_truncated(parsed.number)
                    if truncated is None:
                        return False, None
                    return True, _rebuild_affix(parsed, kind=kind, number=truncated)
            if isinstance(value, NumberAffix):
                truncated = _int_from_truncated(value.number)
                if truncated is None:
                    return False, None
                return True, _rebuild_affix(value, kind=kind, number=truncated)
            truncated = _int_from_truncated(value)
            if truncated is None:
                return (
                    (False, None)
                    if strict
                    else (True, NumberAffix(kind=kind, affix="", space=False, number=stub_integer()))
                )
            return True, NumberAffix(kind=kind, affix="", space=False, number=truncated)

        case JsonType.FLOAT_CURRENCY | JsonType.FLOAT_UNITS:
            kind = _affix_kind_for(json_type)
            if isinstance(value, str):
                parsed = parse_number_affix(value, max_affix_len=NUMBER_AFFIX_MAX_LEN, allow_expensive=allow_expensive)
                if parsed is not None:
                    q = _to_mpq_or_none(parsed.number)
                    if q is None:
                        return False, None
                    return True, _rebuild_affix(parsed, kind=kind, number=q)
            if isinstance(value, NumberAffix):
                q = _to_mpq_or_none(value.number)
                if q is None:
                    return False, None
                return True, _rebuild_affix(value, kind=kind, number=q)
            q = _to_mpq_or_none(value)
            if q is None:
                return (
                    (False, None)
                    if strict
                    else (True, NumberAffix(kind=kind, affix="", space=False, number=stub_float()))
                )
            return True, NumberAffix(kind=kind, affix="", space=False, number=q)

        # 3.1: bool → lowercase "true"/"false" instead of Python's "True"/"False"
        case _ if json_type in TEXT_FAMILY or json_type in (JsonType.SECRET_LINE, JsonType.SECRET_TEXT):
            if value is None:
                # Saint coercion: empty box of nothing → friendly placeholder.
                if strict:
                    return True, ""
                return True, stub_multiline() if json_type in TEXT_MULTI_FAMILY else stub_string()
            if isinstance(value, NumberAffix):
                try:
                    return True, format_number_affix(value)
                except ValueError:
                    # Transitional/incomplete affix values fall back to plain numeric text.
                    return True, str(value.number)
            if isinstance(value, bool):
                return True, "true" if value else "false"
            # Bytes-family → decode and surface the underlying text when printable.
            if isinstance(value, str) and old_type in (JsonType.BYTES, JsonType.ZLIB, JsonType.GZIP):

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
            if isinstance(value, mpq):
                return True, str(mpq_serialization(value)[0])
            return True, str(value)

        # 3.2: fall back to "now" instead of epoch-zero when value is unparseable
        case JsonType.DATE | JsonType.TIME | JsonType.DATETIME | JsonType.DATETIMEZONE | JsonType.DATETIMEUTC:
            parsed = _try_parse_temporal(json_type, value, allow_expensive=allow_expensive)
            if parsed is not None:
                return True, parsed
            return True, _now_for_type(json_type)

        # 3.4: encode-on-switch; use old_type for lossless cross-format re-encoding
        case JsonType.BYTES | JsonType.ZLIB | JsonType.GZIP:

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

        case JsonType.COLOR_RGB | JsonType.COLOR_RGBA:

            if isinstance(value, str):
                normalized = normalize_color_string(value, json_type)
                if normalized is not None:
                    return True, normalized
            stub = stub_color_rgba() if json_type is JsonType.COLOR_RGBA else stub_color_rgb()
            return (False, None) if strict else (True, stub)


def compute_editable(json_type: JsonType, value: Any, editable_blob_limit: int) -> bool:
    if isinstance(value, RawNumericValue):
        # Unsupported numeric literals are editable as plain raw text.
        return True

    if json_type in (JsonType.NULL, JsonType.ARRAY, JsonType.OBJECT):
        return False

    try:
        match json_type:
            case _ if json_type in TEXT_FAMILY or json_type in (JsonType.SECRET_LINE, JsonType.SECRET_TEXT):
                return True
            case JsonType.BYTES:
                base64.b64decode(value, validate=True)
                return True
            case JsonType.ZLIB:
                raw = base64.b64decode(value, validate=True)
                zlib.decompress(raw)
                return True
            case JsonType.GZIP:
                raw = base64.b64decode(value, validate=True)
                gzip.decompress(raw)
                return True
            case _:
                return True
    except (binascii.Error, zlib.error, OSError, ValueError, TypeError):
        return False
