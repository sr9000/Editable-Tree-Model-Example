from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

from settings import APPLICATION_ID
from state.validation_settings import _RECENT_SCHEMAS_KEY

RECENT_SCHEMAS_CAP = 12


def _settings() -> QSettings:
    return QSettings(APPLICATION_ID, "validation")


def _schema_source_cls():
    from validation.schema_types import SchemaSource

    return SchemaSource


def _serialize(source: SchemaSource) -> str:
    return f"{source.kind}:{source.key}"


def _deserialize(raw: object) -> SchemaSource | None:
    schema_source_cls = _schema_source_cls()

    if not isinstance(raw, str):
        return None
    kind, sep, payload = raw.partition(":")
    payload = payload.strip()
    if not sep or not payload:
        return None

    if kind == "file":
        return schema_source_cls.for_file(Path(payload))
    if kind == "url":
        return schema_source_cls.for_url(payload)
    return None


def push_recent_schema(source: SchemaSource) -> None:
    """Move *source* to the front of the recents list (cap 12)."""
    serialized = _serialize(source)
    current = [_serialize(item) for item in recent_schemas()]
    updated = [serialized] + [item for item in current if item != serialized]
    _settings().setValue(_RECENT_SCHEMAS_KEY, updated[:RECENT_SCHEMAS_CAP])


def recent_schemas() -> list[SchemaSource]:
    """Return most-recent-first persisted schema sources.

    Malformed entries are silently dropped.
    """
    raw = _settings().value(_RECENT_SCHEMAS_KEY, [], type=list)
    if isinstance(raw, str):
        candidates = [raw]
    elif isinstance(raw, list):
        candidates = raw
    else:
        candidates = []

    entries: list[SchemaSource] = []
    seen_serialized: set[str] = set()
    for candidate in candidates:
        parsed = _deserialize(candidate)
        if parsed is None:
            continue
        serialized = _serialize(parsed)
        if serialized in seen_serialized:
            continue
        seen_serialized.add(serialized)
        entries.append(parsed)
    return entries


def clear_recent_schemas() -> None:
    _settings().remove(_RECENT_SCHEMAS_KEY)
