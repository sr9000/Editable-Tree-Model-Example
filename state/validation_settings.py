from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

from settings import APPLICATION_ID


def _settings() -> QSettings:
    return QSettings(APPLICATION_ID, "validation")


def _schema_key(doc_path: Path) -> str:
    return f"validation/schema/{doc_path.expanduser().resolve()}"


def read_schema_path(doc_path: Path) -> Path | None:
    raw = _settings().value(_schema_key(doc_path))
    if isinstance(raw, str) and raw.strip():
        return Path(raw.strip())
    return None


def write_schema_path(doc_path: Path, schema_path: Path) -> None:
    _settings().setValue(_schema_key(doc_path), str(schema_path))
