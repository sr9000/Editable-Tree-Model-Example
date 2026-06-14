"""Selection, path, and viewport controller for a document tree view."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QModelIndex, QObject, QPersistentModelIndex, QSortFilterProxyModel, QTimer, Signal

from tree.types import JsonType

# ``tab`` stays loosely typed here to avoid a circular import with ``documents.tab``.

# Plain string tags keep signal payloads simple for tests and logging.
KIND_SELECT_PATHS = "select"
KIND_EXPAND_PATH = "expand"
KIND_EXPAND_ALL = "expand_all"
KIND_COLLAPSE_ALL = "collapse_all"
KIND_SCROLL_TO = "scroll"


class ViewController(QObject):
    """Controller for selection, expansion, scrolling, and path mapping."""

    viewportRequested = Signal(str, object)
    """Signal carrying ``(kind, payload)`` viewport mutation requests."""

    def __init__(self, tab: "JsonTab") -> None:
        super().__init__(tab)
        self._tab = tab

    @property
    def widget(self):
        """Return the underlying tree view."""
        return self._tab.view_state.view

    @property
    def proxy(self):
        """Return the proxy wrapping the model."""
        return self._tab.view_state.proxy

    @property
    def search_edit(self):
        """Return the search/filter line edit."""
        return self._tab.view_state.search_edit

    @property
    def ui(self):
        """Return the generated UI object."""
        return self._tab.view_state.ui

    @property
    def name_delegate(self):
        """Return the name-column delegate."""
        return self._tab.view_state.name_delegate

    @property
    def type_delegate(self):
        """Return the type-column delegate."""
        return self._tab.view_state.type_delegate

    @property
    def value_delegate(self):
        """Return the value-column delegate."""
        return self._tab.view_state.value_delegate

    @property
    def _model(self):
        return self._tab.model

    def set_filter_text(self, text: str) -> None:
        """Push ``text`` straight to the proxy filter."""
        self._tab.view_state.proxy.set_filter_text(text)

    def apply_filter(self) -> None:
        """Re-apply the search edit's current text to the proxy filter."""
        self._tab.view_state.proxy.set_filter_text(self._tab.view_state.search_edit.text())

    def column_widths(self) -> list[int]:
        """Return the current widths of all model columns."""
        view = self._tab.view_state.view
        model = self._tab.model
        return [int(view.columnWidth(c)) for c in range(model.columnCount())]

    def set_column_widths(self, widths: list[int]) -> None:
        """Restore previously saved column widths."""
        model = self._tab.model
        view = self._tab.view_state.view
        for column, width in enumerate(widths[: model.columnCount()]):
            if width > 0:
                view.setColumnWidth(column, width)
        self._tab.appearance.user_sized_columns.update(c for c in (0, 1) if c < len(widths) and widths[c] > 0)

    @staticmethod
    def proxy_to_source(index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
        src = QModelIndex(index) if isinstance(index, QPersistentModelIndex) else index
        model = src.model()
        if isinstance(model, QSortFilterProxyModel):
            return model.mapToSource(src)
        return src

    def source_to_view(self, source_index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
        src = QModelIndex(source_index) if isinstance(source_index, QPersistentModelIndex) else source_index
        model = self._tab.view_state.view.model()
        if isinstance(model, QSortFilterProxyModel):
            return model.mapFromSource(src)
        return src

    def index_path(self, index: QModelIndex) -> tuple[int, ...]:
        """Return a stable path for ``index`` relative to ``root_item``."""
        index = self.proxy_to_source(index)
        if not index.isValid():
            return ()
        model = self._tab.model
        root_item = model.root_item
        if model.get_item(index) is root_item:
            return ()
        path: list[int] = []
        cursor = index
        while cursor.isValid() and model.get_item(cursor) is not root_item:
            path.append(cursor.row())
            cursor = cursor.parent()
        return tuple(reversed(path))

    def index_from_path(self, path: tuple[int | None, ...] | None) -> QModelIndex:
        """Return the source index reached by walking ``path`` from ``root_item``."""
        if path is None:
            return QModelIndex()
        model = self._tab.model
        if model.show_root:
            root_idx = model.index(0, 0, QModelIndex())
            if not path:
                return root_idx
            idx = root_idx
        else:
            if not path:
                return QModelIndex()
            idx = QModelIndex()
        for row in path:
            if not isinstance(row, int) or row < 0:
                return QModelIndex()
            nxt = model.index(row, 0, idx)
            if not nxt.isValid():
                return QModelIndex()
            idx = nxt
        return idx

    def qualified_name(self, index: QModelIndex) -> str:
        """Return a JSON-style qualified path of *index* (e.g. ``$.foo.bar[2].baz``)."""
        index = self.proxy_to_source(index)
        if not index.isValid():
            return "$"
        model = self._tab.model
        item = model.get_item(index)
        if item is model.root_item:
            return "$"
        chain: list[tuple[JsonType | None, Any]] = []
        cursor = model.index(index.row(), 0, index.parent())
        while cursor.isValid():
            item = model.get_item(cursor)
            parent_item = item.parent() if item is not None else None
            parent_type = parent_item.json_type if parent_item is not None else None
            chain.append((parent_type, item))
            cursor = cursor.parent()
        chain.reverse()
        parts: list[str] = ["$"]
        for parent_type, item in chain:
            if parent_type is JsonType.ARRAY:
                parts.append(f"[{item.row()}]")
            else:
                name = item.name if isinstance(item.name, str) and item.name else "<no name>"
                parts.append(f".{name}")
        return "".join(parts)

    def has_current(self) -> bool:
        """Return whether the selection has a valid current index."""
        sm = self._tab.view.selectionModel()
        return sm is not None and sm.currentIndex().isValid()

    def current_path(self) -> tuple[int, ...] | None:
        """Return the path of the current index, or ``None`` if none."""
        sm = self._tab.view.selectionModel()
        if sm is None:
            return None
        idx = sm.currentIndex()
        if not idx.isValid():
            return None
        return self.index_path(idx)

    def selected_paths(self) -> list[tuple[int, ...]]:
        """Return distinct paths for every selected row, preserving order."""
        sm = self._tab.view.selectionModel()
        if sm is None:
            return []
        seen: set[tuple[int, ...]] = set()
        result: list[tuple[int, ...]] = []
        for idx in sm.selectedRows(0):
            if not idx.isValid():
                continue
            path = self.index_path(idx)
            if path in seen:
                continue
            seen.add(path)
            result.append(path)
        return result

    def request_select_paths(self, paths: list[tuple[int, ...]]) -> None:
        """Ask the viewport to select ``paths``."""
        if not paths:
            return
        self.viewportRequested.emit(KIND_SELECT_PATHS, list(paths))

    def request_select_paths_deferred(self, paths: list[tuple[int, ...]]) -> None:
        """Queue ``request_select_paths`` for the next event-loop turn."""
        if not paths:
            return
        queued = list(paths)
        QTimer.singleShot(0, lambda: self.request_select_paths(queued))

    def request_expand(self, path: tuple[int, ...]) -> None:
        """Ask the viewport to expand ``path``."""
        self.viewportRequested.emit(KIND_EXPAND_PATH, tuple(path))

    def request_expand_all(self) -> None:
        """Ask the viewport to expand all nodes."""
        self.viewportRequested.emit(KIND_EXPAND_ALL, None)

    def request_collapse_all(self) -> None:
        """Ask the viewport to collapse all nodes."""
        self.viewportRequested.emit(KIND_COLLAPSE_ALL, None)

    def request_scroll_to(self, path: tuple[int, ...]) -> None:
        """Ask the viewport to scroll ``path`` into view."""
        self.viewportRequested.emit(KIND_SCROLL_TO, tuple(path))

    def request_scroll_to_deferred(self, path: tuple[int, ...]) -> None:
        """Queue ``request_scroll_to`` for the next event-loop turn."""
        queued = tuple(path)
        QTimer.singleShot(0, lambda: self.request_scroll_to(queued))

    def apply_request(self, kind: str, payload: object) -> None:
        """Apply a queued viewport request to the tree view."""
        view = self._tab.view
        if view is None:
            return
        if kind == KIND_SELECT_PATHS:
            self._apply_select(payload)
        elif kind == KIND_EXPAND_PATH:
            self._apply_expand(payload)
        elif kind == KIND_EXPAND_ALL:
            view.expandAll()
        elif kind == KIND_COLLAPSE_ALL:
            view.collapseAll()
        elif kind == KIND_SCROLL_TO:
            self._apply_scroll(payload)
        # Unknown kinds are silently ignored; the signal contract is
        # closed (only this controller emits) so an unknown value is a
        # programming error rather than a runtime concern.

    def _path_to_view_index(self, path: tuple[int, ...]) -> QModelIndex:
        source_index = self.index_from_path(path)
        if not source_index.isValid():
            return QModelIndex()
        return self._tab.mutations.source_to_view(source_index)

    def _apply_select(self, payload: object) -> None:
        if not isinstance(payload, list) or not payload:
            return
        view = self._tab.view
        first_view_index = self._path_to_view_index(payload[0])
        if not first_view_index.isValid():
            return
        view.setCurrentIndex(first_view_index)
        # Multi-select extension is intentionally minimal: undo callers
        # restore exactly one selection; if a future caller needs an
        # extended selection it can call selectionModel() via the
        # controller's read API instead.

    def _apply_expand(self, payload: object) -> None:
        if not isinstance(payload, tuple):
            return
        view_index = self._path_to_view_index(payload)
        if view_index.isValid():
            self._tab.view.expand(view_index)

    def _apply_scroll(self, payload: object) -> None:
        if not isinstance(payload, tuple):
            return
        view_index = self._path_to_view_index(payload)
        if view_index.isValid():
            self._tab.view.scrollTo(view_index)
