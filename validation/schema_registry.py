from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit
from weakref import WeakSet

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QDesktopServices

from validation.schema_source import SchemaRef, load_schema


def open_in_browser(source: "SchemaSource") -> bool:
    if source.kind != "url":
        return False
    return bool(QDesktopServices.openUrl(QUrl(source.key)))


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


@dataclass(slots=True)
class SchemaEntry:
    source: SchemaSource
    inline: Mapping[str, Any]
    mtime_ns: int | None
    ref_count: int = 0
    bound_tabs: WeakSet[object] = field(default_factory=WeakSet, repr=False)


class SchemaRegistry(QObject):
    schemaReloaded = Signal(object)  # SchemaSource

    def __init__(self) -> None:
        super().__init__()
        self._entries: dict[SchemaSource, SchemaEntry] = {}
        self._bound_tabs: dict[SchemaSource, WeakSet[object]] = {}

    def acquire(
        self,
        source: SchemaSource,
        tab: object,
        *,
        inline_hint: Mapping[str, Any] | None = None,
    ) -> SchemaEntry | None:
        entry = self._entries.get(source)
        if entry is None:
            loaded = inline_hint if inline_hint is not None else self._load_for_source(source)
            if loaded is None:
                return None
            entry = SchemaEntry(
                source=source,
                inline=loaded,
                mtime_ns=self._file_mtime_ns(source),
            )
            self._entries[source] = entry
            self._bound_tabs[source] = entry.bound_tabs

        tabs = self._bound_tabs.setdefault(source, entry.bound_tabs)
        if tab not in tabs:
            tabs.add(tab)
            entry.ref_count += 1
        return entry

    def acquire_ref(self, ref: SchemaRef, tab: object) -> tuple[SchemaSource | None, SchemaEntry | None]:
        source = SchemaSource.from_ref(ref)
        if source is None:
            return None, None
        inline_hint = ref.inline if isinstance(ref.inline, Mapping) else None
        return source, self.acquire(source, tab, inline_hint=inline_hint)

    def release(self, source: SchemaSource, tab: object) -> None:
        entry = self._entries.get(source)
        if entry is None:
            return

        tabs = self._bound_tabs.get(source)
        if tabs is not None and tab in tabs:
            tabs.remove(tab)
            if entry.ref_count > 0:
                entry.ref_count -= 1

        if entry.ref_count == 0:
            self._entries.pop(source, None)
            self._bound_tabs.pop(source, None)

    def reload(self, source: SchemaSource) -> SchemaEntry | None:
        entry = self._entries.get(source)
        if entry is None:
            return None

        loaded = self._load_for_source(source)
        if loaded is None:
            return None

        entry.inline = loaded
        entry.mtime_ns = self._file_mtime_ns(source)
        self.schemaReloaded.emit(source)
        return entry

    def lookup(self, source: SchemaSource) -> SchemaEntry | None:
        return self._entries.get(source)

    def all_entries(self) -> list[SchemaEntry]:
        return list(self._entries.values())

    def _load_for_source(self, source: SchemaSource) -> Mapping[str, Any] | None:
        if source.kind == "file":
            ref = SchemaRef(path=Path(source.key), inline=None, origin="manual")
        else:
            ref = SchemaRef(path=None, inline=None, origin="manual", url=source.key)
        loaded = load_schema(ref)
        if not isinstance(loaded, Mapping):
            return None
        return loaded

    @staticmethod
    def _file_mtime_ns(source: SchemaSource) -> int | None:
        if source.kind != "file":
            return None
        try:
            return Path(source.key).stat().st_mtime_ns
        except OSError:
            return None


schema_registry = SchemaRegistry()
