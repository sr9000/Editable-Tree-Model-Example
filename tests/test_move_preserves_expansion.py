from __future__ import annotations

from PySide6.QtCore import QItemSelectionModel

from documents.tab import JsonTab
from tree_actions.selection import selected_source_rows


def _make_tab(qtbot, data) -> JsonTab:
    tab = JsonTab(lambda *_: None, data=data)
    qtbot.addWidget(tab)
    return tab


def _idx(tab: JsonTab, *path: int):
    return tab.view_controller.index_from_path(path)


def _select_source_rows(tab: JsonTab, *source_indexes) -> None:
    first, *rest = source_indexes
    sm = tab.view.selectionModel()
    first_view = tab.view_controller.source_to_view(first)
    sm.select(
        first_view,
        QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
    )
    sm.setCurrentIndex(first_view, QItemSelectionModel.SelectionFlag.NoUpdate)
    for idx in rest:
        vi = tab.view_controller.source_to_view(idx)
        sm.select(vi, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)


def _child_row_by_name(tab: JsonTab, parent, name: str) -> int:
    for row in range(tab.data_store.model.rowCount(parent)):
        idx = tab.data_store.model.index(row, 0, parent)
        if tab.data_store.model.get_item(idx).name == name:
            return row
    raise AssertionError(f"missing child {name!r}")


def test_move_preserves_expansion_and_selection_and_undo(qtbot):
    tab = _make_tab(
        qtbot,
        {
            "target": {},
            "a": {"b": {"c": 1, "d": {"e": 2}}},
            "x": {"k": 0},
        },
    )

    target = _idx(tab, 0)
    b = _idx(tab, 1, 0)
    d = _idx(tab, 1, 0, 1)
    x = _idx(tab, 2)

    tab.view.setExpanded(tab.view_controller.source_to_view(b), True)
    tab.view.setExpanded(tab.view_controller.source_to_view(d), True)
    tab.view.setExpanded(tab.view_controller.source_to_view(x), False)
    _select_source_rows(tab, b, x)

    assert tab.push_move_rows([b, x], target, 0)

    target_after = _idx(tab, 0)
    moved_b_row = _child_row_by_name(tab, target_after, "b")
    moved_x_row = _child_row_by_name(tab, target_after, "x")
    moved_b = _idx(tab, 0, moved_b_row)
    moved_d = _idx(tab, 0, moved_b_row, 1)
    moved_x = _idx(tab, 0, moved_x_row)

    assert tab.view.isExpanded(tab.view_controller.source_to_view(moved_b))
    assert tab.view.isExpanded(tab.view_controller.source_to_view(moved_d))
    assert not tab.view.isExpanded(tab.view_controller.source_to_view(moved_x))

    expected_selected = {(0, moved_b_row), (0, moved_x_row)}
    selected_paths = {tab.view_controller.index_path(idx) for idx in selected_source_rows(tab.view) if idx.isValid()}
    assert selected_paths == expected_selected
    assert (
        tab.view_controller.index_path(tab.view_controller.proxy_to_source(tab.view.currentIndex()))
        in expected_selected
    )

    tab.data_store.undo_stack.undo()

    assert tab.view.isExpanded(tab.view_controller.source_to_view(_idx(tab, 1, 0)))
    assert tab.view.isExpanded(tab.view_controller.source_to_view(_idx(tab, 1, 0, 1)))
    assert not tab.view.isExpanded(tab.view_controller.source_to_view(_idx(tab, 2)))

    restored_selected = {tab.view_controller.index_path(idx) for idx in selected_source_rows(tab.view) if idx.isValid()}
    assert restored_selected == {(1, 0), (2,)}
    assert tab.view_controller.index_path(tab.view_controller.proxy_to_source(tab.view.currentIndex())) == (1, 0)
