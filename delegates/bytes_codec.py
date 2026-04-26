import base64
import gzip
import zlib

from enums import JsonType


def decode_bytes(b64string: str, json_type: JsonType) -> bytes:
    # Prepare binary data for hex editor
    raw = base64.b64decode(b64string, validate=True) if b64string else b""

    match json_type:  # Decompress if needed
        case JsonType.ZLIB:
            return zlib.decompress(raw)
        case JsonType.GZIP:
            return gzip.decompress(raw)
        case _:
            return raw


def encode_bytes(edited_data: bytes, json_type: JsonType) -> str:
    # Compress if needed before encoding
    match json_type:
        case JsonType.ZLIB:
            edited_data = zlib.compress(edited_data)
        case JsonType.GZIP:
            edited_data = gzip.compress(edited_data)

    return base64.b64encode(edited_data).decode("ascii")
