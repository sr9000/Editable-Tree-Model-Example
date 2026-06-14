"""Hotspot registry for parsing vulnerability measurement.

Each entry maps a review hotspot to a single-string wrapper that can be called
with one adversarial string. The registry prevents each test from inventing a
different call shape.

Entry fields:
- name: Human-readable name for the entry.
- component: The module/function being tested.
- call: A callable that accepts a single string argument.
- notes: Additional context about the entry.
- is_decode_path: Whether this is a decode/decompress path (affects allocation caps).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class RegistryEntry:
    """A single hotspot registry entry."""

    name: str
    component: str
    call: Callable[[str], Any]
    notes: str
    is_decode_path: bool = False


# ---------------------------------------------------------------------------
# Import target functions
# ---------------------------------------------------------------------------

# Datetime parsing
from core.datetime_parsing import parse_datetime_text
from core.datetime_parsing.regex import DATETIME_RE

# Formatting and display
from delegates.formatting.value_formatting import format_with_type
from tree.codecs.bytes_codec import decode_bytes

# Item coercion (decode/decompress path)
from tree.item_coercion import compute_editable

# Central type inference
from tree.types import (
    JsonType,
    _looks_like_base64,
    infer_text_json_type,
    looks_like_color_rgb,
    looks_like_color_rgba,
    parse_json_type,
)

# Number affix parsing
from units.number_affix import _CURRENCY_RE, _UNITS_RE, parse_number_affix

# ---------------------------------------------------------------------------
# Wrapper functions
# ---------------------------------------------------------------------------


def _wrap_parse_json_type(text: str) -> JsonType:
    """Wrapper for parse_json_type with a string value."""
    return parse_json_type(text)


def _wrap_parse_datetime_text(text: str) -> Any:
    """Wrapper for parse_datetime_text."""
    return parse_datetime_text(text)


def _wrap_datetime_re_fullmatch(text: str) -> Any:
    """Wrapper for DATETIME_RE.fullmatch."""
    return DATETIME_RE.fullmatch(text)


def _wrap_parse_number_affix(text: str) -> Any:
    """Wrapper for parse_number_affix."""
    return parse_number_affix(text)


def _wrap_currency_re_fullmatch(text: str) -> Any:
    """Wrapper for _CURRENCY_RE.fullmatch."""
    return _CURRENCY_RE.fullmatch(text)


def _wrap_units_re_fullmatch(text: str) -> Any:
    """Wrapper for _UNITS_RE.fullmatch."""
    return _UNITS_RE.fullmatch(text)


def _wrap_looks_like_base64(text: str) -> bool:
    """Wrapper for _looks_like_base64."""
    return _looks_like_base64(text)


def _wrap_looks_like_color_rgb(text: str) -> bool:
    """Wrapper for looks_like_color_rgb."""
    return looks_like_color_rgb(text)


def _wrap_looks_like_color_rgba(text: str) -> bool:
    """Wrapper for looks_like_color_rgba."""
    return looks_like_color_rgba(text)


def _wrap_infer_text_json_type(text: str) -> JsonType:
    """Wrapper for infer_text_json_type."""
    return infer_text_json_type(text)


def _wrap_compute_editable_bytes(text: str) -> bool:
    """Wrapper for compute_editable with BYTES type."""
    return compute_editable(JsonType.BYTES, text, editable_blob_limit=1024 * 1024)


def _wrap_compute_editable_zlib(text: str) -> bool:
    """Wrapper for compute_editable with ZLIB type."""
    return compute_editable(JsonType.ZLIB, text, editable_blob_limit=1024 * 1024)


def _wrap_compute_editable_gzip(text: str) -> bool:
    """Wrapper for compute_editable with GZIP type."""
    return compute_editable(JsonType.GZIP, text, editable_blob_limit=1024 * 1024)


def _wrap_format_with_type_string(text: str) -> str:
    """Wrapper for format_with_type with STRING type."""
    return format_with_type(text, JsonType.STRING)


def _wrap_format_with_type_bytes(text: str) -> str:
    """Wrapper for format_with_type with BYTES type."""
    return format_with_type(text, JsonType.BYTES)


def _wrap_decode_bytes(text: str) -> bytes:
    """Wrapper for decode_bytes with BYTES type."""
    return decode_bytes(text, JsonType.BYTES)


# ---------------------------------------------------------------------------
# Registry definition
# ---------------------------------------------------------------------------

HOTSPOT_REGISTRY: list[RegistryEntry] = [
    # Central type inference
    RegistryEntry(
        name="parse_json_type",
        component="tree.types.parse_json_type",
        call=_wrap_parse_json_type,
        notes="Central automatic inference dispatcher for string values.",
    ),
    # Datetime parsing
    RegistryEntry(
        name="parse_datetime_text",
        component="core.datetime_parsing.parse_datetime_text",
        call=_wrap_parse_datetime_text,
        notes="Datetime regex and conversion path.",
    ),
    RegistryEntry(
        name="DATETIME_RE.fullmatch",
        component="core.datetime_parsing.regex.DATETIME_RE",
        call=_wrap_datetime_re_fullmatch,
        notes="Direct regex fullmatch for datetime pattern.",
    ),
    # Number affix parsing
    RegistryEntry(
        name="parse_number_affix",
        component="units.number_affix.parse_number_affix",
        call=_wrap_parse_number_affix,
        notes="Number-affix detection with currency and units patterns.",
    ),
    RegistryEntry(
        name="_CURRENCY_RE.fullmatch",
        component="units.number_affix._CURRENCY_RE",
        call=_wrap_currency_re_fullmatch,
        notes="Direct regex fullmatch for currency prefix pattern.",
    ),
    RegistryEntry(
        name="_UNITS_RE.fullmatch",
        component="units.number_affix._UNITS_RE",
        call=_wrap_units_re_fullmatch,
        notes="Direct regex fullmatch for units suffix pattern.",
    ),
    # Base64 detection
    RegistryEntry(
        name="_looks_like_base64",
        component="tree.types._looks_like_base64",
        call=_wrap_looks_like_base64,
        notes="Base64 syntactic check and decode probe.",
        is_decode_path=True,
    ),
    # Color detection
    RegistryEntry(
        name="looks_like_color_rgb",
        component="tree.types.looks_like_color_rgb",
        call=_wrap_looks_like_color_rgb,
        notes="Color regex check for RGB format (#RGB or #RRGGBB).",
    ),
    RegistryEntry(
        name="looks_like_color_rgba",
        component="tree.types.looks_like_color_rgba",
        call=_wrap_looks_like_color_rgba,
        notes="Color regex check for RGBA format (#RGBA or #RRGGBBAA).",
    ),
    # Text inference
    RegistryEntry(
        name="infer_text_json_type",
        component="tree.types.infer_text_json_type",
        call=_wrap_infer_text_json_type,
        notes="Text fallback checks including multiline, whitespace, and unicode detection.",
    ),
    # Decode/decompress paths
    RegistryEntry(
        name="compute_editable(BYTES)",
        component="tree.item_coercion.compute_editable",
        call=_wrap_compute_editable_bytes,
        notes="Decode path for BYTES type during item coercion.",
        is_decode_path=True,
    ),
    RegistryEntry(
        name="compute_editable(ZLIB)",
        component="tree.item_coercion.compute_editable",
        call=_wrap_compute_editable_zlib,
        notes="Decompress path for ZLIB type during item coercion.",
        is_decode_path=True,
    ),
    RegistryEntry(
        name="compute_editable(GZIP)",
        component="tree.item_coercion.compute_editable",
        call=_wrap_compute_editable_gzip,
        notes="Decompress path for GZIP type during item coercion.",
        is_decode_path=True,
    ),
    # Formatting and display
    RegistryEntry(
        name="format_with_type(STRING)",
        component="delegates.formatting.value_formatting.format_with_type",
        call=_wrap_format_with_type_string,
        notes="Paint-time display preview for STRING type.",
    ),
    RegistryEntry(
        name="format_with_type(BYTES)",
        component="delegates.formatting.value_formatting.format_with_type",
        call=_wrap_format_with_type_bytes,
        notes="Paint-time display preview for BYTES type (includes decode).",
        is_decode_path=True,
    ),
    RegistryEntry(
        name="decode_bytes",
        component="tree.codecs.bytes_codec.decode_bytes",
        call=_wrap_decode_bytes,
        notes="Direct decode for BYTES type.",
        is_decode_path=True,
    ),
]


def get_registry_entry(name: str) -> RegistryEntry | None:
    """Get a registry entry by name, or None if not found."""
    for entry in HOTSPOT_REGISTRY:
        if entry.name == name:
            return entry
    return None


def get_registry_names() -> list[str]:
    """Get all registry entry names."""
    return [entry.name for entry in HOTSPOT_REGISTRY]
