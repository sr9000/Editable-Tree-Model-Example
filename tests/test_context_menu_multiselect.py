from __future__ import annotations

from PySide6.QtCore import QItemSelectionModel
from PySide6.QtWidgets import QApplication

from documents.tab import JsonTab
from tree_actions.context_menu import _prepare_context_selection
from tree_actions.paste import paste_auto
from tree_actions.selection import selected_source_rows


def _make_tab(qtbot, data) -> JsonTab:
    tab = JsonTab(lambda *_: None, data=data)
    qtbot.addWidget(tab)
    return tab


def _select_value_cells(tab: JsonTab, *paths: tuple[int, ...]) -> None:
    sm = tab.view.selectionModel()
    first, *rest = paths
    first_src = tab._index_from_path(first).siblingAtColumn(2)
    first_view = tab._source_to_view(first_src)
    sm.select(first_view, QItemSelectionModel.SelectionFlag.ClearAndSelect)
    sm.setCurrentIndex(first_view, QItemSelectionModel.SelectionFlag.NoUpdate)
    for path in rest:
        src = tab._index_from_path(path).siblingAtColumn(2)
        sm.select(tab._source_to_view(src), QItemSelectionModel.SelectionFlag.Select)


def _selected_paths(tab: JsonTab) -> set[tuple[int, ...]]:
    return {tab._index_path(idx) for idx in selected_source_rows(tab.view)}


def _root_values(tab: JsonTab) -> list:
    return [item.to_json() for item in tab.model.root_item.child_items]


def test_context_menu_prepare_preserves_selection_when_clicking_selected_value_cell(qtbot):
    tab = _make_tab(qtbot, {"a": 1, "b": 2, "c": 3})
    _select_value_cells(tab, (0,), (2,))

    clicked = tab._source_to_view(tab._index_from_path((0,)).siblingAtColumn(2))
    _prepare_context_selection(tab.view, clicked)

    assert _selected_paths(tab) == {(0,), (2,)}


def test_context_menu_prepare_resets_selection_when_clicking_unselected_row(qtbot):
    tab = _make_tab(qtbot, {"a": 1, "b": 2, "c": 3})
    _select_value_cells(tab, (0,), (1,))

    clicked = tab._source_to_view(tab._index_from_path((2,)).siblingAtColumn(2))
    _prepare_context_selection(tab.view, clicked)

    assert _selected_paths(tab) == {(2,)}


def test_context_paste_action_uses_preserved_multiselect(qtbot):
    tab = _make_tab(qtbot, {"a": 1, "b": 2, "c": 3})
    _select_value_cells(tab, (0,), (2,))

    clicked = tab._source_to_view(tab._index_from_path((0,)).siblingAtColumn(2))
    _prepare_context_selection(tab.view, clicked)

    QApplication.clipboard().setText("99")
    assert paste_auto(tab.view)
    assert _root_values(tab) == [1, 99, 2, 3, 99]
