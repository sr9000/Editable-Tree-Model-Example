from PySide6.QtCore import QModelIndex, QSortFilterProxyModel
from PySide6.QtWidgets import QTreeView

from tree.model import JsonTreeModel


def _resolve_model(tree_view: QTreeView) -> tuple[JsonTreeModel | None, QSortFilterProxyModel | None]:
    model = tree_view.model()
    if isinstance(model, JsonTreeModel):
        return model, None
    if isinstance(model, QSortFilterProxyModel) and isinstance(model.sourceModel(), JsonTreeModel):
        return model.sourceModel(), model
    return None, None


def _to_source_index(index: QModelIndex) -> QModelIndex:
    model = index.model()
    if isinstance(model, QSortFilterProxyModel):
        return model.mapToSource(index)
    return index


def _to_view_index(tree_view: QTreeView, index: QModelIndex) -> QModelIndex:
    _source_model, proxy = _resolve_model(tree_view)
    if proxy is None:
        return index
    return proxy.mapFromSource(index)


def _index_path(index) -> tuple[int, ...]:
    path: list[int] = []
    cursor = index
    while cursor.isValid():
        path.append(cursor.row())
        cursor = cursor.parent()
    return tuple(reversed(path))


def _is_ancestor(ancestor, index) -> bool:
    parent = index.parent()
    while parent.isValid():
        if parent == ancestor:
            return True
        parent = parent.parent()
    return False


def _selected_rows(tree_view: QTreeView) -> list:
    source_model, _proxy = _resolve_model(tree_view)
    if source_model is None:
        return []

    selection = tree_view.selectionModel()
    if selection is None:
        return []

    rows = selection.selectedRows(0)
    if rows:
        return [_to_source_index(idx) for idx in rows]

    current = selection.currentIndex()
    if not current.isValid():
        return []
    source_current = _to_source_index(current)
    return [source_model.index(source_current.row(), 0, source_current.parent())]


def _top_level_selected_rows(tree_view: QTreeView) -> list:
    rows = [idx for idx in _selected_rows(tree_view) if idx.isValid()]
    return [idx for idx in rows if not any(_is_ancestor(other, idx) for other in rows if other != idx)]


# Public API (promoted from private names)
def selected_source_rows(tree_view: QTreeView) -> list:
    """Return source-model indexes for every selected row (or the current row)."""
    return _selected_rows(tree_view)


def top_level_source_rows(tree_view: QTreeView) -> list:
    """Return source-model indexes pruned so no index is a descendant of another."""
    return _top_level_selected_rows(tree_view)


def selection_spans_multiple_parents(rows: list) -> bool:
    """Return True when *rows* contains indexes with more than one distinct parent."""
    if not rows:
        return False
    first_parent = rows[0].parent()
    return any(idx.parent() != first_parent for idx in rows[1:])


def _row0(model: JsonTreeModel, index: QModelIndex) -> QModelIndex:
    if not index.isValid():
        return QModelIndex()
    return model.index(index.row(), 0, index.parent())


def _is_root_index(model: JsonTreeModel, index: QModelIndex) -> bool:
    return bool(index.isValid() and model.get_item(index) is model.root_item)
