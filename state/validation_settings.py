from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtCore import QSettings

from settings import APPLICATION_ID


def _settings() -> QSettings:
    return QSettings(APPLICATION_ID, "validation")


def _schema_key(doc_path: Path) -> str:
    """Return a stable QSettings key for *doc_path*.

    The key is ``validation/<sha1[:16]>`` keyed off the resolved absolute path,
    matching the pattern used by ``state.view_state.state_key``.
    """
    resolved = str(doc_path.expanduser().resolve())
    digest = hashlib.sha1(resolved.encode("utf-8")).hexdigest()[:16]
    return f"validation/{digest}"


def read_schema_path(doc_path: Path) -> Path | None:
    """Return the last manually attached schema path for *doc_path*, or ``None``.

    Returns ``None`` if the persisted binding is a URL (use
    ``read_schema_ref_str`` to retrieve URLs as well).
    """
    raw = read_schema_ref_str(doc_path)
    if raw is not None and not _is_url(raw):
        return Path(raw)
    return None


def read_schema_ref_str(doc_path: Path) -> str | None:
    """Return the raw persisted binding (path string or URL) for *doc_path*."""
    raw = _settings().value(_schema_key(doc_path))
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def _is_url(value: str) -> bool:
    lo = value.lower()
    return lo.startswith("http://") or lo.startswith("https://")


def write_schema_path(doc_path: Path, schema_path: Path) -> None:
    """Persist the manual schema binding for *doc_path* (file path variant)."""
    write_schema_ref_str(doc_path, str(schema_path))


def write_schema_url(doc_path: Path, url: str) -> None:
    """Persist the manual schema binding for *doc_path* (URL variant)."""
    write_schema_ref_str(doc_path, url)


def write_schema_ref_str(doc_path: Path, ref_str: str) -> None:
    """Persist *ref_str* (path or URL) as the schema binding for *doc_path*."""
    _settings().setValue(_schema_key(doc_path), ref_str)


def clear_schema_path(doc_path: Path) -> None:
    """Remove the persisted schema binding for *doc_path*.

    Called when the user explicitly clears the schema or when the document is
    saved to a new path (``Save As``), mirroring ``state.view_state.discard``.
    """
    _settings().remove(_schema_key(doc_path))


_AUTO_RESCAN_KEY = "validation/auto_rescan"


def auto_rescan_enabled() -> bool:
    """Return the persisted auto-rescan setting (default ``False``)."""
    raw = _settings().value(_AUTO_RESCAN_KEY, False)
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().casefold() in {"1", "true", "yes", "on"}
    return False


def set_auto_rescan_enabled(enabled: bool) -> None:
    """Persist the auto-rescan setting."""
    _settings().setValue(_AUTO_RESCAN_KEY, bool(enabled))
