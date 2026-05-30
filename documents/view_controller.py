"""View controller for a :class:`documents.tab.JsonTab`.

Centralises selection / expansion / scroll reads and writes for one
``JsonTreeView`` so callers outside ``documents/`` never touch the
QTreeView directly. Writes are buffered through the
:attr:`ViewController.viewportRequested` signal so non-Qt-aware
producers (notably undo command implementations) can ask the viewport
to act without importing or holding references to the widget itself.

Plan 21 Phase M promoted this from the selection-only ``DocumentView``
into a full ``ViewController`` that also owns the proxy/source path
helpers (formerly ``documents.tab_paths``) and the search-filter glue.

See ``plans/20-decouple-jsontab.md`` Phase D (D1) and
``plans/21-promote-substates-to-controllers.md`` Phase M (M1).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QModelIndex, QObject, QPersistentModelIndex, QSortFilterProxyModel, Signal

from tree.types import JsonType

# Note: the constructor's ``tab`` parameter is documented to be a
# ``documents.tab.JsonTab`` but is not statically typed here because
# importing JsonTab eagerly would create a circular import (JsonTab
# itself imports ViewController).


# Kind tags carried by ``viewportRequested``. Kept as module-level
# string constants (rather than a true enum) because the receiver in
# ``tab_init`` switches on them with a small if-chain and the values
# also appear in test assertions / log messages where a plain string
# is friendlier than an enum repr.
KIND_SELECT_PATHS = "select"
KIND_EXPAND_PATH = "expand"
KIND_EXPAND_ALL = "expand_all"
KIND_COLLAPSE_ALL = "collapse_all"
KIND_SCROLL_TO = "scroll"


class ViewController(QObject):
    """Selection / expansion / scroll controller for one ``JsonTreeView``.

    Reads (``current_path``, ``selected_paths``, ``has_current``) are
    synchronous and return path tuples relative to ``root_item``.

    Writes (``request_select_paths``, ``request_expand``,
    ``request_expand_all``, ``request_scroll_to``) emit
    ``viewportRequested`` which the owning tab wires to a slot that
    performs the action on the real ``QTreeView``. Consumers must not
    rely on the write being applied synchronously — callers that need
    to inspect the post-condition should listen for the appropriate
    Qt signal (e.g. ``selectionChanged``) or refetch on the next
    event-loop turn.
    """

    viewportRequested = Signal(str, object)
    """``(kind, payload)`` notification of a viewport mutation request.

    ``kind`` is one of the ``KIND_*`` constants in this module.
    ``payload`` is:
      * for ``KIND_SELECT_PATHS``: ``list[tuple[int, ...]]`` (non-empty)
      * for ``KIND_EXPAND_PATH``:  ``tuple[int, ...]``
      * for ``KIND_EXPAND_ALL``:   ``None``
      * for ``KIND_SCROLL_TO``:    ``tuple[int, ...]``
    """

    def __init__(self, tab: "JsonTab") -> None:
        super().__init__(tab)
        self._tab = tab

    # ------------------------------------------------------------------
    # Widget accessors (the view axis owns the QTreeView / proxy / search
    # edit; storage still lives on ``ViewState`` until Phase P).
    # ------------------------------------------------------------------

    @property
    def widget(self):
        """The underlying :class:`tree.view.JsonTreeView`."""
        return self._tab.data_store.view

    @property
    def proxy(self):
        """The :class:`tree_filter_proxy.TreeFilterProxy` wrapping the model."""
        return self._tab.data_store.proxy

    @property
    def search_edit(self):
        """The search/filter ``QLineEdit``."""
        return self._tab.data_store.search_edit

    @property
    def _model(self):
        return self._tab.data_store.model

    # ------------------------------------------------------------------
    # Search filter
    # ------------------------------------------------------------------

    def set_filter_text(self, text: str) -> None:
        """Push *text* straight to the proxy filter."""
        self._tab.data_store.proxy.set_filter_text(text)

    def apply_filter(self) -> None:
        """Re-apply the search edit's current text to the proxy filter."""
        self._tab.data_store.proxy.set_filter_text(self._tab.data_store.search_edit.text())

    # ------------------------------------------------------------------
    # Proxy <-> source <-> view index mapping (was documents/tab_paths.py)
    # ------------------------------------------------------------------

    @staticmethod
    def proxy_to_source(index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
        src = QModelIndex(index) if isinstance(index, QPersistentModelIndex) else index
        model = src.model()
        if isinstance(model, QSortFilterProxyModel):
            return model.mapToSource(src)
        return src

    def source_to_view(self, source_index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
        src = QModelIndex(source_index) if isinstance(source_index, QPersistentModelIndex) else source_index
        model = self._tab.data_store.view.model()
        if isinstance(model, QSortFilterProxyModel):
            return model.mapFromSource(src)
        return src

    def index_path(self, index: QModelIndex) -> tuple[int, ...]:
        """Return a stable, parent-relative path for *index*.

        Convention: paths are **always relative to ``root_item``** — the
        synthetic root row that ``show_root=True`` exposes is implicit and
        NEVER appears in returned paths. So:

        - ``root_item`` itself → ``()``
        - first child of root_item → ``(0,)``
        - grand-child at root_item.child(2).child(1) → ``(2, 1)``

        This convention matches :meth:`index_from_path`, which always starts
        its walk at ``root_item`` (regardless of ``show_root``).
        """
        index = self.proxy_to_source(index)
        if not index.isValid():
            return ()
        model = self._tab.data_store.model
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
        """Inverse of :meth:`index_path` — walk *path* starting at root_item."""
        if path is None:
            return QModelIndex()
        model = self._tab.data_store.model
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
        model = self._tab.data_store.model
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

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def has_current(self) -> bool:
        """Return True iff the underlying selection has a valid current index."""
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

    # ------------------------------------------------------------------
    # Writes (signal-mediated)
    # ------------------------------------------------------------------

    def request_select_paths(self, paths: list[tuple[int, ...]]) -> None:
        """Ask the viewport to make *paths* the current selection.

        The first entry becomes the current index; the rest are added to
        the selection. No-op when *paths* is empty.
        """
        if not paths:
            return
        self.viewportRequested.emit(KIND_SELECT_PATHS, list(paths))

    def request_expand(self, path: tuple[int, ...]) -> None:
        """Ask the viewport to expand the node at *path*."""
        self.viewportRequested.emit(KIND_EXPAND_PATH, tuple(path))

    def request_expand_all(self) -> None:
        """Ask the viewport to expand every node."""
        self.viewportRequested.emit(KIND_EXPAND_ALL, None)

    def request_collapse_all(self) -> None:
        """Ask the viewport to collapse every node."""
        self.viewportRequested.emit(KIND_COLLAPSE_ALL, None)

    def request_scroll_to(self, path: tuple[int, ...]) -> None:
        """Ask the viewport to scroll the node at *path* into view."""
        self.viewportRequested.emit(KIND_SCROLL_TO, tuple(path))

    # ------------------------------------------------------------------
    # Apply (consumed by JsonTab's wiring; not part of the public API
    # for callers outside ``documents/``)
    # ------------------------------------------------------------------

    def apply_request(self, kind: str, payload: object) -> None:
        """Handle a ``viewportRequested`` emission on the QTreeView.

        Wired by :func:`documents.tab_init.bootstrap` to the signal.
        Public-but-internal: tests reach in to assert behaviour, but
        callers outside ``documents/`` should not invoke this directly.
        """
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
