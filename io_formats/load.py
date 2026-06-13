"""Load text files into Python data for JsonTreeModel.

Secret kinds are not serialized as tagged values on disk. Reload relies on
name-based promotion in the tree model (and newline coercion) to classify
secret_line / secret_text again.
"""

from typing import Any
from decimal import Decimal, InvalidOperation

import simplejson
import yaml

from core.frozen_value import FrozenValue
from core.safe_mpq import safe_mpq_from_text
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
    parsed = safe_mpq_from_text(text)
    if parsed is not None:
        return parsed

    # Keep invalid-literal classification for direct callers/tests while
    # avoiding binary-float parsing semantics.
    candidate = text.replace("_", "").strip()
    try:
        d = Decimal(candidate)
    except InvalidOperation:
        return FrozenValue(raw=text, reason="json-float-invalid")
    if not d.is_finite():
        return FrozenValue(raw=text, reason="json-float-invalid")

    return FrozenValue(raw=text, reason="json-float-overflow")


def _decode_number_affixes(value: Any) -> Any:
    if isinstance(value, str):
        # parse_json_type encodes the canonical priority of string heuristics
        # (multiline -> color -> datetime -> number-affix -> base64 -> text).
        # Only convert to NumberAffix when parse_json_type agrees the string is
        # actually a number-with-affix; otherwise leave it intact.
        if parse_json_type(value) in _AFFIX_JSON_TYPES:
            parsed = parse_number_affix(value, max_affix_len=NUMBER_AFFIX_MAX_LEN)
            if parsed is not None:
                return parsed
        return value
    if isinstance(value, list):
        return [_decode_number_affixes(v) for v in value]
    if isinstance(value, dict):
        return {k: _decode_number_affixes(v) for k, v in value.items()}
    return value


def load_file(path: str) -> Any:
    data, _fmt = load_file_with_format(path)
    return data


def load_file_with_format(path: str) -> tuple[Any, str]:

    fmt = detect_format(path)
    with open(path, "r", encoding="utf-8") as fh:
        if fmt == SAVE_FORMAT_JSON:
            return _decode_number_affixes(simplejson.load(fh, parse_float=_safe_parse_float)), SAVE_FORMAT_JSON
        if fmt == SAVE_FORMAT_JSONL:
            rows = []
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                rows.append(_decode_number_affixes(simplejson.loads(stripped, parse_float=_safe_parse_float)))
            return rows, SAVE_FORMAT_JSONL

        docs = [_decode_number_affixes(doc) for doc in yaml.load_all(fh, Loader=MpqSafeLoader)]
        if len(docs) <= 1:
            return (docs[0] if docs else {}), SAVE_FORMAT_YAML
        return docs, SAVE_FORMAT_YAML_MULTI
