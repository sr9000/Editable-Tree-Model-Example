from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from weakref import WeakSet

from PySide6.QtCore import QFileSystemWatcher, QObject, QUrl, Signal
from PySide6.QtGui import QDesktopServices

from state.recent_schemas import push_recent_schema
from validation.schema_source import load_schema
from validation.schema_types import SchemaRef, SchemaSource

_LOG = logging.getLogger(__name__)


def open_in_browser(source: "SchemaSource") -> bool:
    if source.kind != "url":
        return False
    return bool(QDesktopServices.openUrl(QUrl(source.key)))


@dataclass(slots=True)
class SchemaEntry:
    source: SchemaSource
    inline: dict[str, Any]
    mtime_ns: int | None
    ref_count: int = 0
    bound_tabs: WeakSet[object] = field(default_factory=WeakSet, repr=False)


class SchemaRegistry(QObject):
    schemaReloaded = Signal(object)  # SchemaSource

    def __init__(self) -> None:
        super().__init__()
        self._entries: dict[SchemaSource, SchemaEntry] = {}
        self._bound_tabs: dict[SchemaSource, WeakSet[object]] = {}
        self._watcher: QFileSystemWatcher | None = None
        self._file_sources_by_path: dict[str, SchemaSource] = {}

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
                inline=dict(loaded),
                mtime_ns=self._file_mtime_ns(source),
            )
            self._entries[source] = entry
            self._bound_tabs[source] = entry.bound_tabs

        tabs = self._bound_tabs.setdefault(source, entry.bound_tabs)
        if tab not in tabs:
            tabs.add(tab)
            entry.ref_count += 1
            if source.kind == "file":
                self._watch_file_source(source)
        push_recent_schema(source)
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
            if source.kind == "file":
                self._unwatch_file_source(source)
            self._entries.pop(source, None)
            self._bound_tabs.pop(source, None)

    def reload(self, source: SchemaSource) -> SchemaEntry | None:
        entry = self._entries.get(source)
        if entry is None:
            return None

        loaded = self._load_for_source(source)
        if loaded is None:
            return None

        entry.inline.clear()
        entry.inline.update(loaded)
        entry.mtime_ns = self._file_mtime_ns(source)
        self.schemaReloaded.emit(source)
        push_recent_schema(source)
        return entry

    def lookup(self, source: SchemaSource) -> SchemaEntry | None:
        return self._entries.get(source)

    def all_entries(self) -> list[SchemaEntry]:
        return list(self._entries.values())

    def exists(self, source: SchemaSource) -> bool:
        if source.kind == "url":
            return True
        path = Path(source.key)
        return path.exists() and path.is_file()

    def _load_for_source(self, source: SchemaSource) -> dict[str, Any] | None:
        if source.kind == "file":
            ref = SchemaRef(path=Path(source.key), inline=None, origin="manual")
        else:
            ref = SchemaRef(path=None, inline=None, origin="manual", url=source.key)
        loaded = load_schema(ref)
        if not isinstance(loaded, Mapping):
            return None
        return dict(loaded)

    def _ensure_watcher(self) -> QFileSystemWatcher:
        if self._watcher is None:
            self._watcher = QFileSystemWatcher(self)
            self._watcher.fileChanged.connect(self._on_file_changed)
        return self._watcher

    def _watch_file_source(self, source: SchemaSource) -> None:
        watcher = self._ensure_watcher()
        path = source.key
        self._file_sources_by_path[path] = source
        if path not in watcher.files():
            watcher.addPath(path)

    def _unwatch_file_source(self, source: SchemaSource) -> None:
        path = source.key
        self._file_sources_by_path.pop(path, None)
        if self._watcher is not None and path in self._watcher.files():
            self._watcher.removePath(path)

    def _on_file_changed(self, path: str) -> None:
        source = self._file_sources_by_path.get(path)
        if source is None:
            return

        entry = self._entries.get(source)
        if entry is None:
            return

        mtime_ns = self._file_mtime_ns(source)
        if mtime_ns == entry.mtime_ns:
            return

        if mtime_ns is None:
            _LOG.warning("Schema file changed but is unreadable: %s", path)
            return

        loaded = self._load_for_source(source)
        if loaded is None:
            _LOG.warning("Schema file changed but reload failed: %s", path)
            return

        # Some backends drop watch paths after a change; re-arm when needed.
        if self._watcher is not None and path not in self._watcher.files():
            self._watcher.addPath(path)

        entry.inline.clear()
        entry.inline.update(loaded)
        entry.mtime_ns = mtime_ns
        self.schemaReloaded.emit(source)

    @staticmethod
    def _file_mtime_ns(source: SchemaSource) -> int | None:
        if source.kind != "file":
            return None
        try:
            return Path(source.key).stat().st_mtime_ns
        except OSError:
            return None


schema_registry = SchemaRegistry()


def get_schema_registry() -> SchemaRegistry:
    return schema_registry
