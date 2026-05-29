"""Viewport controller for a :class:`documents.tab.JsonTab`.

Centralises selection / expansion / scroll reads and writes for one
``JsonTreeView`` so callers outside ``documents/`` never touch the
QTreeView directly. Writes are buffered through the
:attr:`DocumentView.viewportRequested` signal so non-Qt-aware
producers (notably undo command implementations) can ask the viewport
to act without importing or holding references to the widget itself.

See ``plans/20-decouple-jsontab.md`` Phase D (D1).
"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QObject, Signal

# Note: the constructor's ``tab`` parameter is documented to be a
# ``documents.tab.JsonTab`` but is not statically typed here because
# importing JsonTab eagerly would create a circular import (JsonTab
# itself imports DocumentView).


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


class DocumentView(QObject):
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
        return self._tab._index_path(idx)

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
            path = self._tab._index_path(idx)
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
        source_index = self._tab._index_from_path(path)
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
