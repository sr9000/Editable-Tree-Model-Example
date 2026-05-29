from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from PySide6.QtCore import QObject

from documents.tab import JsonTab
from validation.schema_registry import SchemaSource, get_schema_registry


class SchemaPoolTabWidgetProtocol(Protocol):
    def indexOf(self, widget: QObject) -> int: ...

    def setCurrentIndex(self, index: int) -> None: ...

    def count(self) -> int: ...

    def widget(self, index: int) -> QObject | None: ...

    def setTabText(self, index: int, text: str) -> None: ...

    def setTabToolTip(self, index: int, text: str) -> None: ...


class SchemaPoolWindowProtocol(Protocol):
    tabWidget: SchemaPoolTabWidgetProtocol

    def _open_path(self, path: str) -> bool: ...

    def _current_tab(self) -> JsonTab | None: ...

    def _add_tab(
        self, *, data=None, file_path: str | None = None, save_format: str | None = None
    ) -> JsonTab | None: ...


class _RegistryBorrower:
    __slots__ = ("__weakref__",)


class SchemaTabPool(QObject):
    """Identity-based pool that keeps one open schema tab per SchemaSource."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._tabs_by_source: dict[SchemaSource, JsonTab] = {}
        self._source_by_tab: dict[JsonTab, SchemaSource] = {}
        self._registry_token = _RegistryBorrower()

    def find(self, source: SchemaSource) -> JsonTab | None:
        tab = self._tabs_by_source.get(source)
        if tab is None:
            return None
        if tab.parent() is None:
            self.unregister(tab)
            return None
        return tab

    def register(self, tab: JsonTab, source: SchemaSource, *, read_only: bool) -> None:
        existing = self.find(source)
        if existing is not None and existing is not tab:
            self.unregister(existing)

        previous_source = self._source_by_tab.get(tab)
        if previous_source is not None and previous_source != source:
            if previous_source in self._tabs_by_source:
                self._tabs_by_source.pop(previous_source)

        self._tabs_by_source[source] = tab
        self._source_by_tab[tab] = source
        tab.set_read_only(read_only)
        tab.validation.set_schema_view_source(source)

        tab.destroyed.connect(lambda *_args, t=tab: self.unregister(t))

    def unregister(self, tab: JsonTab) -> None:
        source = self._source_by_tab.pop(tab, None)
        if source is None:
            return
        if self._tabs_by_source.get(source) is tab:
            self._tabs_by_source.pop(source, None)

    def open_or_focus(self, window: SchemaPoolWindowProtocol, source: SchemaSource) -> JsonTab | None:
        tab = self.find(source)
        if tab is not None:
            index = window.tabWidget.indexOf(tab)
            if index >= 0:
                window.tabWidget.setCurrentIndex(index)
            return tab

        if source.kind == "file":
            tab = self._find_open_file_tab(window, source)
            if tab is not None:
                self.register(tab, source, read_only=False)
                index = window.tabWidget.indexOf(tab)
                if index >= 0:
                    window.tabWidget.setCurrentIndex(index)
                return tab

            if not window._open_path(source.key):
                return None
            tab = window._current_tab()
            if tab is None:
                return None
            self.register(tab, source, read_only=False)
            return tab

        # URL-backed schema viewers are opened from registry materialized data.
        entry = get_schema_registry().lookup(source)
        acquired_here = False
        if entry is None:
            entry = get_schema_registry().acquire(source, self._registry_token)
            acquired_here = True
        if entry is None:
            return None

        inline = entry.inline if isinstance(entry.inline, Mapping) else None
        data: dict[str, Any] = dict(inline) if inline is not None else {}

        tab = window._add_tab(data=data, file_path=None)
        if tab is None:
            if acquired_here:
                get_schema_registry().release(source, self._registry_token)
            return None

        self.register(tab, source, read_only=True)
        self._apply_url_tab_title(window, tab, source)

        if acquired_here:
            get_schema_registry().release(source, self._registry_token)
        return tab

    @staticmethod
    def _find_open_file_tab(window: SchemaPoolWindowProtocol, source: SchemaSource) -> JsonTab | None:
        resolved = str(Path(source.key).expanduser().resolve())
        for i in range(window.tabWidget.count()):
            widget = window.tabWidget.widget(i)
            if not isinstance(widget, JsonTab):
                continue
            if widget.file_path and str(Path(widget.file_path).expanduser().resolve()) == resolved:
                return widget
        return None

    @staticmethod
    def _apply_url_tab_title(window: SchemaPoolWindowProtocol, tab: JsonTab, source: SchemaSource) -> None:
        idx = window.tabWidget.indexOf(tab)
        if idx < 0:
            return
        window.tabWidget.setTabText(idx, source.display)
        window.tabWidget.setTabToolTip(idx, source.key)
