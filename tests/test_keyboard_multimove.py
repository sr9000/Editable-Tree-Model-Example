"""Step 4 — Keyboard multi-move + parent-boundary bubble-out."""

from __future__ import annotations

import copy

from PySide6.QtCore import QItemSelectionModel

from documents.tab import JsonTab
from tree_actions.structure import (
    move_selection_down,
    move_selection_out_down,
    move_selection_out_up,
    move_selection_up,
)


def _make_tab(qtbot, data, *, show_root: bool = False) -> JsonTab:
    tab = JsonTab(lambda *_: None, data=data, show_root=show_root)
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


def _assert_single_undo_roundtrip(tab: JsonTab, before_snapshot, before_count: int) -> None:
    assert tab.undo_stack.count() == before_count + 1
    tab.undo_stack.undo()
    assert tab.model.root_item.to_json() == before_snapshot


def test_alt_up_single_row_reorders_within_parent_and_undo(qtbot):
    tab = _make_tab(qtbot, {"a": 1, "b": 2, "c": 3})
    before = copy.deepcopy(tab.model.root_item.to_json())
    before_count = tab.undo_stack.count()

    b = _idx(tab, 1)
    _select_source_rows(tab, b)

    assert move_selection_up(tab.view)
    assert list(tab.model.root_item.to_json().keys()) == ["b", "a", "c"]
    _assert_single_undo_roundtrip(tab, before, before_count)


def test_alt_up_multiselect_block_moves_together_and_undo(qtbot):
    tab = _make_tab(qtbot, {"a": 1, "b": 2, "c": 3})
    before = copy.deepcopy(tab.model.root_item.to_json())
    before_count = tab.undo_stack.count()

    b = _idx(tab, 1)
    c = _idx(tab, 2)
    _select_source_rows(tab, b, c)

    assert move_selection_up(tab.view)
    assert list(tab.model.root_item.to_json().keys()) == ["b", "c", "a"]
    _assert_single_undo_roundtrip(tab, before, before_count)


def test_alt_up_bubbles_out_before_parent_at_boundary_and_undo(qtbot):
    tab = _make_tab(qtbot, {"obj": {"x": 1, "y": 2, "z": 3}, "tail": 0})
    before = copy.deepcopy(tab.model.root_item.to_json())
    before_count = tab.undo_stack.count()

    x = _idx(tab, 0, 0)
    _select_source_rows(tab, x)

    assert move_selection_up(tab.view)
    assert tab.model.root_item.to_json() == {"x": 1, "obj": {"y": 2, "z": 3}, "tail": 0}
    _assert_single_undo_roundtrip(tab, before, before_count)


def test_alt_up_on_root_level_row_is_noop(qtbot):
    tab = _make_tab(qtbot, {"a": 1, "b": 2})
    before = copy.deepcopy(tab.model.root_item.to_json())
    before_count = tab.undo_stack.count()

    a = _idx(tab, 0)
    _select_source_rows(tab, a)

    assert move_selection_up(tab.view) is False
    assert tab.undo_stack.count() == before_count
    assert tab.model.root_item.to_json() == before


def test_alt_down_discontinuous_selection_moves_each_parent_independently(qtbot):
    tab = _make_tab(qtbot, {"left": {"a": 1, "b": 2, "c": 3}, "right": {"x": 4, "y": 5, "z": 6}})
    before = copy.deepcopy(tab.model.root_item.to_json())
    before_count = tab.undo_stack.count()

    left_a = _idx(tab, 0, 0)
    right_x = _idx(tab, 1, 0)
    _select_source_rows(tab, left_a, right_x)

    assert move_selection_down(tab.view)
    assert tab.model.root_item.to_json() == {
        "left": {"b": 2, "a": 1, "c": 3},
        "right": {"y": 5, "x": 4, "z": 6},
    }
    _assert_single_undo_roundtrip(tab, before, before_count)


def test_alt_down_bottom_block_bubbles_out_after_parent_and_undo(qtbot):
    tab = _make_tab(qtbot, {"obj": {"x": 1, "y": 2, "z": 3}, "tail": 0})
    before = copy.deepcopy(tab.model.root_item.to_json())
    before_count = tab.undo_stack.count()

    y = _idx(tab, 0, 1)
    z = _idx(tab, 0, 2)
    _select_source_rows(tab, y, z)

    assert move_selection_down(tab.view)
    assert tab.model.root_item.to_json() == {"obj": {"x": 1}, "y": 2, "z": 3, "tail": 0}
    _assert_single_undo_roundtrip(tab, before, before_count)


def test_show_root_true_root_level_move_uses_root_relative_paths(qtbot):
    tab = _make_tab(qtbot, {"a": 1, "b": 2, "c": 3}, show_root=True)
    before = copy.deepcopy(tab.model.root_item.to_json())
    before_count = tab.undo_stack.count()

    b = _idx(tab, 1)
    _select_source_rows(tab, b)

    assert move_selection_up(tab.view)
    assert list(tab.model.root_item.to_json().keys()) == ["b", "a", "c"]
    tab.undo_stack.undo()
    assert tab.model.root_item.to_json() == before
    tab.undo_stack.redo()
    assert list(tab.model.root_item.to_json().keys()) == ["b", "a", "c"]
    assert tab.undo_stack.count() == before_count + 1


def test_show_root_true_boundary_move_bubbles_out_and_redo_does_not_crash(qtbot):
    tab = _make_tab(qtbot, {"obj": {"x": 1, "y": 2}, "tail": 0}, show_root=True)
    before = copy.deepcopy(tab.model.root_item.to_json())

    x = _idx(tab, 0, 0)
    _select_source_rows(tab, x)

    assert move_selection_up(tab.view)
    assert tab.model.root_item.to_json() == {"x": 1, "obj": {"y": 2}, "tail": 0}
    tab.undo_stack.undo()
    assert tab.model.root_item.to_json() == before
    tab.undo_stack.redo()
    assert tab.model.root_item.to_json() == {"x": 1, "obj": {"y": 2}, "tail": 0}


def test_move_selection_out_up_down_regardless_of_boundary(qtbot):
    tab = _make_tab(qtbot, {"head": 0, "obj": {"x": 1, "y": 2}, "tail": 3}, show_root=True)

    y = _idx(tab, 1, 1)
    _select_source_rows(tab, y)
    assert move_selection_out_up(tab.view)
    assert tab.model.root_item.to_json() == {"head": 0, "y": 2, "obj": {"x": 1}, "tail": 3}

    tab.undo_stack.undo()
    x = _idx(tab, 1, 0)
    _select_source_rows(tab, x)
    assert move_selection_out_down(tab.view)
    assert tab.model.root_item.to_json() == {"head": 0, "obj": {"y": 2}, "x": 1, "tail": 3}
