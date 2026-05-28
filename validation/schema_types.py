from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit


@dataclass(frozen=True, slots=True)
class SchemaRef:
    path: Path | None
    inline: Mapping[str, Any] | None
    origin: Literal["inline", "sibling", "manual", "none"]
    url: str | None = field(default=None)


def _normalize_url(raw_url: str) -> str:
    text = raw_url.strip()
    parts = urlsplit(text)
    scheme = parts.scheme.lower()
    path = parts.path.rstrip("/")
    return urlunsplit((scheme, parts.netloc, path, parts.query, parts.fragment))


def _display_for_url(normalized_url: str) -> str:
    parts = urlsplit(normalized_url)
    host = parts.hostname or parts.netloc
    if not host:
        return normalized_url
    path = parts.path.strip("/")
    if not path:
        return host
    tail = path.split("/")[-1]
    return f"{host}/{tail}"


@dataclass(frozen=True, slots=True)
class SchemaSource:
    kind: Literal["file", "url"]
    key: str
    display: str

    @classmethod
    def for_file(cls, path: Path) -> "SchemaSource":
        resolved = path.expanduser().resolve()
        display = resolved.name or str(resolved)
        return cls(kind="file", key=str(resolved), display=display)

    @classmethod
    def for_url(cls, url: str) -> "SchemaSource":
        key = _normalize_url(url)
        return cls(kind="url", key=key, display=_display_for_url(key))

    @classmethod
    def from_ref(cls, ref: SchemaRef) -> "SchemaSource | None":
        if ref.path is not None:
            return cls.for_file(ref.path)
        if ref.url is not None and ref.url.strip():
            return cls.for_url(ref.url)
        return None

    def as_ref(self, *, origin: Literal["inline", "sibling", "manual", "none"] = "manual") -> SchemaRef:
        if self.kind == "file":
            return SchemaRef(path=Path(self.key), inline=None, origin=origin)
        return SchemaRef(path=None, inline=None, origin=origin, url=self.key)
