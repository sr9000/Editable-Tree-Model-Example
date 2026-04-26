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
    index = proxy_to_source(index)
    if not index.isValid():
        return ()
    if tab.model.show_root and tab.model.get_item(index) is tab.model.root_item:
        return ()
    path: list[int] = []
    cursor = index
    while cursor.isValid():
        path.append(cursor.row())
        cursor = cursor.parent()
    return tuple(reversed(path))


def index_from_path(tab, path: tuple[int, ...]) -> QModelIndex:
    if tab.model.show_root and not path:
        return tab.model.index(0, 0, QModelIndex())
    idx = QModelIndex()
    for row in path:
        nxt = tab.model.index(row, 0, idx)
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
