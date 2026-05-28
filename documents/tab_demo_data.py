from __future__ import annotations

import base64
import gzip
import zlib
from typing import Any

import gmpy2


def build_demo_data() -> dict[str, Any]:
    """Default sample document used when ``JsonTab`` is constructed without data."""
    return {
        "question": "The Ultimate Question of Life, the Universe, and Everything.",
        "answer": 42,
        "integer": 9223372036854775808,
        "int units": "10 m/s",
        "float units": "3.45s",
        "int currency": "$10",
        "float currency": "lvl 2.5",
        "float": gmpy2.mpq("3.14"),
        "percent": gmpy2.mpq("50/100"),
        "single-line": "Hello, world!" * 100,
        "utf8-line": "caf\u00e9",
        "multi-line": "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\nLine 6",
        "utf8-text": "Line 1\nLine 2\n\u03a9",
        "password": "plainsecret",
        "private_key": "-----BEGIN KEY-----\nabc\n-----END KEY-----",
        "bytes": base64.b64encode(b"hello " * 10).decode(),
        "zlib": base64.b64encode(zlib.compress(b"hello " * 10)).decode(),
        "gzip": base64.b64encode(gzip.compress(b"hello " * 10)).decode(),
        "date": "2024-06-01",
        "time": "12:34",
        "datetime": "2024-06-01 12:34:56",
        "datetime-utc": "2024-06-01T12:34:56Z",
        "dt+timezone": "2024-06-01T12:34:56.9999+00:00",
        "boolean": True,
        "object": {"key": "value"},
        "array": [1, 2, 3],
        "null": None,
        "color rgb": "#3498db",
        "color rgba": "#3498db80",
        # Pseudo text types — content-derived labels that appear automatically
        # when a string value is empty or whitespace-only.
        "empty string": "",  # → EMPTY_STRING
        "ws ascii": "   ",  # → WS_STRING (ASCII spaces only)
        "ws unicode": " \u00a0 ",  # → WS_UNICODE (includes NBSP)
        "ws multiline": "  \n  ",  # → WS_MULTILINE (whitespace + newline)
        "ws text": " \u00a0\n ",  # → WS_TEXT  (non-ASCII WS + newline)
    }
