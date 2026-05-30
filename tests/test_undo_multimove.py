"""Step 3 — Atomic multi-row move on the undo stack.

Tests for _MoveRowsCmd and JsonTab.push_move_rows.
"""

from PySide6.QtCore import QModelIndex

from documents.tab import JsonTab

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tab(qtbot, data) -> JsonTab:
    tab = JsonTab(lambda *_: None, data=data)
    qtbot.addWidget(tab)
    return tab


def _idx(tab: JsonTab, *path):
    """Return the source QModelIndex at the given integer path."""
    return tab.view_controller.index_from_path(path)


def _keys(tab: JsonTab) -> list:
    return list(tab.data_store.model.root_item.to_json().keys())


def _values(tab: JsonTab) -> list:
    return list(tab.data_store.model.root_item.to_json().values())


# ---------------------------------------------------------------------------
# Test 1 — Same-parent forward block move keeps relative order; single undo
# ---------------------------------------------------------------------------


def test_same_parent_forward_block_move_and_undo(qtbot):
    """Move rows [2,3] forward to position 5 (after e): order preserved; undo restores."""
    # keys: a=0, b=1, c=2, d=3, e=4, f=5
    tab = _make_tab(qtbot, {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6})

    c = tab.data_store.model.index(2, 0, QModelIndex())  # row 2 = "c"
    d = tab.data_store.model.index(3, 0, QModelIndex())  # row 3 = "d"

    # Move c,d after e → target_row = 5
    assert tab.push_move_rows([c, d], QModelIndex(), 5)

    # After move: a, b, e, c, d, f  (rows 2&3 land at position 3 after adjustment)
    result_before_undo = _keys(tab)
    assert result_before_undo.index("c") > result_before_undo.index("e")
    assert result_before_undo.index("d") > result_before_undo.index("e")
    assert result_before_undo.index("c") < result_before_undo.index("d")
    assert result_before_undo.index("d") < result_before_undo.index("f")

    # Single undo step
    assert tab.data_store.undo_stack.count() == 1
    tab.data_store.undo_stack.undo()
    assert _keys(tab) == ["a", "b", "c", "d", "e", "f"]


# ---------------------------------------------------------------------------
# Test 2 — Same-parent backward block move; undo restores
# ---------------------------------------------------------------------------


def test_same_parent_backward_block_move_and_undo(qtbot):
    """Move rows [5,7] backward to position 2: target stays 2."""
    # keys: a=0, b=1, c=2, d=3, e=4, f=5, g=6, h=7
    tab = _make_tab(qtbot, {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6, "g": 7, "h": 8})

    f = tab.data_store.model.index(5, 0, QModelIndex())  # row 5 = "f"
    h = tab.data_store.model.index(7, 0, QModelIndex())  # row 7 = "h"

    assert tab.push_move_rows([f, h], QModelIndex(), 2)

    result = _keys(tab)
    # f and h must appear before their original neighbors c..g (at/after index 2)
    assert result.index("f") >= 2
    assert result.index("h") >= 2
    # relative order of f, h preserved
    assert result.index("f") < result.index("h")
    # a, b still at front
    assert result[:2] == ["a", "b"]

    assert tab.data_store.undo_stack.count() == 1
    tab.data_store.undo_stack.undo()
    assert _keys(tab) == ["a", "b", "c", "d", "e", "f", "g", "h"]


# ---------------------------------------------------------------------------
# Test 3 — Cross-parent multi-row move; undo restores both parents
# ---------------------------------------------------------------------------


def test_cross_parent_multimove_and_undo(qtbot):
    """Lift a.x and b.y into c (array); undo restores both."'"""
    tab = _make_tab(
        qtbot,
        {
            "a": {"x": 10, "a2": 20},
            "b": {"y": 30, "b2": 40},
            "c": [],
        },
    )

    a_idx = _idx(tab, 0)  # "a" object
    b_idx = _idx(tab, 1)  # "b" object
    c_idx = _idx(tab, 2)  # "c" array
    ax = tab.data_store.model.index(0, 0, a_idx)  # a.x
    by = tab.data_store.model.index(0, 0, b_idx)  # b.y

    assert tab.push_move_rows([ax, by], c_idx, 0)

    # c should now contain 2 items
    c_after = tab.data_store.model.get_item(c_idx).to_json()
    assert len(c_after) == 2
    assert 10 in c_after and 30 in c_after

    # a should have lost "x"
    a_after = tab.data_store.model.get_item(a_idx).to_json()
    assert "x" not in a_after
    assert "a2" in a_after

    # Single undo step
    assert tab.data_store.undo_stack.count() == 1
    tab.data_store.undo_stack.undo()

    assert tab.data_store.model.get_item(a_idx).to_json() == {"x": 10, "a2": 20}
    assert tab.data_store.model.get_item(b_idx).to_json() == {"y": 30, "b2": 40}
    assert tab.data_store.model.get_item(c_idx).to_json() == []


def test_cross_parent_move_undo_restores_original_name_after_collision_rename(qtbot):
    """Undo must restore the source field name even if redo auto-renamed on collision."""
    tab = _make_tab(
        qtbot,
        {
            "foo": {"x": 1},
            "bar": {"x": 2},
        },
    )

    foo_idx = _idx(tab, 0)
    bar_idx = _idx(tab, 1)
    bar_x = tab.data_store.model.index(0, 0, bar_idx)

    assert tab.push_move_rows([bar_x], foo_idx, 1)
    assert tab.data_store.model.root_item.to_json() == {
        "foo": {"x": 1, "x_2": 2},
        "bar": {},
    }

    tab.data_store.undo_stack.undo()
    assert tab.data_store.model.root_item.to_json() == {
        "foo": {"x": 1},
        "bar": {"x": 2},
    }

    tab.data_store.undo_stack.redo()
    assert tab.data_store.model.root_item.to_json() == {
        "foo": {"x": 1, "x_2": 2},
        "bar": {},
    }


# ---------------------------------------------------------------------------
# Test 4 — Cycle guard: parent into its own descendant → False, no command
# ---------------------------------------------------------------------------


def test_cycle_guard_returns_false_no_command_pushed(qtbot):
    """Moving a into a.child must be rejected; undo_stack count must stay 0."""
    tab = _make_tab(qtbot, {"top": {"nest": {"deep": 1}}})

    top_idx = _idx(tab, 0)  # "top"
    nest_idx = _idx(tab, 0, 0)  # "top.nest"
    deep_idx = _idx(tab, 0, 0, 0)  # "top.nest.deep"

    original_count = tab.data_store.undo_stack.count()

    # Try to move "top" into "deep"
    assert tab.push_move_rows([top_idx], deep_idx, 0) is False
    assert tab.data_store.undo_stack.count() == original_count

    # Try to move "nest" into itself (same path as target parent)
    assert tab.push_move_rows([nest_idx], nest_idx, 0) is False
    assert tab.data_store.undo_stack.count() == original_count

    # Model must be unchanged
    assert tab.data_store.model.root_item.to_json() == {"top": {"nest": {"deep": 1}}}


# ---------------------------------------------------------------------------
# Test 5 — mergeWith always returns False (each move is its own step)
# ---------------------------------------------------------------------------


def test_merge_with_returns_false(qtbot):
    tab = _make_tab(qtbot, {"a": 1, "b": 2, "c": 3})

    a = tab.data_store.model.index(0, 0, QModelIndex())

    # Move a → end of root: [b, c, a]
    tab.push_move_rows([a], QModelIndex(), 3)
    # After first move: [b, c, a]  →  a is now at index 2
    # Move a → row 0: [a, b, c]
    a2 = tab.data_store.model.index(2, 0, QModelIndex())
    tab.push_move_rows([a2], QModelIndex(), 0)

    # Two separate undo steps
    assert tab.data_store.undo_stack.count() == 2

    tab.data_store.undo_stack.undo()
    tab.data_store.undo_stack.undo()
    assert _keys(tab) == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# Test 6 — push_move_row still works (delegates to push_move_rows)
# ---------------------------------------------------------------------------


def test_push_move_row_still_works(qtbot):
    tab = _make_tab(qtbot, {"a": 1, "b": 2, "c": 3})

    assert tab.push_move_row(QModelIndex(), 0, 2)  # move row 0 ("a") to row 2
    assert _keys(tab) == ["b", "c", "a"]

    assert tab.data_store.undo_stack.count() == 1
    tab.data_store.undo_stack.undo()
    assert _keys(tab) == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# Test 7 — Order-translation invariant: forward block [2,3] → 5 adjusts by 2
# ---------------------------------------------------------------------------


def test_forward_block_move_index_adjustment(qtbot):
    """Forward move [2,3] → row 5: after popping 2 rows before target,
    effective insert row = 5 - 2 = 3."""
    # a=0, b=1, c=2, d=3, e=4, f=5
    tab = _make_tab(qtbot, {"a": 0, "b": 1, "c": 2, "d": 3, "e": 4, "f": 5})

    c = tab.data_store.model.index(2, 0, QModelIndex())
    d = tab.data_store.model.index(3, 0, QModelIndex())
    assert tab.push_move_rows([c, d], QModelIndex(), 5)

    # Expected: a, b, e, c, d, f
    assert _keys(tab) == ["a", "b", "e", "c", "d", "f"]
    tab.data_store.undo_stack.undo()
    assert _keys(tab) == ["a", "b", "c", "d", "e", "f"]


# ---------------------------------------------------------------------------
# Test 8 — Backward block move [5,7] → 2: target stays 2
# ---------------------------------------------------------------------------


def test_backward_block_move_index_invariant(qtbot):
    """Backward move [5,7] → row 2: no adjustment needed (sources after target)."""
    # a=0, b=1, c=2, d=3, e=4, f=5, g=6, h=7
    tab = _make_tab(qtbot, {"a": 0, "b": 1, "c": 2, "d": 3, "e": 4, "f": 5, "g": 6, "h": 7})

    f = tab.data_store.model.index(5, 0, QModelIndex())
    h = tab.data_store.model.index(7, 0, QModelIndex())
    assert tab.push_move_rows([f, h], QModelIndex(), 2)

    # f lands at 2, h at 3; c,d,e,g shift right
    keys = _keys(tab)
    assert keys[:2] == ["a", "b"]
    assert keys[2] == "f"
    assert keys[3] == "h"
    assert "g" in keys
    tab.data_store.undo_stack.undo()
    assert _keys(tab) == ["a", "b", "c", "d", "e", "f", "g", "h"]
