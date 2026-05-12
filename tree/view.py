"""QTreeView subclass that overrides ``startDrag`` so the model can fully
own internal moves without Qt's default post-drag selection removal.

Background
----------
Qt's ``QAbstractItemView::startDrag`` performs ``QDrag::exec(...)`` and,
if the result is ``Qt::MoveAction``, calls ``d->clearOrRemove()`` which
issues ``model->removeRows(...)`` against every currently-selected
contiguous range on the **source** view.

Our ``dropMimeData`` performs internal moves itself via
``tab.push_move_rows(...)``, which restructures the tree AND repositions
the selection to the destination rows. The default
``clearOrRemove()`` therefore tries to delete the freshly-placed
destination rows — visible to the user as "the dragged item
disappears" after a successful drop.

The fix is to skip ``clearOrRemove()`` whenever the drop was handled
internally (same model). For cross-model moves we still need to honour
``MoveAction`` semantics, so we manually delete the original source
selection — equivalent to Qt's default behaviour, but only when the
move was *not* handled internally.
"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QAbstractItemView, QTreeView


class JsonTreeView(QTreeView):
    """QTreeView that lets the model fully own internal drag-and-drop moves."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        # Set to True by ``tree_actions.dnd.handle_drop`` whenever an
        # internal move was handled by the model. Reset before each drag.
        self._drag_handled_internally = False

    # ------------------------------------------------------------------
    # Public flag used by the drop handler.
    # ------------------------------------------------------------------
    def mark_drag_handled_internally(self) -> None:
        self._drag_handled_internally = True

    # ------------------------------------------------------------------
    # QAbstractItemView overrides.
    # ------------------------------------------------------------------
    def startDrag(self, supported_actions: Qt.DropAction) -> None:  # type: ignore[override]
        self._drag_handled_internally = False

        sm = self.selectionModel()
        model = self.model()
        if sm is None or model is None:
            return

        # Collect drag-enabled column-0 indexes (one per row), matching
        # Qt's ``selectedDraggableIndexes`` semantics.
        seen: set[tuple[int, ...]] = set()
        indexes: list[QModelIndex] = []
        for idx in sm.selectedIndexes():
            if idx.column() != 0:
                continue
            if not (model.flags(idx) & Qt.ItemFlag.ItemIsDragEnabled):
                continue
            key = _index_signature(idx)
            if key in seen:
                continue
            seen.add(key)
            indexes.append(idx)

        if not indexes:
            return

        mime = model.mimeData(indexes)
        if mime is None:
            return

        drag = QDrag(self)
        drag.setMimeData(mime)

        default_action = Qt.DropAction.IgnoreAction
        view_default = self.defaultDropAction()
        if view_default != Qt.DropAction.IgnoreAction and (supported_actions & view_default):
            default_action = view_default
        elif (supported_actions & Qt.DropAction.CopyAction) and self.dragDropMode() != QAbstractItemView.DragDropMode.InternalMove:
            default_action = Qt.DropAction.CopyAction

        result = drag.exec(supported_actions, default_action)

        # Skip Qt's default ``clearOrRemove`` whenever our model already
        # performed the move internally. For cross-model MoveAction the
        # destination model only inserted entries via paste; the source
        # rows must still be removed here.
        if result == Qt.DropAction.MoveAction and not self._drag_handled_internally:
            self._remove_selected_source_rows()

        self._drag_handled_internally = False

    # ------------------------------------------------------------------
    # Helpers.
    # ------------------------------------------------------------------
    def _remove_selected_source_rows(self) -> None:
        sm = self.selectionModel()
        model = self.model()
        if sm is None or model is None:
            return

        # Remove bottom-up so earlier removals don't shift later rows.
        ranges = list(sm.selection())
        ranges.sort(
            key=lambda r: (_parent_signature(r.parent()), r.top()),
            reverse=True,
        )
        for r in ranges:
            parent = r.parent()
            if r.left() != 0:
                continue
            if r.right() != model.columnCount(parent) - 1:
                # Selection does not span the full row; skip to avoid
                # accidentally removing rows the user did not fully select.
                continue
            count = r.bottom() - r.top() + 1
            model.removeRows(r.top(), count, parent)


def _index_signature(index: QModelIndex) -> tuple[int, ...]:
    path: list[int] = []
    cursor = index
    while cursor.isValid():
        path.append(cursor.row())
        cursor = cursor.parent()
    return tuple(reversed(path))


def _parent_signature(parent: QModelIndex) -> tuple[int, ...]:
    return _index_signature(parent)
