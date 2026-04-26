import os
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
from io_formats.load import load_file, load_file_with_format
from mpq2py import MpqSafeDumper, mpq_json_default


def dump_text(path: str, data: Any, save_format: str | None = None) -> str:
    fmt = save_format or detect_format(path)
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


def atomic_write(path: str, text: str) -> None:
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp_path, path)


def save_file(path: str, data: Any, save_format: str | None = None) -> None:
    atomic_write(path, dump_text(path, data, save_format=save_format))
