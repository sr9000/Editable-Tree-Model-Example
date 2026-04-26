import os
from pathlib import Path
from typing import Any

import simplejson
import yaml
from gmpy2 import mpq

from mpq2py import MpqSafeDumper, MpqSafeLoader, mpq_json_default

SAVE_FORMAT_JSON = "json"
SAVE_FORMAT_YAML = "yaml"
SAVE_FORMAT_YAML_MULTI = "yaml-multi"
SAVE_FORMAT_JSONL = "jsonl"


def detect_format(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".json":
        return SAVE_FORMAT_JSON
    if ext in (".jsonl", ".ndjson"):
        return SAVE_FORMAT_JSONL
    if ext in (".yaml", ".yml"):
        return SAVE_FORMAT_YAML
    raise ValueError(f"Unknown file format: {ext}")


def load_file(path: str) -> Any:
    data, _fmt = load_file_with_format(path)
    return data


def load_file_with_format(path: str) -> tuple[Any, str]:
    fmt = detect_format(path)
    with open(path, "r", encoding="utf-8") as fh:
        if fmt == SAVE_FORMAT_JSON:
            return simplejson.load(fh, parse_float=mpq), SAVE_FORMAT_JSON
        if fmt == SAVE_FORMAT_JSONL:
            rows = []
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                rows.append(simplejson.loads(stripped, parse_float=mpq))
            return rows, SAVE_FORMAT_JSONL

        docs = list(yaml.load_all(fh, Loader=MpqSafeLoader))
        if len(docs) <= 1:
            return (docs[0] if docs else {}), SAVE_FORMAT_YAML
        return docs, SAVE_FORMAT_YAML_MULTI


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
