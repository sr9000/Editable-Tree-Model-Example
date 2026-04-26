from gmpy2 import mpq

from delegates.bytes_codec import decode_bytes
from enums import JsonType
from mpq2py import mpq_serialization
from units import format_bytes


def format_default(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, mpq):
        return str(mpq_serialization(value)[0])
    if isinstance(value, bytes):
        return f"<{format_bytes(len(value))}>"
    if isinstance(value, str) and len(value) > 80:
        return value[:80] + "…"
    return str(value)


def format_with_type(value, json_type: JsonType | None) -> str:
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
