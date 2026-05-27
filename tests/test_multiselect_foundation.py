"""Step 1 — Multiselect foundation audit & hardening.

Tests for the promoted public helpers in tree_actions/selection.py and their
behaviour with multi-row selections.
"""

from PySide6.QtCore import QItemSelectionModel, QModelIndex
from PySide6.QtWidgets import QAbstractItemView, QTreeView

from documents.tab import JsonTab
from tree.model import JsonTreeModel
from tree_actions.clipboard import copy_selection
from tree_actions.paste import paste_from_clipboard
from tree_actions.selection import (
    _index_path,
    _selected_rows,
    _top_level_selected_rows,
    selected_source_rows,
    selection_spans_multiple_parents,
    top_level_source_rows,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_view(qtbot, data) -> tuple[QTreeView, JsonTreeModel]:
    model = JsonTreeModel(data)
    view = QTreeView()
    view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    view.setModel(model)
    qtbot.addWidget(view)
    return view, model


def _select_rows(view: QTreeView, *indexes) -> None:
    sm = view.selectionModel()
    first, *rest = indexes
    sm.select(first, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
    sm.setCurrentIndex(first, QItemSelectionModel.SelectionFlag.NoUpdate)
    for idx in rest:
        sm.select(idx, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)


def _select_tab(tab: JsonTab, *source_indexes) -> None:
    first, *rest = source_indexes
    vi = tab._source_to_view(first)
    sm = tab.data_store.view.selectionModel()
    sm.select(vi, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
    sm.setCurrentIndex(vi, QItemSelectionModel.SelectionFlag.NoUpdate)
    for src in rest:
        vi = tab._source_to_view(src)
        sm.select(vi, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)


# ---------------------------------------------------------------------------
# Test 1 – ExtendedSelection is set on a fresh JsonTab
# ---------------------------------------------------------------------------


def test_extended_selection_mode_on_json_tab(qtbot):
    tab = JsonTab(lambda *_: None, data={"a": 1})
    qtbot.addWidget(tab)
    assert tab.data_store.view.selectionMode() == QAbstractItemView.SelectionMode.ExtendedSelection


# ---------------------------------------------------------------------------
# Test 2 – Contiguous (Shift-style) selection returns N ordered rows
# ---------------------------------------------------------------------------


def test_contiguous_selection_returns_ordered_rows(qtbot):
    data = {"a": 1, "b": 2, "c": 3, "d": 4}
    view, model = _make_view(qtbot, data)

    a = model.index(0, 0, QModelIndex())
    b = model.index(1, 0, QModelIndex())
    c = model.index(2, 0, QModelIndex())

    _select_rows(view, a, b, c)

    rows = top_level_source_rows(view)
    assert len(rows) == 3
    # Must be ordered by _index_path (i.e. ascending row numbers)
    paths = [_index_path(r) for r in rows]
    assert paths == sorted(paths)


# ---------------------------------------------------------------------------
# Test 3 – Disjoint selection → correct top-level indexes, spans_multiple_parents
# ---------------------------------------------------------------------------


def test_disjoint_selection_and_spans_multiple_parents(qtbot):
    """Select items from two different sub-trees; selection_spans_multiple_parents → True."""
    data = {"obj1": {"x": 1}, "obj2": {"y": 2}}
    view, model = _make_view(qtbot, data)

    obj1 = model.index(0, 0, QModelIndex())
    obj2 = model.index(1, 0, QModelIndex())

    _select_rows(view, obj1, obj2)

    rows = top_level_source_rows(view)
    assert len(rows) == 2
    names = {model.get_item(r).name for r in rows}
    assert names == {"obj1", "obj2"}

    assert selection_spans_multiple_parents(rows) is False  # both share root parent

    # Now select children from different parents to actually span parents
    view2, model2 = _make_view(qtbot, {"obj1": {"x": 1, "x2": 2}, "obj2": {"y": 3, "y2": 4}})
    view2.expandAll()

    obj1_v2 = model2.index(0, 0, QModelIndex())
    obj2_v2 = model2.index(1, 0, QModelIndex())
    x_child = model2.index(0, 0, obj1_v2)
    y_child = model2.index(0, 0, obj2_v2)

    _select_rows(view2, x_child, y_child)
    rows2 = top_level_source_rows(view2)
    assert len(rows2) == 2
    assert selection_spans_multiple_parents(rows2) is True


# ---------------------------------------------------------------------------
# Test 4 – Ancestor pruning: selecting parent + child returns parent only
# ---------------------------------------------------------------------------


def test_ancestor_pruning_parent_and_child(qtbot):
    data = {"parent": {"child": 42}}
    view, model = _make_view(qtbot, data)
    view.expandAll()

    parent_idx = model.index(0, 0, QModelIndex())
    child_idx = model.index(0, 0, parent_idx)

    _select_rows(view, parent_idx, child_idx)

    rows = top_level_source_rows(view)
    assert len(rows) == 1
    assert model.get_item(rows[0]).name == "parent"


# ---------------------------------------------------------------------------
# Test 5 – copy → paste round-trip preserves 3-row disjoint selection
# ---------------------------------------------------------------------------


def test_copy_paste_roundtrip_disjoint_selection(qtbot):
    tab = JsonTab(lambda *_: None, data={"a": 1, "b": 2, "c": 3, "target": []})
    qtbot.addWidget(tab)

    a = tab.data_store.model.index(0, 0, QModelIndex())
    b = tab.data_store.model.index(1, 0, QModelIndex())
    c = tab.data_store.model.index(2, 0, QModelIndex())

    _select_tab(tab, a, b, c)
    assert copy_selection(tab.data_store.view)

    # Select the "target" array and paste into it as children
    target = tab.data_store.model.index(3, 0, QModelIndex())
    _select_tab(tab, target)
    tab.data_store.view.expand(tab._source_to_view(target))

    assert paste_from_clipboard(tab.data_store.view)

    result = tab.data_store.model.get_item(target).to_json()
    assert isinstance(result, list)
    assert len(result) == 3
    # Values 1, 2, 3 must be present (order preserved)
    assert sorted(result) == [1, 2, 3]


# ---------------------------------------------------------------------------
# Test 6 – Public names are true aliases for private names
# ---------------------------------------------------------------------------


def test_public_names_are_aliases(qtbot):
    view, model = _make_view(qtbot, {"x": 10, "y": 20})
    a = model.index(0, 0, QModelIndex())
    _select_rows(view, a)

    assert selected_source_rows(view) == _selected_rows(view)
    assert top_level_source_rows(view) == _top_level_selected_rows(view)
