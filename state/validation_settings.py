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


# ---------------------------------------------------------------------------
# Global auto-rescan toggle
# ---------------------------------------------------------------------------

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
