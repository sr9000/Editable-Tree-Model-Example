from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from io_formats.load import load_file_with_format


@dataclass(frozen=True, slots=True)
class SchemaRef:
    path: Path | None
    inline: Mapping[str, Any] | None
    origin: Literal["inline", "sibling", "manual", "none"]
    url: str | None = field(default=None)


def schema_source_from_ref(ref: SchemaRef):
    """Convert a SchemaRef into a SchemaSource when possible."""
    from validation.schema_registry import SchemaSource

    return SchemaSource.from_ref(ref)


def _is_remote_ref(value: str) -> bool:
    lowered = value.strip().lower()
    return lowered.startswith("http://") or lowered.startswith("https://")


def _resolve_local_schema_path(doc_path: Path | None, raw_ref: str) -> Path | None:
    candidate = Path(raw_ref).expanduser()
    if not candidate.is_absolute():
        if doc_path is None:
            return None
        candidate = (doc_path.parent / candidate).resolve()
    if candidate.exists() and candidate.is_file():
        return candidate
    return None


def _sibling_schema_path(doc_path: Path | None) -> Path | None:
    if doc_path is None:
        return None
    if doc_path.suffix:
        sibling = doc_path.with_suffix(".schema.json")
    else:
        sibling = Path(str(doc_path) + ".schema.json")
    if sibling.exists() and sibling.is_file():
        return sibling
    return None


def load_schema_from_url(url: str, *, timeout: int = 10) -> Mapping[str, Any] | None:
    """Fetch a JSON/YAML schema from *url* and return it as a mapping."""
    import urllib.request

    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            raw = resp.read()
    except Exception:
        return None

    # Try JSON first, then YAML
    try:
        data = json.loads(raw)
        if isinstance(data, Mapping):
            return data
        return None
    except Exception:
        pass

    try:
        import yaml

        data = yaml.safe_load(raw)
        if isinstance(data, Mapping):
            return data
        return None
    except Exception:
        return None


def load_schema(ref: SchemaRef) -> Mapping[str, Any] | None:
    if ref.inline is not None:
        return ref.inline
    if ref.url is not None:
        return load_schema_from_url(ref.url)
    if ref.path is None:
        return None
    data, _fmt = load_file_with_format(str(ref.path))
    if isinstance(data, Mapping):
        return data
    return None


def discover_schema(doc_path: Path | None, data: Any) -> SchemaRef:
    resolved_doc = doc_path.expanduser().resolve() if doc_path is not None else None

    if isinstance(data, Mapping):
        raw_ref = data.get("$schema")
        if isinstance(raw_ref, str) and raw_ref.strip() and not _is_remote_ref(raw_ref):
            local_path = _resolve_local_schema_path(resolved_doc, raw_ref)
            if local_path is not None:
                schema_ref = SchemaRef(path=local_path, inline=None, origin="inline")
                loaded = load_schema(schema_ref)
                if loaded is not None:
                    return SchemaRef(path=local_path, inline=loaded, origin="inline")

    sibling = _sibling_schema_path(resolved_doc)
    if sibling is not None:
        schema_ref = SchemaRef(path=sibling, inline=None, origin="sibling")
        loaded = load_schema(schema_ref)
        if loaded is not None:
            return SchemaRef(path=sibling, inline=loaded, origin="sibling")

    return SchemaRef(path=None, inline=None, origin="none")
