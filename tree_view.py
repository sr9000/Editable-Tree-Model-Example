from __future__ import annotations

from jsontream import StreamingJSONEncoderWrapper


def to_json(item):
    encoder = StreamingJSONEncoderWrapper(separators=(",", ":"), indent=2)
    source = item.to_json() if hasattr(item, "to_json") else item
    return "".join(encoder.iterencode(source))
