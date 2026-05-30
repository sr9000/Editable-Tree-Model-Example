"""Regression: Alt+Up/Alt+Down must move the whole multi-selection in the live
app, where the view uses SelectionBehavior.SelectItems (not SelectRows).

This test mirrors the production JsonTab configuration. Before the fix,
``_selected_rows`` fell through to ``currentIndex()`` because
``selectedRows(0)`` is empty under SelectItems, and only one row moved.
"""

from __future__ import annotations

import copy

from PySide6.QtCore import QItemSelectionModel
from PySide6.QtWidgets import QAbstractItemView

from documents.tab import JsonTab
from tree_actions.selection import top_level_source_rows
from tree_actions.structure import move_selection_down, move_selection_up


def _make_tab(qtbot, data) -> JsonTab:
    tab = JsonTab(lambda *_: None, data=data)
    qtbot.addWidget(tab)
    # Mirror the real app: the MainWindow constructs the tab with show_root=True
    # and SelectItems behaviour comes from documents/tab_setup.py.
    assert tab.view.selectionBehavior() == QAbstractItemView.SelectionBehavior.SelectItems
    return tab


def _idx(tab: JsonTab, *path: int):
    return tab.view_controller.index_from_path(path)


def _select_items(tab: JsonTab, *source_indexes) -> None:
    """Select indexes one cell at a time (NoUpdate-friendly), matching how
    Ctrl+Click builds a selection in the live app under SelectItems."""
    sm = tab.view.selectionModel()
    first, *rest = source_indexes
    first_view = tab.view_controller.source_to_view(first)
    sm.select(first_view, QItemSelectionModel.SelectionFlag.ClearAndSelect)
    sm.setCurrentIndex(first_view, QItemSelectionModel.SelectionFlag.NoUpdate)
    for idx in rest:
        vi = tab.view_controller.source_to_view(idx)
        sm.select(vi, QItemSelectionModel.SelectionFlag.Select)


def _selected_names(tab: JsonTab) -> list[str]:
    """Return the names of all top-level selected source rows, in path order."""
    rows = top_level_source_rows(tab.view)
    return [tab.model.get_item(r).name for r in rows]


# ---------------------------------------------------------------------------
# Original regression: only one row moved (SelectItems vs SelectRows)
# ---------------------------------------------------------------------------


def test_alt_up_moves_block_under_select_items_behaviour(qtbot):
    """Two adjacent siblings selected via SelectItems → Alt+Up must move both."""
    tab = _make_tab(qtbot, {"a": 1, "b": 2, "c": 3, "d": 4})
    before = copy.deepcopy(tab.model.root_item.to_json())
    before_count = tab.undo_stack.count()

    b = _idx(tab, 1)
    c = _idx(tab, 2)
    _select_items(tab, b, c)

    assert move_selection_up(tab.view)
    # Both b and c must climb past a in a single undo step.
    assert list(tab.model.root_item.to_json().keys()) == ["b", "c", "a", "d"]
    assert tab.undo_stack.count() == before_count + 1
    tab.undo_stack.undo()
    assert tab.model.root_item.to_json() == before


def test_alt_down_moves_block_under_select_items_behaviour(qtbot):
    """Two adjacent siblings selected via SelectItems → Alt+Down must move both."""
    tab = _make_tab(qtbot, {"a": 1, "b": 2, "c": 3, "d": 4})
    before = copy.deepcopy(tab.model.root_item.to_json())
    before_count = tab.undo_stack.count()

    b = _idx(tab, 1)
    c = _idx(tab, 2)
    _select_items(tab, b, c)

    assert move_selection_down(tab.view)
    assert list(tab.model.root_item.to_json().keys()) == ["a", "d", "b", "c"]
    assert tab.undo_stack.count() == before_count + 1
    tab.undo_stack.undo()
    assert tab.model.root_item.to_json() == before


def test_alt_up_block_when_user_selects_value_column_cells(qtbot):
    """Real-world flow: user clicks on Value column cells while holding Ctrl.
    All selected cells share rows but live in column 2 — the move helper
    must still treat them as full-row selections."""
    tab = _make_tab(qtbot, {"a": 1, "b": 2, "c": 3, "d": 4})
    before = copy.deepcopy(tab.model.root_item.to_json())

    # Click the value column (column 2) for rows "b" and "c".
    b_val = tab.model.index(1, 2)
    c_val = tab.model.index(2, 2)
    _select_items(tab, b_val, c_val)

    assert move_selection_up(tab.view)
    assert list(tab.model.root_item.to_json().keys()) == ["b", "c", "a", "d"]
    tab.undo_stack.undo()
    assert tab.model.root_item.to_json() == before


# ---------------------------------------------------------------------------
# Selection preservation after move
# ---------------------------------------------------------------------------


def test_selection_preserved_after_alt_up_same_parent(qtbot):
    """Moved rows must still be selected after Alt+Up."""
    tab = _make_tab(qtbot, {"a": 1, "b": 2, "c": 3, "d": 4})

    b = _idx(tab, 1)
    c = _idx(tab, 2)
    _select_items(tab, b, c)

    assert move_selection_up(tab.view)
    assert list(tab.model.root_item.to_json().keys()) == ["b", "c", "a", "d"]
    # b and c should still be selected at their new positions.
    assert set(_selected_names(tab)) == {"b", "c"}


def test_selection_preserved_after_alt_down_same_parent(qtbot):
    """Moved rows must still be selected after Alt+Down."""
    tab = _make_tab(qtbot, {"a": 1, "b": 2, "c": 3, "d": 4})

    b = _idx(tab, 1)
    c = _idx(tab, 2)
    _select_items(tab, b, c)

    assert move_selection_down(tab.view)
    assert list(tab.model.root_item.to_json().keys()) == ["a", "d", "b", "c"]
    assert set(_selected_names(tab)) == {"b", "c"}


def test_selection_preserved_after_bubble_up(qtbot):
    """When a row bubbles out before its parent, it stays selected."""
    tab = _make_tab(qtbot, {"obj": {"x": 1, "y": 2}, "tail": 0})

    x = _idx(tab, 0, 0)
    _select_items(tab, x)

    assert move_selection_up(tab.view)
    # x should now be a root-level sibling before obj.
    root_keys = list(tab.model.root_item.to_json().keys())
    assert root_keys[0] == "x"
    assert set(_selected_names(tab)) == {"x"}


def test_selection_preserved_after_multi_parent_fallback(qtbot):
    """Cross-parent independent moves (macro) must keep all moved rows selected."""
    tab = _make_tab(qtbot, {"left": {"a": 1, "b": 2, "c": 3}, "right": {"x": 4, "y": 5, "z": 6}})

    left_b = _idx(tab, 0, 1)  # "b" at row 1 inside "left"
    right_y = _idx(tab, 1, 1)  # "y" at row 1 inside "right"
    _select_items(tab, left_b, right_y)

    assert move_selection_up(tab.view)
    assert tab.model.root_item.to_json() == {
        "left": {"b": 2, "a": 1, "c": 3},
        "right": {"y": 5, "x": 4, "z": 6},
    }
    # Both moved rows must remain selected.
    assert set(_selected_names(tab)) == {"b", "y"}
