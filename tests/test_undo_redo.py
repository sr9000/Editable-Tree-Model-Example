from PySide6.QtCore import QItemSelectionModel, QModelIndex, Qt

from json_tab import JsonTab
from tree_view import delete_selection, move_selection_down, move_selection_up, paste_from_clipboard


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


def _keys_in_order(tab: JsonTab) -> list[str]:
    return [tab.model.index(r, 0, QModelIndex()).data() for r in range(tab.model.rowCount(QModelIndex()))]


def test_undo_redo_move_object_member_up(qtbot):
    tab = JsonTab(lambda *_: None)
    qtbot.addWidget(tab)

    keys_before = _keys_in_order(tab)
    assert len(keys_before) >= 2

    _select_row0(tab, 1)
    assert move_selection_up(tab.view)

    keys_after = _keys_in_order(tab)
    assert keys_after != keys_before
    assert keys_after[0] == keys_before[1]
    assert keys_after[1] == keys_before[0]

    tab.undo_stack.undo()
    assert _keys_in_order(tab) == keys_before

    tab.undo_stack.redo()
    assert _keys_in_order(tab) == keys_after


def test_undo_redo_move_object_member_down(qtbot):
    tab = JsonTab(lambda *_: None)
    qtbot.addWidget(tab)

    keys_before = _keys_in_order(tab)
    _select_row0(tab, 0)
    assert move_selection_down(tab.view)

    keys_after = _keys_in_order(tab)
    assert keys_after[0] == keys_before[1]
    assert keys_after[1] == keys_before[0]

    tab.undo_stack.undo()
    assert _keys_in_order(tab) == keys_before
