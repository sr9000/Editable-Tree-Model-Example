"""Load text files into Python data for JsonTreeModel.

Secret kinds are not serialized as tagged values on disk. Reload relies on
name-based promotion in the tree model (and newline coercion) to classify
secret_line / secret_text again.
"""

from typing import Any

import simplejson
import yaml
from gmpy2 import mpq

from io_formats.detect import (
    SAVE_FORMAT_JSON,
    SAVE_FORMAT_JSONL,
    SAVE_FORMAT_YAML,
    SAVE_FORMAT_YAML_MULTI,
    detect_format,
)
from mpq2py import MpqSafeLoader
from settings import NUMBER_AFFIX_MAX_LEN
from units.number_affix import parse_number_affix


def _decode_number_affixes(value: Any) -> Any:
    if isinstance(value, str):
        parsed = parse_number_affix(value, max_affix_len=NUMBER_AFFIX_MAX_LEN)
        return parsed if parsed is not None else value
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
            return _decode_number_affixes(simplejson.load(fh, parse_float=mpq)), SAVE_FORMAT_JSON
        if fmt == SAVE_FORMAT_JSONL:
            rows = []
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                rows.append(_decode_number_affixes(simplejson.loads(stripped, parse_float=mpq)))
            return rows, SAVE_FORMAT_JSONL

        docs = [_decode_number_affixes(doc) for doc in yaml.load_all(fh, Loader=MpqSafeLoader)]
        if len(docs) <= 1:
            return (docs[0] if docs else {}), SAVE_FORMAT_YAML
        return docs, SAVE_FORMAT_YAML_MULTI
