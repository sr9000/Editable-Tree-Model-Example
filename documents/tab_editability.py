from __future__ import annotations

from PySide6.QtWidgets import QAbstractItemView

from documents.tab_data import JsonTabData
from tree.model import JsonTreeModel
from tree.view import JsonTreeView


class JsonTabEditabilityController:
    """Own read-only/editable view state for a JsonTab."""

    def __init__(self, data_store: JsonTabData) -> None:
        self._data_store = data_store

    def capture_editable_view_state(self) -> None:
        view = self._require_view()
        self._data_store._editable_view_edit_triggers = view.editTriggers()
        self._data_store._editable_drag_enabled = view.dragEnabled()
        self._data_store._editable_accept_drops = view.acceptDrops()
        self._data_store._editable_drag_drop_mode = view.dragDropMode()

    def set_read_only(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self._data_store._read_only == enabled:
            return

        self._data_store._read_only = enabled
        self._require_model().set_read_only(enabled)

        view = self._require_view()
        if enabled:
            view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            view.setDragEnabled(False)
            view.setAcceptDrops(False)
            view.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
            return

        view.setEditTriggers(self._data_store._editable_view_edit_triggers)
        view.setDragEnabled(self._data_store._editable_drag_enabled)
        view.setAcceptDrops(self._data_store._editable_accept_drops)
        view.setDragDropMode(self._data_store._editable_drag_drop_mode)

    def _require_view(self) -> JsonTreeView:
        view = self._data_store.view
        if view is None:
            raise RuntimeError("JsonTab view is not initialized")
        return view

    def _require_model(self) -> JsonTreeModel:
        model = self._data_store.model
        if model is None:
            raise RuntimeError("JsonTab model is not initialized")
        return model


__all__ = ["JsonTabEditabilityController"]
