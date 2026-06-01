"""Step 9 — Anchor-based move primitive.

The classic `_MoveRowsCmd` API uses pre-pop integer ``target_row``
which forces every caller to reinvent index arithmetic. The new
``MoveAnchor`` describes the *gap* by reference to a non-moving
sibling (or end-of-parent sentinel) so callers never compute pre-pop
indices.

These tests pin down the anchor API, the `JsonTab.push_move_rows_anchor`
push helper, identity preservation, the cycle guard and the no-op
guard.
"""

from __future__ import annotations

import copy

from PySide6.QtCore import QModelIndex

from documents.tab import JsonTab
from tree_actions.anchors import MoveAnchor, anchor_at_end, anchor_before_index


def _make_tab(qtbot, data) -> JsonTab:
    tab = JsonTab(lambda *_: None, data=data)
    qtbot.addWidget(tab)
    return tab


def _idx(tab: JsonTab, *path: int) -> QModelIndex:
    return tab.view_controller.index_from_path(path)


def _keys(tab: JsonTab) -> list:
    return list(tab.model.root_item.to_json().keys())


# ---------------------------------------------------------------------------
# 1) Anchor factories produce identifiable descriptors
# ---------------------------------------------------------------------------


def test_anchor_at_end_is_distinguishable(qtbot):
    tab = _make_tab(qtbot, {"a": 1, "b": 2})
    anchor = anchor_at_end(QModelIndex(), tab)
    assert isinstance(anchor, MoveAnchor)
    assert anchor.is_at_end


def test_anchor_before_index_records_sibling_path(qtbot):
    tab = _make_tab(qtbot, {"a": 1, "b": 2, "c": 3})
    anchor = anchor_before_index(tab.model.index(1, 0, QModelIndex()), tab)
    assert isinstance(anchor, MoveAnchor)
    assert not anchor.is_at_end
    assert anchor.before_sibling_path == (1,)


# ---------------------------------------------------------------------------
# 2) Same-parent forward block move via anchor
# ---------------------------------------------------------------------------


def test_anchor_move_same_parent_forward_block(qtbot):
    """Move [c,d] before f → [a,b,e,c,d,f]."""
    tab = _make_tab(qtbot, {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6})

    c = tab.model.index(2, 0, QModelIndex())
    d = tab.model.index(3, 0, QModelIndex())
    f = tab.model.index(5, 0, QModelIndex())

    anchor = anchor_before_index(f, tab)
    assert tab.editing.commands.push_move_rows_anchor([c, d], anchor, label="move")
    assert _keys(tab) == ["a", "b", "e", "c", "d", "f"]

    assert tab.undo_stack.count() == 1
    tab.undo_stack.undo()
    assert _keys(tab) == ["a", "b", "c", "d", "e", "f"]


# ---------------------------------------------------------------------------
# 3) Same-parent backward block move via anchor
# ---------------------------------------------------------------------------


def test_anchor_move_same_parent_backward_block(qtbot):
    """Move [f,h] before c → [a,b,f,h,c,d,e,g]."""
    tab = _make_tab(qtbot, {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6, "g": 7, "h": 8})

    c = tab.model.index(2, 0, QModelIndex())
    f = tab.model.index(5, 0, QModelIndex())
    h = tab.model.index(7, 0, QModelIndex())

    anchor = anchor_before_index(c, tab)
    assert tab.editing.commands.push_move_rows_anchor([f, h], anchor, label="move")
    assert _keys(tab) == ["a", "b", "f", "h", "c", "d", "e", "g"]

    tab.undo_stack.undo()
    assert _keys(tab) == ["a", "b", "c", "d", "e", "f", "g", "h"]


# ---------------------------------------------------------------------------
# 4) Cross-parent move via anchor
# ---------------------------------------------------------------------------


def test_anchor_move_cross_parent(qtbot):
    tab = _make_tab(
        qtbot,
        {
            "a": {"x": 10, "a2": 20},
            "b": {"y": 30, "b2": 40},
            "c": [],
        },
    )

    a_idx = _idx(tab, 0)
    b_idx = _idx(tab, 1)
    c_idx = _idx(tab, 2)
    ax = tab.model.index(0, 0, a_idx)
    by = tab.model.index(0, 0, b_idx)

    assert tab.editing.commands.push_move_rows_anchor([ax, by], anchor_at_end(c_idx, tab), label="move into c")

    a_after = tab.model.get_item(a_idx).to_json()
    assert "x" not in a_after and a_after == {"a2": 20}
    b_after = tab.model.get_item(b_idx).to_json()
    assert "y" not in b_after and b_after == {"b2": 40}
    c_after = tab.model.get_item(c_idx).to_json()
    assert len(c_after) == 2 and 10 in c_after and 30 in c_after

    tab.undo_stack.undo()
    assert tab.model.get_item(a_idx).to_json() == {"x": 10, "a2": 20}
    assert tab.model.get_item(b_idx).to_json() == {"y": 30, "b2": 40}
    assert tab.model.get_item(c_idx).to_json() == []


# ---------------------------------------------------------------------------
# 5) Identity preservation — same JsonTreeItem instance after move
# ---------------------------------------------------------------------------


def test_anchor_move_preserves_item_identity(qtbot):
    """A moved row keeps its JsonTreeItem instance, so expansion of the
    moved subtree survives the move (Step 5 builds on top of this)."""
    tab = _make_tab(qtbot, {"a": 1, "b": {"deep": {"deeper": 7}}, "c": 3})

    b_src_idx = tab.model.index(1, 0, QModelIndex())
    b_item_before = tab.model.get_item(b_src_idx)
    deep_item_before = b_item_before.child_items[0]

    # Move "b" to before "a" (i.e. before row 0)
    a_idx = tab.model.index(0, 0, QModelIndex())
    assert tab.editing.commands.push_move_rows_anchor([b_src_idx], anchor_before_index(a_idx, tab), label="move")

    # Locate "b" at its new row 0 — must be the SAME instance.
    b_idx_after = tab.model.index(0, 0, QModelIndex())
    b_item_after = tab.model.get_item(b_idx_after)
    assert b_item_after is b_item_before
    # Subtree identity preserved transitively
    assert b_item_after.child_items[0] is deep_item_before


# ---------------------------------------------------------------------------
# 6) Cycle guard via anchor — refuses moving parent into its descendant
# ---------------------------------------------------------------------------


def test_anchor_move_cycle_guard(qtbot):
    tab = _make_tab(qtbot, {"top": {"nest": {"deep": 1}}})
    before = copy.deepcopy(tab.model.root_item.to_json())

    top_idx = _idx(tab, 0)
    nest_idx = _idx(tab, 0, 0)
    deep_idx = _idx(tab, 0, 0, 0)

    count = tab.undo_stack.count()
    # Move "top" into "deep" — cycle
    assert tab.editing.commands.push_move_rows_anchor([top_idx], anchor_at_end(deep_idx, tab), label="cycle") is False
    # Move "nest" into "nest" — degenerate cycle
    assert tab.editing.commands.push_move_rows_anchor([nest_idx], anchor_at_end(nest_idx, tab), label="cycle") is False
    assert tab.undo_stack.count() == count
    assert tab.model.root_item.to_json() == before


# ---------------------------------------------------------------------------
# 7) No-op guard — anchor equal to current position is rejected silently
# ---------------------------------------------------------------------------


def test_anchor_move_no_op_guard_same_position(qtbot):
    """Moving row N before row N+1 (its own immediate next-sibling) is a no-op
    — same final layout. The command must NOT be pushed."""
    tab = _make_tab(qtbot, {"a": 1, "b": 2, "c": 3})
    before = copy.deepcopy(tab.model.root_item.to_json())
    before_count = tab.undo_stack.count()

    a = tab.model.index(0, 0, QModelIndex())
    b = tab.model.index(1, 0, QModelIndex())
    # "a" → before "b" — but "a" is already immediately before "b". No-op.
    assert tab.editing.commands.push_move_rows_anchor([a], anchor_before_index(b, tab), label="noop") is False
    assert tab.undo_stack.count() == before_count
    assert tab.model.root_item.to_json() == before


def test_anchor_move_no_op_guard_at_end(qtbot):
    """Moving the last row to at_end of its own parent is a no-op."""
    tab = _make_tab(qtbot, {"a": 1, "b": 2, "c": 3})
    before_count = tab.undo_stack.count()

    c = tab.model.index(2, 0, QModelIndex())
    assert tab.editing.commands.push_move_rows_anchor([c], anchor_at_end(QModelIndex(), tab), label="noop") is False
    assert tab.undo_stack.count() == before_count


# ---------------------------------------------------------------------------
# 8) Backward compatibility — push_move_rows(sources, parent, target_row) still works
# ---------------------------------------------------------------------------


def test_legacy_push_move_rows_signature_still_works(qtbot):
    """The pre-step-9 signature must remain green so old callers keep working."""
    tab = _make_tab(qtbot, {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6})
    c = tab.model.index(2, 0, QModelIndex())
    d = tab.model.index(3, 0, QModelIndex())
    assert tab.editing.commands.push_move_rows([c, d], QModelIndex(), 5)
    assert _keys(tab) == ["a", "b", "e", "c", "d", "f"]
    tab.undo_stack.undo()
    assert _keys(tab) == ["a", "b", "c", "d", "e", "f"]
