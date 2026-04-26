import os
from pathlib import Path
from typing import Any

import simplejson
import yaml
from gmpy2 import mpq

from mpq2py import MpqSafeDumper, MpqSafeLoader, mpq_json_default


def detect_format(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".json":
        return "json"
    if ext in (".yaml", ".yml"):
        return "yaml"
    raise ValueError(f"Unknown file format: {ext}")


def load_file(path: str) -> Any:
    fmt = detect_format(path)
    with open(path, "r", encoding="utf-8") as fh:
        if fmt == "json":
            return simplejson.load(fh, parse_float=mpq)
        return yaml.load(fh, Loader=MpqSafeLoader)


def dump_text(path: str, data: Any) -> str:
    fmt = detect_format(path)
    if fmt == "json":
        return simplejson.dumps(data, default=mpq_json_default, indent=2, use_decimal=True) + "\n"
    return yaml.dump(data, Dumper=MpqSafeDumper, sort_keys=False, allow_unicode=True)


def atomic_write(path: str, text: str) -> None:
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp_path, path)


def save_file(path: str, data: Any) -> None:
    atomic_write(path, dump_text(path, data))
