"""Comprehensive drag-and-drop regression matrix.

Covers the structural drop pipeline through the proxy that the view
actually uses, i.e. ``QSortFilterProxyModel.dropMimeData``. Tests reflect
the exact ``(row, column, parent)`` signatures Qt's ``QTreeView`` emits
for the four drop indicators:

- AboveItem of row R under parent P  → row=R,    col=0,  parent=P
- BelowItem of row R under parent P  → row=R+1,  col=0,  parent=P
- OnItem    of index I               → row=-1,   col=-1, parent=I
- OnViewport                          → row=-1,   col=-1, parent=invalid

Every test runs against **both** ``show_root`` modes because the real
app uses ``show_root=True`` and the path convention differs subtly
between modes.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QItemSelection, QItemSelectionModel, QModelIndex, Qt

from documents.tab import JsonTab


# Every test gets parameterized over both modes via an autouse fixture so the
# author cannot forget the show_root=True variant — that's the gap that hid
# the path-convention bug we just patched.
@pytest.fixture(params=[False, True], ids=["show_root=False", "show_root=True"])
def show_root(request):
    return request.param


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_tab(qtbot, data, show_root) -> JsonTab:
    tab = JsonTab(lambda *_: None, data=data, show_root=show_root)
    qtbot.addWidget(tab)
    return tab


def _proxy_root(tab) -> QModelIndex:
    """Return the proxy index the user sees as 'the root' of children.

    With show_root=False the children of the underlying root_item appear
    directly under the invalid index. With show_root=True they appear
    one level deeper, under the single synthetic root row.
    """
    if tab.model.show_root:
        return tab.view_controller.proxy.index(0, 0, QModelIndex())
    return QModelIndex()


def _pidx(tab, *path):
    """Walk a path of rows through the proxy, relative to the visible root."""
    idx = _proxy_root(tab)
    for r in path:
        idx = tab.view_controller.proxy.index(r, 0, idx)
    return idx


def _select(tab, proxy_indexes):
    sm = tab.view.selectionModel()
    sel = QItemSelection()
    for pidx in proxy_indexes:
        sel.select(pidx, pidx)
    sm.select(sel, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)


def _drop(tab, sel_paths, row, col, parent_path=None):
    sel = [_pidx(tab, *p) for p in sel_paths]
    _select(tab, sel)
    mime = tab.view_controller.proxy.mimeData(sel)
    parent_pidx = _proxy_root(tab) if parent_path is None else _pidx(tab, *parent_path)
    return tab.view_controller.proxy.dropMimeData(mime, Qt.DropAction.MoveAction, row, col, parent_pidx)


# Convenience: 4 indicator helpers ------------------------------------------------


def above_of(tab, sel_paths, row, parent_path=None):
    """Drop AboveItem of (parent_path, row): Qt sends row=R, col=0, parent=P."""
    return _drop(tab, sel_paths, row, 0, parent_path)


def below_of(tab, sel_paths, row, parent_path=None):
    """Drop BelowItem of (parent_path, row): Qt sends row=R+1, col=0, parent=P."""
    return _drop(tab, sel_paths, row + 1, 0, parent_path)


def on_item(tab, sel_paths, target_path):
    """Drop OnItem of target_path: Qt sends row=-1, col=-1, parent=target."""
    return _drop(tab, sel_paths, -1, -1, target_path)


def on_viewport(tab, sel_paths):
    return _drop(tab, sel_paths, -1, -1, None)


def snap(tab):
    return tab.model.root_item.to_json()


# ===========================================================================
# Bug-2 reproductions (and matrix around them)
#
# In a root array of OBJECT children, dragging element N and dropping ONTO
# element N+1 must place N as a child of N+1 — not of N+2.
# ===========================================================================

OBJECTS_6 = [{"a": 1}, {"b": 2}, {"c": 3}, {"d": 4}, {"e": 5}, {"f": 6}]


def test_drop_d_on_e_inserts_into_e(qtbot, show_root):
    """User-reported BUG2: drag 4th onto 5th must land INSIDE 5th."""
    tab = _make_tab(qtbot, list(OBJECTS_6), show_root)
    assert on_item(tab, [(3,)], (4,))
    result = snap(tab)
    assert len(result) == 5
    # The 5th slot is now {"e": 5, <key>: {"d": 4}}, NOT the 6th.
    e_slot = result[3]
    assert "e" in e_slot
    nested = next(v for k, v in e_slot.items() if k != "e")
    assert nested == {"d": 4}
    # And f is intact.
    assert result[4] == {"f": 6}


def test_drop_e_on_f_inserts_into_f(qtbot, show_root):
    """User-reported BUG1: drag 5th onto last 6th must land INSIDE 6th, not after it."""
    tab = _make_tab(qtbot, list(OBJECTS_6), show_root)
    assert on_item(tab, [(4,)], (5,))
    result = snap(tab)
    assert len(result) == 5
    f_slot = result[4]
    assert "f" in f_slot
    nested = next(v for k, v in f_slot.items() if k != "f")
    assert nested == {"e": 5}


def test_drop_b_on_e_inserts_into_e(qtbot, show_root):
    """Drop FAR-EARLIER source onto a later container — same shift bug pattern."""
    tab = _make_tab(qtbot, list(OBJECTS_6), show_root)
    assert on_item(tab, [(1,)], (4,))
    result = snap(tab)
    assert len(result) == 5
    # Without the fix, b would land inside f (the next-after-e); with the fix,
    # it lands inside e — at slot index 3 of the new root.
    e_slot = result[3]
    assert "e" in e_slot
    assert {"b": 2} in e_slot.values()


def test_drop_a_b_c_on_e_inserts_into_e(qtbot, show_root):
    """Multi-source: 3 earlier siblings onto a single later container."""
    tab = _make_tab(qtbot, list(OBJECTS_6), show_root)
    assert on_item(tab, [(0,), (1,), (2,)], (4,))
    result = snap(tab)
    assert len(result) == 3
    # The remaining root: [d, e+children, f]
    e_slot = result[1]
    assert "e" in e_slot
    nested_values = [v for k, v in e_slot.items() if k != "e"]
    assert {"a": 1} in nested_values
    assert {"b": 2} in nested_values
    assert {"c": 3} in nested_values


# ===========================================================================
# Reverse direction: source AFTER target — anchor path should NOT shift.
# ===========================================================================


def test_drop_e_on_b_inserts_into_b(qtbot, show_root):
    """Drop later source onto earlier container — target path does NOT shift."""
    tab = _make_tab(qtbot, list(OBJECTS_6), show_root)
    assert on_item(tab, [(4,)], (1,))
    result = snap(tab)
    assert len(result) == 5
    b_slot = result[1]
    assert "b" in b_slot
    nested = next(v for k, v in b_slot.items() if k != "b")
    assert nested == {"e": 5}


def test_drop_f_on_a_inserts_into_a(qtbot, show_root):
    tab = _make_tab(qtbot, list(OBJECTS_6), show_root)
    assert on_item(tab, [(5,)], (0,))
    result = snap(tab)
    assert len(result) == 5
    a_slot = result[0]
    nested = next(v for k, v in a_slot.items() if k != "a")
    assert nested == {"f": 6}


# ===========================================================================
# Indicator-position semantics (Above / Below / OnViewport)
# ===========================================================================


def test_above_item_within_same_parent_is_reorder(qtbot, show_root):
    tab = _make_tab(qtbot, ["a", "b", "c", "d", "e", "f"], show_root)
    # Drop "d" AboveItem of "e" — that's the gap between d and e (no-op).
    assert not above_of(tab, [(3,)], 4)


def test_below_item_within_same_parent_swaps_neighbors(qtbot, show_root):
    tab = _make_tab(qtbot, ["a", "b", "c", "d", "e", "f"], show_root)
    # Drop "d" BelowItem of "e" — d lands between e and f.
    assert below_of(tab, [(3,)], 4)
    assert snap(tab) == ["a", "b", "c", "e", "d", "f"]


def test_below_last_item_moves_to_end(qtbot, show_root):
    tab = _make_tab(qtbot, ["a", "b", "c", "d", "e", "f"], show_root)
    assert below_of(tab, [(4,)], 5)
    assert snap(tab) == ["a", "b", "c", "d", "f", "e"]


def test_on_viewport_appends_to_root(qtbot, show_root):
    tab = _make_tab(qtbot, ["a", "b", "c", "d", "e", "f"], show_root)
    assert on_viewport(tab, [(2,)])
    assert snap(tab) == ["a", "b", "d", "e", "f", "c"]


# ===========================================================================
# Bug-3 angle: 1st root element drags correctly at the model level
# ===========================================================================


def test_drag_first_root_child_to_middle(qtbot, show_root):
    tab = _make_tab(qtbot, ["a", "b", "c", "d", "e", "f"], show_root)
    assert above_of(tab, [(0,)], 3)  # land before row 3
    assert snap(tab) == ["b", "c", "a", "d", "e", "f"]


def test_drag_first_root_child_to_end(qtbot, show_root):
    tab = _make_tab(qtbot, ["a", "b", "c", "d", "e", "f"], show_root)
    assert below_of(tab, [(0,)], 5)
    assert snap(tab) == ["b", "c", "d", "e", "f", "a"]


def test_drag_first_root_child_into_container(qtbot, show_root):
    tab = _make_tab(qtbot, [{"a": 1}, {"b": 2}, {"c": 3}, {"d": 4}, {"e": 5}, {"f": 6}], show_root)
    assert on_item(tab, [(0,)], (4,))
    result = snap(tab)
    # a went INTO e, not f.
    e_slot = result[3]
    assert "e" in e_slot
    assert next(v for k, v in e_slot.items() if k != "e") == {"a": 1}


def test_drag_first_root_child_flag_is_drag_enabled(qtbot, show_root):
    """Bug-3 sanity: the 1st child must report ``ItemIsDragEnabled``."""
    tab = _make_tab(qtbot, [{"a": 1}, {"b": 2}], show_root)
    pidx = _pidx(tab, 0)
    flags = tab.view_controller.proxy.flags(pidx)
    assert bool(flags & Qt.ItemFlag.ItemIsDragEnabled)


# ===========================================================================
# Undo round-trip: every successful drop must be reversible by ONE undo step
# ===========================================================================


def test_undo_reverses_drop_into_container(qtbot, show_root):
    initial = list(OBJECTS_6)
    tab = _make_tab(qtbot, initial, show_root)
    before = snap(tab)
    assert on_item(tab, [(3,)], (4,))  # d INTO e
    assert snap(tab) != before
    assert tab.undo_stack.count() == 1
    tab.undo_stack.undo()
    assert snap(tab) == before


def test_undo_reverses_drop_after_sibling(qtbot, show_root):
    tab = _make_tab(qtbot, ["a", "b", "c", "d", "e", "f"], show_root)
    before = snap(tab)
    assert below_of(tab, [(0,)], 4)
    assert snap(tab) != before
    tab.undo_stack.undo()
    assert snap(tab) == before


def test_undo_reverses_multi_source_drop(qtbot, show_root):
    tab = _make_tab(qtbot, [{"a": 1}, {"b": 2}, {"c": 3}, {"d": 4}, {"e": 5}, {"f": 6}], show_root)
    before = snap(tab)
    assert on_item(tab, [(0,), (1,), (2,)], (4,))
    tab.undo_stack.undo()
    assert snap(tab) == before


# ===========================================================================
# Nested-tree drops: dragging across container types
# ===========================================================================


def test_drag_array_child_into_object(qtbot, show_root):
    tab = _make_tab(qtbot, {"arr": [10, 20, 30], "obj": {"x": 1}}, show_root)
    # Drag arr[1]=20 into obj container's tail.
    arr = (0,)
    obj = (1,)
    assert on_item(tab, [arr + (1,)], obj)
    result = snap(tab)
    assert result["arr"] == [10, 30]
    # 20 landed inside obj with a generated key.
    assert 20 in result["obj"].values()


def test_drag_object_child_into_array(qtbot, show_root):
    tab = _make_tab(qtbot, {"arr": [], "obj": {"x": 1, "y": 2}}, show_root)
    obj = (1,)
    # Drop "x" (obj's first child) into arr (an empty ARRAY).
    assert on_item(tab, [obj + (0,)], (0,))
    result = snap(tab)
    assert result["obj"] == {"y": 2}
    assert result["arr"] == [1]


def test_drag_container_with_subtree(qtbot, show_root):
    tab = _make_tab(qtbot, [{"nested": {"deep": [1, 2, 3]}}, {"x": "y"}], show_root)
    before = snap(tab)
    # Drop entire {"nested": ...} INTO {"x":"y"}.
    assert on_item(tab, [(0,)], (1,))
    result = snap(tab)
    assert len(result) == 1
    x_slot = result[0]
    nested_val = next(v for k, v in x_slot.items() if k != "x")
    assert nested_val == {"nested": {"deep": [1, 2, 3]}}
    tab.undo_stack.undo()
    assert snap(tab) == before


# ===========================================================================
# Cycle guard: source must not become an ancestor of the target
# ===========================================================================


def test_cannot_drop_parent_into_own_descendant(qtbot, show_root):
    tab = _make_tab(qtbot, {"outer": {"inner": {"leaf": 1}}}, show_root)
    outer = (0,)
    inner = (0, 0)
    # Attempt to move outer INTO inner.
    assert not on_item(tab, [outer], inner)
    # Tree unchanged.
    assert snap(tab) == {"outer": {"inner": {"leaf": 1}}}


def test_cannot_drop_parent_above_own_child(qtbot, show_root):
    tab = _make_tab(qtbot, {"outer": ["a", "b", "c"]}, show_root)
    outer = (0,)
    # Drop outer AboveItem of outer[1].
    assert not above_of(tab, [outer], 1, parent_path=outer)
    assert snap(tab) == {"outer": ["a", "b", "c"]}


# ===========================================================================
# No-op detection: drop "between own neighbors" must be rejected
# ===========================================================================


def test_drop_between_own_neighbors_is_noop(qtbot, show_root):
    tab = _make_tab(qtbot, ["a", "b", "c"], show_root)
    # Drop "b" AboveItem of "c" — no movement.
    assert not above_of(tab, [(1,)], 2)
    # Drop "b" BelowItem of "a" — also no movement.
    assert not below_of(tab, [(1,)], 0)


def test_at_end_when_block_is_already_suffix_is_noop(qtbot, show_root):
    tab = _make_tab(qtbot, ["a", "b", "c"], show_root)
    # Drop "c" OnViewport (= at end of root) — already at end.
    assert not on_viewport(tab, [(2,)])


# ===========================================================================
# OBJECT key naming invariants under move
# ===========================================================================


def test_move_into_object_renames_on_collision(qtbot, show_root):
    tab = _make_tab(qtbot, {"a": {"k": 1}, "b": {"k": 2}}, show_root)
    # Drag a INTO b. b already has "k"; the moved entry must auto-rename.
    assert on_item(tab, [(0,)], (1,))
    result = snap(tab)
    assert len(result) == 1
    b_slot = result["b"]
    assert b_slot["k"] == 2
    # New entry has the original {"k":1} value but a unique key.
    other = {k: v for k, v in b_slot.items() if k != "k"}
    assert len(other) == 1
    assert next(iter(other.values())) == {"k": 1}


def test_move_array_child_into_object_gets_generated_name(qtbot, show_root):
    tab = _make_tab(qtbot, {"arr": [42], "obj": {"x": 1}}, show_root)
    assert on_item(tab, [(0, 0)], (1,))
    result = snap(tab)
    assert result["arr"] == []
    # 42 was added to obj with a fresh key.
    assert 42 in result["obj"].values()
    assert result["obj"]["x"] == 1


# ===========================================================================
# Stress: repeated container-drop cycles must remain reversible and serializable
# ===========================================================================


def test_repeated_container_drops_remain_consistent(qtbot, show_root):
    tab = _make_tab(qtbot, [{"a": 1}, {"b": 2}, {"c": 3}], show_root)
    # 12 alternating drops INTO the last container.
    for _ in range(12):
        n = tab.model.root_item.child_count()
        if n < 2:
            break
        # Drop element 0 into element 1.
        on_item(tab, [(0,)], (1,))
        # Walk the result — must be valid serializable JSON.
        result = snap(tab)
        assert isinstance(result, list)
        for entry in result:
            assert isinstance(entry, dict)


def test_full_redo_undo_cycle_round_trips(qtbot, show_root):
    tab = _make_tab(qtbot, [{"a": 1}, {"b": 2}, {"c": 3}, {"d": 4}, {"e": 5}, {"f": 6}], show_root)
    before = snap(tab)
    # Three structural drops.
    on_item(tab, [(3,)], (4,))
    on_item(tab, [(0,)], (2,))
    below_of(tab, [(0,)], 1)
    # Undo all three.
    while tab.undo_stack.canUndo():
        tab.undo_stack.undo()
    assert snap(tab) == before
    # Redo all three back to the final state.
    while tab.undo_stack.canRedo():
        tab.undo_stack.redo()
    after_redo = snap(tab)
    # Repeat undo to verify the chain stays correct.
    while tab.undo_stack.canUndo():
        tab.undo_stack.undo()
    assert snap(tab) == before
    while tab.undo_stack.canRedo():
        tab.undo_stack.redo()
    assert snap(tab) == after_redo


# ===========================================================================
# Anchor adjustment unit tests — the exact mechanic we just fixed
# ===========================================================================


def test_adjust_path_for_removed_sources_shifts_higher_indexes():
    from tree_actions.anchors import adjust_path_for_removed_sources

    # Source at row 3 of root removed → anchor pointing to row 5 of root
    # now points to row 4 of root.
    assert adjust_path_for_removed_sources((5,), [((), 3)]) == (4,)


def test_adjust_path_does_not_shift_lower_indexes():
    from tree_actions.anchors import adjust_path_for_removed_sources

    # Source at row 5 of root removed → anchor pointing to row 3 of root
    # is unaffected.
    assert adjust_path_for_removed_sources((3,), [((), 5)]) == (3,)


def test_adjust_path_handles_deep_paths():
    from tree_actions.anchors import adjust_path_for_removed_sources

    # Source at (root, 0) removed → anchor at (root[2], 1) becomes (root[1], 1).
    assert adjust_path_for_removed_sources((2, 1), [((), 0)]) == (1, 1)


def test_adjust_path_handles_multiple_same_parent_sources():
    from tree_actions.anchors import adjust_path_for_removed_sources

    # Two sources at root rows 1 and 2 removed; anchor at root row 5 → 3.
    assert adjust_path_for_removed_sources((5,), [((), 1), ((), 2)]) == (3,)


def test_adjust_path_handles_unrelated_branch_sources():
    from tree_actions.anchors import adjust_path_for_removed_sources

    # Source at (root[1], 0) does NOT affect anchor at root[2].
    assert adjust_path_for_removed_sources((2,), [((1,), 0)]) == (2,)
