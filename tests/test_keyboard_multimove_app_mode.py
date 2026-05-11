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
from tree_actions.structure import move_selection_down, move_selection_up


def _make_tab(qtbot, data) -> JsonTab:
    tab = JsonTab(lambda *_: None, data=data)
    qtbot.addWidget(tab)
    # Mirror the real app: the MainWindow constructs the tab with show_root=True
    # and SelectItems behaviour comes from documents/tab_setup.py.
    assert tab.view.selectionBehavior() == QAbstractItemView.SelectionBehavior.SelectItems
    return tab


def _idx(tab: JsonTab, *path: int):
    return tab._index_from_path(path)


def _select_items(tab: JsonTab, *source_indexes) -> None:
    """Select indexes one cell at a time (NoUpdate-friendly), matching how
    Ctrl+Click builds a selection in the live app under SelectItems."""
    sm = tab.view.selectionModel()
    first, *rest = source_indexes
    first_view = tab._source_to_view(first)
    sm.select(first_view, QItemSelectionModel.SelectionFlag.ClearAndSelect)
    sm.setCurrentIndex(first_view, QItemSelectionModel.SelectionFlag.NoUpdate)
    for idx in rest:
        vi = tab._source_to_view(idx)
        sm.select(vi, QItemSelectionModel.SelectionFlag.Select)


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
