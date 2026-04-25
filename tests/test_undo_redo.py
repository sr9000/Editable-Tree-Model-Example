from PySide6.QtCore import QItemSelectionModel, QModelIndex, Qt

from json_tab import JsonTab
from tree_view import delete_selection, paste_from_clipboard


def _select_row0(tab: JsonTab, row: int, parent: QModelIndex = QModelIndex()) -> None:
    idx = tab.model.index(row, 0, parent)
    tab.view.setCurrentIndex(idx)
    tab.view.selectionModel().select(idx, QItemSelectionModel.SelectionFlag.ClearAndSelect)


def test_undo_redo_delete_selection(qtbot):
    tab = JsonTab(lambda *_: None)
    qtbot.addWidget(tab)

    before = tab.model.root_item.to_json()

    _select_row0(tab, 0)
    assert delete_selection(tab.view)
    assert tab.model.root_item.to_json() != before

    tab.undo_stack.undo()
    assert tab.model.root_item.to_json() == before

    tab.undo_stack.redo()
    assert tab.model.root_item.to_json() != before


def test_undo_redo_paste(qtbot):
    tab = JsonTab(lambda *_: None)
    qtbot.addWidget(tab)

    before = tab.model.root_item.to_json()
    idx = tab.model.index(0, 0, QModelIndex())
    tab.view.setCurrentIndex(idx)
    tab.view.selectionModel().select(idx, QItemSelectionModel.SelectionFlag.ClearAndSelect)

    from PySide6.QtWidgets import QApplication

    QApplication.clipboard().setText('{"pasted": 1}')
    assert paste_from_clipboard(tab.view)

    tab.undo_stack.undo()
    assert tab.model.root_item.to_json() == before

    tab.undo_stack.redo()
    assert tab.model.root_item.to_json() != before


def test_undo_redo_commit_set_data(qtbot):
    tab = JsonTab(lambda *_: None)
    qtbot.addWidget(tab)

    value_idx = tab.model.index(0, 2, QModelIndex())
    before = tab.model.root_item.to_json()

    assert tab.commit_set_data(value_idx, "changed", Qt.ItemDataRole.EditRole)
    assert tab.model.root_item.to_json() != before

    tab.undo_stack.undo()
    assert tab.model.root_item.to_json() == before

    tab.undo_stack.redo()
    assert tab.model.root_item.to_json() != before
