"""Inline editor orchestration for type/name/value editing flows."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, Qt, QTimer
from PySide6.QtWidgets import QAbstractItemView, QComboBox


class InlineEditController:
    def __init__(self, tab) -> None:
        self._tab = tab

    def on_type_changed(self, item_index, lossy: bool) -> None:
        tab = self._tab
        # ``change_type`` already emitted ``dataChanged`` for the row, which
        # closes any persistent inline editor that might have been open on the
        # value cell. We additionally close it explicitly so the row is in a
        # clean state before any auto-reopen below.
        value_index = tab.model.index(item_index.row(), 2, item_index.parent())
        tab.view_state.view.closePersistentEditor(tab.view_controller.source_to_view(value_index))

        if lossy:
            tab.show_status("Type change dropped existing child nodes", 3000)

        # Auto-reopen the value editor only when the type change came from a
        # user-driven combo commit (Phase 5.1). Programmatic ``model.setData``
        # paths (tests, scripted edits) bypass the delegate entirely so
        # ``_interactive`` stays ``False`` and we avoid the spurious
        # "edit: editing failed" warning that
        # ``tests/test_smoke_mainwindow.py`` regression-tests.
        if not tab.view_state.type_delegate.interactive:
            return
        if not value_index.isValid():
            return
        # Defer via single-shot timer so Qt finishes the current commit cycle
        # (combo close + setModelData unwind) before we open a new editor on the
        # same row.
        pidx = QPersistentModelIndex(value_index)
        QTimer.singleShot(0, lambda: self.reopen_value_editor(pidx))

    def reopen_value_editor(self, value_pindex: QPersistentModelIndex) -> None:
        tab = self._tab
        if not value_pindex.isValid():
            return
        value_index = QModelIndex(value_pindex) if isinstance(value_pindex, QPersistentModelIndex) else value_pindex
        if not value_index.isValid():
            return
        flags = tab.model.flags(value_index)
        if not (flags & Qt.ItemFlag.ItemIsEditable):
            return
        view_index = tab.view_controller.source_to_view(value_index)
        if not view_index.isValid():
            return
        tab.view_state.view.setCurrentIndex(view_index)
        tab.view_state.view.edit(view_index)

    def edit_name_or_value_from_enter(self) -> None:
        """Start editing the current name, type, or value cell from Enter."""
        tab = self._tab
        if tab.view_state.view.state() == QAbstractItemView.State.EditingState:
            return
        current = tab.view_state.view.currentIndex()
        if not current.isValid():
            return

        if current.column() == 1:
            if tab.view_state.view.model().flags(current) & Qt.ItemFlag.ItemIsEditable:
                tab.view_state.view.edit(current)
                QTimer.singleShot(0, self.open_active_type_combo_popup)
            return

        candidates: list[QModelIndex] = []
        if current.column() in (0, 2):
            candidates.append(current)
        candidates.extend((current.siblingAtColumn(2), current.siblingAtColumn(0)))

        model = tab.view_state.view.model()
        for idx in candidates:
            if not idx.isValid():
                continue
            if not (model.flags(idx) & Qt.ItemFlag.ItemIsEditable):
                continue
            tab.view_state.view.setCurrentIndex(idx)
            tab.view_state.view.edit(idx)
            return

    def open_active_type_combo_popup(self) -> None:
        tab = self._tab
        for combo in tab.view_state.view.findChildren(QComboBox):
            if combo.parent() is tab.view_state.view.viewport() and combo.isVisible():
                combo.showPopup()
                return


__all__ = ["InlineEditController"]
