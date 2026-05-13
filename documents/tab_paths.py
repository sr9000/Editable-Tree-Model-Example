from typing import Any

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QSortFilterProxyModel

from tree.types import JsonType


def proxy_to_source(index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
    src = QModelIndex(index) if isinstance(index, QPersistentModelIndex) else index
    model = src.model()
    if isinstance(model, QSortFilterProxyModel):
        return model.mapToSource(src)
    return src


def source_to_view(tab, source_index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
    src = QModelIndex(source_index) if isinstance(source_index, QPersistentModelIndex) else source_index
    model = tab.view.model()
    if isinstance(model, QSortFilterProxyModel):
        return model.mapFromSource(src)
    return src


def index_path(tab, index: QModelIndex) -> tuple[int, ...]:
    """Return a stable, parent-relative path for *index*.

    Convention: paths are **always relative to ``root_item``** — the
    synthetic root row that ``show_root=True`` exposes is implicit and
    NEVER appears in returned paths. So:

    - ``root_item`` itself → ``()``
    - first child of root_item → ``(0,)``
    - grand-child at root_item.child(2).child(1) → ``(2, 1)``

    This convention matches :func:`index_from_path`, which always starts
    its walk at ``root_item`` (regardless of ``show_root``). Without it
    the anchor-based move code captures source parents and anchor
    targets in two different coordinate systems and corrupts the tree
    on every drop under ``show_root=True``.
    """
    index = proxy_to_source(index)
    if not index.isValid():
        return ()
    root_item = tab.model.root_item
    if tab.model.get_item(index) is root_item:
        return ()
    path: list[int] = []
    cursor = index
    while cursor.isValid() and tab.model.get_item(cursor) is not root_item:
        path.append(cursor.row())
        cursor = cursor.parent()
    return tuple(reversed(path))


def index_from_path(tab, path: tuple[int | None, ...] | None) -> QModelIndex:
    """Inverse of :func:`index_path` — walk *path* starting at root_item.

    Always descends from ``root_item`` regardless of ``show_root``. When
    ``show_root=False`` we still start at the (invalid) QModelIndex that
    Qt uses for root_item's children; when ``show_root=True`` we first
    materialise root_item's index so that the path entries align with
    the underlying ``child_items`` list.
    """
    if path is None:
        return QModelIndex()
    model = tab.model
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


def qualified_name(tab, index: QModelIndex) -> str:
    """Return a JSON-style qualified path of *index* (e.g. ``$.foo.bar[2].baz``)."""
    index = proxy_to_source(index)
    if not index.isValid():
        return "$"

    item = tab.model.get_item(index)
    if item is tab.model.root_item:
        return "$"

    chain: list[tuple[JsonType | None, Any]] = []
    cursor = tab.model.index(index.row(), 0, index.parent())
    while cursor.isValid():
        item = tab.model.get_item(cursor)
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
