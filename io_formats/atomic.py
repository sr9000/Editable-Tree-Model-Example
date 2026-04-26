import os
from typing import Any

from io_formats.dump import dump_text


def atomic_write(path: str, text: str) -> None:
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp_path, path)


def save_file(path: str, data: Any, save_format: str | None = None) -> None:
    atomic_write(path, dump_text(path, data, save_format=save_format))
