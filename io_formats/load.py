"""Load text files into Python data for JsonTreeModel.

Secret kinds are not serialized as tagged values on disk. Reload relies on
name-based promotion in the tree model (and newline coercion) to classify
secret_line / secret_text again.
"""

from collections.abc import Callable
from typing import Any

import simplejson
import yaml

from core.raw_numeric import REASON_NON_FINITE, REASON_UNKNOWN, RawNumericValue
from core.safe_mpq import parse_mpq
from io_formats.detect import (
    SAVE_FORMAT_JSON,
    SAVE_FORMAT_JSONL,
    SAVE_FORMAT_YAML,
    SAVE_FORMAT_YAML_MULTI,
    detect_format,
)
from mpq2py import MpqSafeLoader
from settings import NUMBER_AFFIX_MAX_LEN
from tree.types import JsonType, parse_json_type
from units.number_affix import parse_number_affix

# Only these inferred types should cause a string to be promoted to a NumberAffix
# at load time. Other strings that happen to look like "<prefix><digits>" (colors
# such as "#ff0000", base64 blobs ending in digits, etc.) are classified to a
# different JsonType by parse_json_type and must be preserved as plain strings
# so that downstream type detection can pick the correct category.
_AFFIX_JSON_TYPES = frozenset(
    {
        JsonType.INTEGER_CURRENCY,
        JsonType.FLOAT_CURRENCY,
        JsonType.INTEGER_UNITS,
        JsonType.FLOAT_UNITS,
    }
)


def _safe_parse_float(text: str):
    """Parse a JSON float token into a safe ``mpq`` or a ``RawNumericValue``.

    Successful safe parses become exact rationals. Anything the safe parser
    rejects (overflow, underflow, non-finite, precision, format) is preserved
    verbatim as raw, editable text instead of constructing an unsafe value.
    """
    result = parse_mpq(text)
    if result.value is not None:
        return result.value
    return RawNumericValue(raw=text, reason=result.reason or REASON_UNKNOWN, source_syntax="json")


def _safe_parse_constant(name: str):
    """Preserve non-standard JSON constants (NaN / Infinity) as raw text."""
    return RawNumericValue(raw=name, reason=REASON_NON_FINITE, source_syntax="json")


def _decode_number_affixes(value: Any, on_progress: Callable[[int, str], None] | None = None) -> Any:
    """Decode NumberAffix-like strings with optional iterative progress callback."""

    processed = 0

    def _notify(path: str) -> None:
        nonlocal processed
        processed += 1
        if on_progress is not None:
            on_progress(processed, path)

    if isinstance(value, str):
        _notify("")
        return _maybe_decode_string(value)

    if not isinstance(value, (list, dict)):
        _notify("")
        return value

    root_result: Any = [None] * len(value) if isinstance(value, list) else {}
    stack: list[tuple[Any, Any, str, int, list[Any]]] = []
    stack.append((value, root_result, "", 0, _entries_for_container(value)))

    while stack:
        src_container, dst_container, parent_path, index, entries = stack[-1]
        if index >= len(entries):
            stack.pop()
            continue

        stack[-1] = (src_container, dst_container, parent_path, index + 1, entries)
        name, child_value = entries[index]
        child_path = _append_json_pointer(parent_path, name)
        _notify(child_path)

        if isinstance(child_value, str):
            decoded = _maybe_decode_string(child_value)
            _assign_container_value(dst_container, name, decoded)
            continue

        if isinstance(child_value, dict):
            child_result: dict[Any, Any] = {}
            _assign_container_value(dst_container, name, child_result)
            stack.append((child_value, child_result, child_path, 0, _entries_for_container(child_value)))
            continue

        if isinstance(child_value, list):
            child_result = [None] * len(child_value)
            _assign_container_value(dst_container, name, child_result)
            stack.append((child_value, child_result, child_path, 0, _entries_for_container(child_value)))
            continue

        _assign_container_value(dst_container, name, child_value)

    return root_result


def _maybe_decode_string(value: str) -> Any:
    # parse_json_type encodes the canonical priority of string heuristics
    # (multiline -> color -> datetime -> number-affix -> base64 -> text).
    # Only convert to NumberAffix when parse_json_type agrees the string is
    # actually a number-with-affix; otherwise leave it intact.
    if parse_json_type(value) in _AFFIX_JSON_TYPES:
        parsed = parse_number_affix(value, max_affix_len=NUMBER_AFFIX_MAX_LEN)
        if parsed is not None:
            return parsed
    return value


def _entries_for_container(value: Any) -> list[Any]:
    if isinstance(value, dict):
        return list(value.items())
    return list(enumerate(value))


def _assign_container_value(container: Any, key: Any, value: Any) -> None:
    if isinstance(container, list):
        container[key] = value
    else:
        container[key] = value


def _append_json_pointer(parent_path: str, segment: str | int) -> str:
    token = str(segment).replace("~", "~0").replace("/", "~1")
    if not parent_path:
        return f"/{token}"
    return f"{parent_path}/{token}"


def load_text_with_format(
    text: str,
    *,
    allow_scalar_yaml: bool = True,
    on_progress: Callable[[int, str], None] | None = None,
) -> tuple[Any, str] | tuple[None, None]:
    """Parse structured *text* using the same safe numeric rules as file load.

    JSON uses ``_safe_parse_float`` / ``_safe_parse_constant`` so unsupported
    numerics are preserved as ``RawNumericValue``. YAML uses ``MpqSafeLoader`` so
    float-like scalars follow the same preservation rules.

    When ``allow_scalar_yaml`` is False, bare YAML scalars are rejected and only
    mapping/list payloads are accepted. This matches clipboard semantics, where
    arbitrary plain text should not become paste-able structured data.
    """

    stripped = text.strip()
    if not stripped:
        return None, None

    try:
        return (
            _decode_number_affixes(
                simplejson.loads(
                    stripped,
                    parse_float=_safe_parse_float,
                    parse_constant=_safe_parse_constant,
                ),
                on_progress=on_progress,
            ),
            SAVE_FORMAT_JSON,
        )
    except Exception:
        pass

    try:
        docs = [
            _decode_number_affixes(doc, on_progress=on_progress)
            for doc in yaml.load_all(stripped, Loader=MpqSafeLoader)
        ]
    except Exception:
        return None, None

    if not docs:
        return None, None

    if len(docs) > 1:
        docs = [doc for doc in docs if isinstance(doc, (dict, list))]
        if not docs:
            return None, None
        return docs, SAVE_FORMAT_YAML_MULTI

    doc = docs[0]
    if not allow_scalar_yaml and not isinstance(doc, (dict, list)):
        return None, None
    return doc, SAVE_FORMAT_YAML


def load_file(path: str) -> Any:
    data, _fmt = load_file_with_format(path)
    return data


def load_file_with_format(
    path: str,
    on_progress: Callable[[int, str], None] | None = None,
) -> tuple[Any, str]:

    fmt = detect_format(path)
    with open(path, "r", encoding="utf-8") as fh:
        if fmt == SAVE_FORMAT_JSON:
            return (
                _decode_number_affixes(
                    simplejson.load(fh, parse_float=_safe_parse_float, parse_constant=_safe_parse_constant),
                    on_progress=on_progress,
                ),
                SAVE_FORMAT_JSON,
            )
        if fmt == SAVE_FORMAT_JSONL:
            rows = []
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                rows.append(
                    _decode_number_affixes(
                        simplejson.loads(stripped, parse_float=_safe_parse_float, parse_constant=_safe_parse_constant),
                        on_progress=on_progress,
                    )
                )
            return rows, SAVE_FORMAT_JSONL

        docs = [_decode_number_affixes(doc, on_progress=on_progress) for doc in yaml.load_all(fh, Loader=MpqSafeLoader)]
        if len(docs) <= 1:
            return (docs[0] if docs else {}), SAVE_FORMAT_YAML
        return docs, SAVE_FORMAT_YAML_MULTI
