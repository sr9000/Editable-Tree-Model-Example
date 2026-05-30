from PySide6.QtCore import QItemSelectionModel, QModelIndex, Qt

from documents.tab import JsonTab
from tree_actions.paste import paste_from_clipboard
from tree_actions.structure import delete_selection, move_selection_down, move_selection_up


def _select_row0(tab: JsonTab, row: int, parent: QModelIndex = QModelIndex()) -> None:
    source_index = tab.data_store.model.index(row, 0, parent)
    idx = tab._source_to_view(source_index)
    tab.view.setCurrentIndex(idx)
    tab.view.selectionModel().select(idx, QItemSelectionModel.SelectionFlag.ClearAndSelect)


def test_undo_redo_delete_selection(qtbot):
    tab = JsonTab(lambda *_: None)
    qtbot.addWidget(tab)

    before = tab.data_store.model.root_item.to_json()

    _select_row0(tab, 0)
    assert delete_selection(tab.view)
    assert tab.data_store.model.root_item.to_json() != before

    tab.data_store.undo_stack.undo()
    assert tab.data_store.model.root_item.to_json() == before

    tab.data_store.undo_stack.redo()
    assert tab.data_store.model.root_item.to_json() != before


def test_undo_redo_paste(qtbot):
    tab = JsonTab(lambda *_: None)
    qtbot.addWidget(tab)

    before = tab.data_store.model.root_item.to_json()
    idx = tab.data_store.model.index(0, 0, QModelIndex())
    view_idx = tab._source_to_view(idx)
    tab.view.setCurrentIndex(view_idx)
    tab.view.selectionModel().select(view_idx, QItemSelectionModel.SelectionFlag.ClearAndSelect)

    from PySide6.QtWidgets import QApplication

    QApplication.clipboard().setText('{"pasted": 1}')
    assert paste_from_clipboard(tab.view)

    tab.data_store.undo_stack.undo()
    assert tab.data_store.model.root_item.to_json() == before

    tab.data_store.undo_stack.redo()
    assert tab.data_store.model.root_item.to_json() != before


def test_undo_redo_commit_set_data(qtbot):
    tab = JsonTab(lambda *_: None)
    qtbot.addWidget(tab)

    value_idx = tab.data_store.model.index(0, 2, QModelIndex())
    before = tab.data_store.model.root_item.to_json()

    assert tab.commit_set_data(value_idx, "changed", Qt.ItemDataRole.EditRole)
    assert tab.data_store.model.root_item.to_json() != before

    tab.data_store.undo_stack.undo()
    assert tab.data_store.model.root_item.to_json() == before

    tab.data_store.undo_stack.redo()
    assert tab.data_store.model.root_item.to_json() != before


def _keys_in_order(tab: JsonTab) -> list[str]:
    return [
        tab.data_store.model.index(r, 0, QModelIndex()).data()
        for r in range(tab.data_store.model.rowCount(QModelIndex()))
    ]


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

    tab.data_store.undo_stack.undo()
    assert _keys_in_order(tab) == keys_before

    tab.data_store.undo_stack.redo()
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

    tab.data_store.undo_stack.undo()
    assert _keys_in_order(tab) == keys_before


def test_undo_command_text_includes_path_and_timestamp(qtbot):
    import re

    from tree_actions.structure import duplicate_selection

    tab = JsonTab(lambda *_: None)
    qtbot.addWidget(tab)

    # Edit value of "answer" -> label should mention `$.answer` and `edit value`.
    answer_value = tab.data_store.model.index(1, 2, QModelIndex())
    assert tab.commit_set_data(answer_value, 999, Qt.ItemDataRole.EditRole)
    text = tab.data_store.undo_stack.command(tab.data_store.undo_stack.count() - 1).text()
    assert re.match(r"^\[\d{2}:\d{2}:\d{2}\] edit value @ \$\.answer$", text), text

    # Duplicate "integer" -> label should mention `$.integer` and `duplicate`.
    _select_row0(tab, 2)
    assert duplicate_selection(tab.view)
    text2 = tab.data_store.undo_stack.command(tab.data_store.undo_stack.count() - 1).text()
    assert re.match(r"^\[\d{2}:\d{2}:\d{2}\] duplicate @ \$\.integer$", text2), text2

    # Rename a row -> label should say `rename`.
    name_idx = tab.data_store.model.index(0, 0, QModelIndex())
    assert tab.commit_set_data(name_idx, "renamed-question", Qt.ItemDataRole.EditRole)
    text3 = tab.data_store.undo_stack.command(tab.data_store.undo_stack.count() - 1).text()
    assert re.match(r"^\[\d{2}:\d{2}:\d{2}\] rename @ \$\.question$", text3), text3
