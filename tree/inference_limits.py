"""Length-gate helpers for expensive type inference (Plan 1).

Each ``*_inference_allowed`` helper returns ``True`` when the text is short
enough to run the corresponding expensive branch, or when ``allow_expensive``
is ``True`` (explicit user type change bypasses the gate).

``base64_syntax_valid`` is a content-based syntax check (not a length gate):
it returns ``True`` when the text has valid base64 structure (length mod 4
and alphabet-only characters). No bypass flag is needed because this is a
correctness check, not a performance gate.

``format_preview_decode_allowed`` caps paint-time decode work for display
previews. No bypass flag: previews are always capped.

This module imports only ``settings`` and standard-library modules.
"""

import re

from settings import (
    FORMAT_PREVIEW_DECODE_LIMIT_BYTES,
    INFERENCE_MAX_AFFIX_CHARS,
    INFERENCE_MAX_COLOR_CHARS,
    INFERENCE_MAX_DATETIME_CHARS,
)

# Base64 alphabet regex: A-Z, a-z, 0-9, +, /, with optional = padding.
# The * quantifier allows empty strings (handled by len % 4 check).
_B64_ALPHABET_RE = re.compile(r"^[A-Za-z0-9+/]*={0,2}$")


def datetime_inference_allowed(text: str, *, allow_expensive: bool = False) -> bool:
    """Return True if datetime regex work is allowed for *text*.

    Returns True when ``len(text) <= INFERENCE_MAX_DATETIME_CHARS`` or
    ``allow_expensive`` is True.
    """
    if allow_expensive:
        return True
    return len(text) <= INFERENCE_MAX_DATETIME_CHARS


def affix_inference_allowed(text: str, *, allow_expensive: bool = False) -> bool:
    """Return True if number-affix regex work is allowed for *text*.

    Returns True when ``len(text) <= INFERENCE_MAX_AFFIX_CHARS`` or
    ``allow_expensive`` is True.
    """
    if allow_expensive:
        return True
    return len(text) <= INFERENCE_MAX_AFFIX_CHARS


def color_inference_allowed(text: str, *, allow_expensive: bool = False) -> bool:
    """Return True if color regex work is allowed for *text*.

    Returns True when ``len(text) <= INFERENCE_MAX_COLOR_CHARS`` or
    ``allow_expensive`` is True.
    """
    if allow_expensive:
        return True
    return len(text) <= INFERENCE_MAX_COLOR_CHARS


def base64_syntax_valid(text: str) -> bool:
    """Return True if *text* has valid base64 syntax.

    Checks:
    1. ``len(text) % 4 == 0`` (base64 encoding always produces length
       divisible by 4).
    2. Text matches the base64 alphabet regex
       ``^[A-Za-z0-9+/]*={0,2}$`` (no whitespace or other invalid chars).

    This is a content validation, not a length gate. No bypass flag.
    """
    if not text:
        return False
    if len(text) % 4 != 0:
        return False
    return _B64_ALPHABET_RE.fullmatch(text) is not None


def format_preview_decode_allowed(byte_count: int) -> bool:
    """Return True if decode work is allowed for a display preview.

    Returns True when ``byte_count <= FORMAT_PREVIEW_DECODE_LIMIT_BYTES``.
    No bypass flag: previews are always capped.
    """
    return byte_count <= FORMAT_PREVIEW_DECODE_LIMIT_BYTES
