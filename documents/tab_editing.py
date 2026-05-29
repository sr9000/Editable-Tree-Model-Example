"""Edit-from-Enter and type-change editor lifecycle helpers.

Extracted from :class:`documents.tab.JsonTab` so the widget stays focused on
wiring.  All entry points take the owning ``JsonTab`` as their first argument.
"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, Qt, QTimer
from PySide6.QtWidgets import QAbstractItemView, QComboBox


def on_type_changed(tab: "JsonTab", item_index, lossy: bool) -> None:
    # ``change_type`` already emitted ``dataChanged`` for the row, which closes
    # any persistent inline editor that might have been open on the value cell.
    # We additionally close it explicitly so the row is in a clean state before
    # any auto-reopen below.
    value_index = tab.data_store.model.index(item_index.row(), 2, item_index.parent())
    tab.data_store.view.closePersistentEditor(tab._source_to_view(value_index))

    if lossy:
        tab.show_status("Type change dropped existing child nodes", 3000)

    # Auto-reopen the value editor only when the type change came from a
    # user-driven combo commit (Phase 5.1). Programmatic ``model.setData`` paths
    # (tests, scripted edits) bypass the delegate entirely so ``_interactive``
    # stays ``False`` and we avoid the spurious "edit: editing failed" warning
    # that ``tests/test_smoke_mainwindow.py`` regression-tests.
    if not tab.data_store.type_delegate.interactive:
        return
    if not value_index.isValid():
        return
    # Defer via single-shot timer so Qt finishes the current commit cycle
    # (combo close + setModelData unwind) before we open a new editor on the
    # same row.
    pidx = QPersistentModelIndex(value_index)
    QTimer.singleShot(0, lambda: reopen_value_editor(tab, pidx))


def reopen_value_editor(tab: "JsonTab", value_pindex: QPersistentModelIndex) -> None:
    if not value_pindex.isValid():
        return
    value_index = QModelIndex(value_pindex) if isinstance(value_pindex, QPersistentModelIndex) else value_pindex
    if not value_index.isValid():
        return
    flags = tab.data_store.model.flags(value_index)
    if not (flags & Qt.ItemFlag.ItemIsEditable):
        return
    view_index = tab._source_to_view(value_index)
    if not view_index.isValid():
        return
    tab.data_store.view.setCurrentIndex(view_index)
    tab.data_store.view.edit(view_index)


def edit_name_or_value_from_enter(tab: "JsonTab") -> None:
    """Start editing from Enter with type-column support.

    - Name/Value columns: edit the current editable cell.
    - Type column: open the inline type combobox editor.
    """
    if tab.data_store.view.state() == QAbstractItemView.State.EditingState:
        return
    current = tab.data_store.view.currentIndex()
    if not current.isValid():
        return

    if current.column() == 1:
        if tab.data_store.view.model().flags(current) & Qt.ItemFlag.ItemIsEditable:
            tab.data_store.view.edit(current)
            QTimer.singleShot(0, tab._open_active_type_combo_popup)
        return

    candidates: list[QModelIndex] = []
    if current.column() in (0, 2):
        candidates.append(current)
    candidates.extend((current.siblingAtColumn(2), current.siblingAtColumn(0)))

    model = tab.data_store.view.model()
    for idx in candidates:
        if not idx.isValid():
            continue
        if not (model.flags(idx) & Qt.ItemFlag.ItemIsEditable):
            continue
        tab.data_store.view.setCurrentIndex(idx)
        tab.data_store.view.edit(idx)
        return


def open_active_type_combo_popup(tab: "JsonTab") -> None:
    for combo in tab.data_store.view.findChildren(QComboBox):
        if combo.parent() is tab.data_store.view.viewport() and combo.isVisible():
            combo.showPopup()
            return
