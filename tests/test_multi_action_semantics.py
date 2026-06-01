"""Step 10 — Multi-action semantics: copy / paste / insert / replace.

Three distinct behaviours sharing the canonical clipboard MIME format:

- **Multi-copy** (Ctrl+C): branches on selection shape.
  Disjoint: copy each top-level row's full subtree.
  Filter (ancestor + descendant both selected): project ancestor
  subtrees down to only the selected descendants.
- **Multi-paste** (Ctrl+V): with multi-selection, paste a clone of
  *every* clipboard entry at *every* selected target, single undo step.
- **Multi-insert** (Ctrl+Shift+V): zip-pair clipboard top-level
  entries with top-level selected targets and insert each paired entry
  *after* its target; single undo step.
- **Multi-replace** (separate action): zip-pair clipboard top-level
  entries with top-level selected targets and replace each target value.
"""

from __future__ import annotations

import json

from PySide6.QtCore import QItemSelectionModel, QModelIndex
from PySide6.QtWidgets import QApplication

from documents.states.editing_controller import TreeAction
from documents.tab import JsonTab
from tree_actions.clipboard import MIME_JSON_TREE, copy_selection
from tree_actions.paste import paste_auto, paste_clones_at_targets, paste_insert_after_zip, paste_replace_zip
from tree_actions.selection import deepest_selected_rows, selection_shape


def _make_tab(qtbot, data) -> JsonTab:
    tab = JsonTab(lambda *_: None, data=data)
    qtbot.addWidget(tab)
    return tab


def _idx(tab: JsonTab, *path: int) -> QModelIndex:
    return tab.view_controller.index_from_path(path)


def _select_items(tab: JsonTab, *source_indexes) -> None:
    sm = tab.view.selectionModel()
    first, *rest = source_indexes
    first_view = tab.view_controller.source_to_view(first)
    sm.select(first_view, QItemSelectionModel.SelectionFlag.ClearAndSelect)
    sm.setCurrentIndex(first_view, QItemSelectionModel.SelectionFlag.NoUpdate)
    for idx in rest:
        sm.select(tab.view_controller.source_to_view(idx), QItemSelectionModel.SelectionFlag.Select)


def _root_values(tab: JsonTab) -> list:
    return [item.to_json() for item in tab.model.root_item.child_items]


# ---------------------------------------------------------------------------
# selection_shape + deepest_selected_rows
# ---------------------------------------------------------------------------


def test_selection_shape_disjoint(qtbot):
    tab = _make_tab(qtbot, {"a": {"x": 1}, "b": {"y": 2}, "c": 3})
    rows = [_idx(tab, 0, 0), _idx(tab, 1, 0)]
    assert selection_shape(rows) == "disjoint"


def test_selection_shape_filter_when_ancestor_and_descendant_selected(qtbot):
    tab = _make_tab(qtbot, {"a": {"x": 1, "y": 2}})
    rows = [_idx(tab, 0), _idx(tab, 0, 0)]  # "a" and "a.x"
    assert selection_shape(rows) == "filter"


def test_selection_shape_single(qtbot):
    tab = _make_tab(qtbot, {"a": 1})
    assert selection_shape([_idx(tab, 0)]) == "single"


def test_deepest_selected_rows_drops_ancestors_when_descendants_present(qtbot):
    tab = _make_tab(qtbot, {"a": {"x": 1, "y": 2}, "b": 3})
    a = _idx(tab, 0)
    ax = _idx(tab, 0, 0)
    b = _idx(tab, 1)
    _select_items(tab, a, ax, b)
    deepest = deepest_selected_rows(tab.view)
    # "a" is dropped because "a.x" is selected; "b" stays (no descendants in selection).
    paths = {tab.view_controller.index_path(idx) for idx in deepest}
    assert paths == {(0, 0), (1,)}


# ---------------------------------------------------------------------------
# Multi-copy filter mode — projection of ancestor subtree
# ---------------------------------------------------------------------------


def test_multi_copy_filter_projects_ancestor_subtree(qtbot):
    """Select 'a' (object) AND 'a.x' (one of its children).
    Filter mode → copied payload is {'a': {'x': 1}} (only the selected
    descendant remains under 'a')."""
    tab = _make_tab(qtbot, {"a": {"x": 1, "y": 2, "z": 3}, "b": 4})

    a = _idx(tab, 0)
    ax = _idx(tab, 0, 0)
    _select_items(tab, a, ax)

    assert copy_selection(tab.view)
    mime = QApplication.clipboard().mimeData()
    assert mime.hasFormat(MIME_JSON_TREE)
    raw = mime.data(MIME_JSON_TREE).data().decode("utf-8")
    blob = json.loads(raw)
    entries = blob["entries"]
    assert len(entries) == 1
    assert entries[0]["name"] == "a"
    assert entries[0]["value"] == {"x": 1}


def test_multi_copy_disjoint_copies_full_subtrees(qtbot):
    """Two disjoint subtrees → both copied in full."""
    tab = _make_tab(qtbot, {"a": {"x": 1, "y": 2}, "b": {"u": 3}})
    a = _idx(tab, 0)
    b = _idx(tab, 1)
    _select_items(tab, a, b)

    assert copy_selection(tab.view)
    raw = QApplication.clipboard().mimeData().data(MIME_JSON_TREE).data().decode("utf-8")
    entries = json.loads(raw)["entries"]
    names_values = {e["name"]: e["value"] for e in entries}
    assert names_values == {"a": {"x": 1, "y": 2}, "b": {"u": 3}}


def test_multi_copy_filter_keeps_multiple_descendants(qtbot):
    """Select 'a' AND 'a.x' AND 'a.z' → projection keeps both descendants."""
    tab = _make_tab(qtbot, {"a": {"x": 1, "y": 2, "z": 3}})
    _select_items(tab, _idx(tab, 0), _idx(tab, 0, 0), _idx(tab, 0, 2))
    assert copy_selection(tab.view)
    entries = json.loads(QApplication.clipboard().mimeData().data(MIME_JSON_TREE).data().decode("utf-8"))["entries"]
    assert len(entries) == 1
    assert entries[0]["value"] == {"x": 1, "z": 3}


# ---------------------------------------------------------------------------
# Multi-paste — clones at every selected target, single undo step
# ---------------------------------------------------------------------------


def test_multi_paste_clones_at_every_selected_leaf(qtbot):
    """Two leaf selections; clipboard has one entry → each leaf gets one
    new sibling after it."""
    tab = _make_tab(qtbot, {"a": 1, "b": 2, "c": 3})
    a = _idx(tab, 0)
    c = _idx(tab, 2)
    _select_items(tab, a, c)

    QApplication.clipboard().setText("99")
    before_count = tab.undo_stack.count()
    assert paste_clones_at_targets(tab.view)

    assert _root_values(tab) == [1, 99, 2, 3, 99]
    # Single undo step.
    assert tab.undo_stack.count() == before_count + 1
    tab.undo_stack.undo()
    assert list(tab.model.root_item.to_json().keys()) == ["a", "b", "c"]


def test_multi_paste_clones_into_containers(qtbot):
    """When a target is a container, the entries are appended as children."""
    tab = _make_tab(qtbot, {"obj": {"x": 1}, "arr": [10]})

    obj = _idx(tab, 0)
    arr = _idx(tab, 1)
    _select_items(tab, obj, arr)

    QApplication.clipboard().setText('{"y": 2}')
    assert paste_clones_at_targets(tab.view)

    after = tab.model.root_item.to_json()
    assert after["obj"] == {"x": 1, "y": 2}
    assert after["arr"] == [10, 2]


def test_ctrl_v_dispatches_to_multi_paste_when_multiple_rows_selected(qtbot):
    tab = _make_tab(qtbot, {"a": 1, "b": 2, "c": 3})
    _select_items(tab, _idx(tab, 0), _idx(tab, 2))

    QApplication.clipboard().setText("99")
    before_count = tab.undo_stack.count()
    tab.editing.run_tree_action("Pasted JSON", {TreeAction.PASTE})

    assert _root_values(tab) == [1, 99, 2, 3, 99]
    assert tab.undo_stack.count() == before_count + 1


def test_paste_auto_single_selection_keeps_single_target_semantics(qtbot):
    tab = _make_tab(qtbot, {"a": 1, "b": 2})
    _select_items(tab, _idx(tab, 0))

    QApplication.clipboard().setText("99")
    assert paste_auto(tab.view)

    assert _root_values(tab) == [1, 99, 2]


# ---------------------------------------------------------------------------
# Multi-insert (Ctrl+Shift+V) — zip insert-after at paired targets
# ---------------------------------------------------------------------------


def test_multi_insert_zip_inserts_after_each_paired_target(qtbot):
    """Two top-level targets, two clipboard entries -> insert after each
    paired target (target values are not replaced)."""
    tab = _make_tab(qtbot, {"a": 1, "b": 2, "c": 3})
    a = _idx(tab, 0)
    c = _idx(tab, 2)
    _select_items(tab, a, c)

    QApplication.clipboard().setText("[100, 200]")
    before_count = tab.undo_stack.count()
    assert paste_insert_after_zip(tab.view)

    assert _root_values(tab) == [1, 100, 2, 3, 200]
    assert tab.undo_stack.count() == before_count + 1


def test_multi_insert_zip_to_shortest_when_counts_mismatch(qtbot):
    """If targets > entries, extra targets are left untouched."""
    tab = _make_tab(qtbot, {"a": 1, "b": 2, "c": 3})
    _select_items(tab, _idx(tab, 0), _idx(tab, 1), _idx(tab, 2))

    QApplication.clipboard().setText("[100, 200]")
    assert paste_insert_after_zip(tab.view)

    assert _root_values(tab) == [1, 100, 2, 200, 3]


def test_multi_insert_zip_no_deep_scan(qtbot):
    """Multi-insert only uses TOP-LEVEL selected rows (top_level_source_rows),
    so an ancestor's selected child is skipped when the ancestor is also
    selected."""
    tab = _make_tab(qtbot, {"a": {"x": 1}, "b": 2})
    a = _idx(tab, 0)
    ax = _idx(tab, 0, 0)
    _select_items(tab, a, ax)

    QApplication.clipboard().setText("[42]")
    assert paste_insert_after_zip(tab.view)
    # Only "a" was used as target — "a.x" was pruned (descendant of selected ancestor).
    after = tab.model.root_item.to_json()
    assert after["a"] == {"x": 1}
    assert list(after.values()) == [{"x": 1}, 42, 2]


def test_multi_replace_zip_replaces_each_target_with_paired_entry(qtbot):
    tab = _make_tab(qtbot, {"a": 1, "b": 2, "c": 3})
    _select_items(tab, _idx(tab, 0), _idx(tab, 2))

    QApplication.clipboard().setText("[100, 200]")
    before_count = tab.undo_stack.count()
    assert paste_replace_zip(tab.view)

    after = tab.model.root_item.to_json()
    assert after == {"a": 100, "b": 2, "c": 200}
    assert tab.undo_stack.count() == before_count + 1
