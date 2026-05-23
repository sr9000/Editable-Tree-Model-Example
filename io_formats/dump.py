"""Serialize Python data to JSON/YAML text.

Secret kinds are emitted as plain strings (no encryption or sidecar marker).
On load, classification is restored only when name heuristics match.
"""

from typing import Any

import simplejson
import yaml

from io_formats.detect import (
    SAVE_FORMAT_JSON,
    SAVE_FORMAT_JSONL,
    SAVE_FORMAT_YAML,
    SAVE_FORMAT_YAML_MULTI,
    detect_format,
)
from mpq2py import MpqSafeDumper, mpq_json_default
from units.number_affix import NumberAffix, format_number_affix


def _encode_number_affixes(value: Any) -> Any:
    if isinstance(value, NumberAffix):
        return format_number_affix(value)
    if isinstance(value, list):
        return [_encode_number_affixes(v) for v in value]
    if isinstance(value, dict):
        return {k: _encode_number_affixes(v) for k, v in value.items()}
    return value


def dump_text(path: str, data: Any, save_format: str | None = None) -> str:
    fmt = save_format or detect_format(path)
    data = _encode_number_affixes(data)
    if fmt == SAVE_FORMAT_JSON:
        return simplejson.dumps(data, default=mpq_json_default, indent=2, use_decimal=True) + "\n"
    if fmt == SAVE_FORMAT_JSONL:
        rows = data if isinstance(data, list) else [data]
        return "\n".join(simplejson.dumps(row, default=mpq_json_default, use_decimal=True) for row in rows) + "\n"
    if fmt == SAVE_FORMAT_YAML_MULTI:
        docs = data if isinstance(data, list) else [data]
        return yaml.dump_all(docs, Dumper=MpqSafeDumper, sort_keys=False, allow_unicode=True)
    if fmt == SAVE_FORMAT_YAML:
        return yaml.dump(data, Dumper=MpqSafeDumper, sort_keys=False, allow_unicode=True)
    raise ValueError(f"Unknown save format: {fmt}")
