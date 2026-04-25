"""Performance smoke tests for Phase 1 + 3a optimizations.

These are NOT strict timing assertions (CI machines vary); they just
ensure that the operations complete in reasonable wall time on a
non-trivial tree, and that ``row()`` is O(1) per call after the lazy
re-numbering rather than O(siblings).
"""

import time

from PySide6.QtCore import QItemSelectionModel, QModelIndex, Qt

from json_tab import JsonTab
from tree_view import duplicate_selection, move_selection_up


def _make_big_tab(qtbot, *, fanout: int = 200) -> JsonTab:
    """Build a tab whose root has ``fanout`` array members of small dicts."""
    tab = JsonTab(lambda *_: None)
    qtbot.addWidget(tab)

    big_array = [{"k": i, "v": f"item-{i}"} for i in range(fanout)]
    arr_value_idx = None
    # Find the seed "array" key.
    for r in range(tab.model.rowCount(QModelIndex())):
        name_idx = tab.model.index(r, 0, QModelIndex())
        if tab.model.data(name_idx) == "array":
            arr_value_idx = tab.model.index(r, 2, QModelIndex())
            break
    assert arr_value_idx is not None
    assert tab.commit_set_data(arr_value_idx, big_array, Qt.ItemDataRole.EditRole)
    return tab


def test_row_index_is_o1_per_call(qtbot):
    """``row()`` must be ~O(1) per call after the lazy re-numbering pass.

    With 5000 siblings, calling row() on every one should be ~linear in
    the population (one pass to re-number plus N attribute reads), not
    quadratic (N * sibling-scan).
    """
    tab = _make_big_tab(qtbot, fanout=5000)
    array_item = None
    for r in range(tab.model.rowCount(QModelIndex())):
        name_idx = tab.model.index(r, 0, QModelIndex())
        if tab.model.data(name_idx) == "array":
            array_item = tab.model.get_item(name_idx)
            break
    assert array_item is not None
    assert len(array_item.child_items) == 5000

    start = time.perf_counter()
    rows = [c.row() for c in array_item.child_items]
    elapsed = time.perf_counter() - start

    # Sanity: row() returned the correct index for every sibling.
    assert rows == list(range(5000))

    # 5000 row() calls should be far under one second on any modern box.
    # On an O(N^2) implementation this loop takes seconds; we assert a
    # generous upper bound to remain CI-stable.
    assert elapsed < 1.0, f"row() loop too slow: {elapsed:.3f}s"


def test_commit_mutation_on_big_tree_is_responsive(qtbot):
    """A single mutation on a 2000-member array must complete quickly."""
    tab = _make_big_tab(qtbot, fanout=2000)

    arr_idx = None
    for r in range(tab.model.rowCount(QModelIndex())):
        if tab.model.data(tab.model.index(r, 0, QModelIndex())) == "array":
            arr_idx = tab.model.index(r, 0, QModelIndex())
            break
    assert arr_idx is not None

    # Select an inner row of the big array and move it up.
    inner = tab.model.index(500, 0, arr_idx)
    tab.view.setCurrentIndex(inner)
    tab.view.selectionModel().select(inner, QItemSelectionModel.SelectionFlag.ClearAndSelect)

    start = time.perf_counter()
    assert move_selection_up(tab.view)
    elapsed_move = time.perf_counter() - start

    # Generous bound: a single move on 2k siblings should be well under 2s.
    assert elapsed_move < 2.0, f"move_selection_up too slow: {elapsed_move:.3f}s"

    # Undo and redo should each be similarly responsive.
    start = time.perf_counter()
    tab.undo_stack.undo()
    elapsed_undo = time.perf_counter() - start
    assert elapsed_undo < 2.0, f"undo too slow: {elapsed_undo:.3f}s"

    start = time.perf_counter()
    tab.undo_stack.redo()
    elapsed_redo = time.perf_counter() - start
    assert elapsed_redo < 2.0, f"redo too slow: {elapsed_redo:.3f}s"


def test_no_op_set_data_does_not_push(qtbot):
    """The fast-path ``_tree_equals_data`` skips pushing when nothing changed."""
    tab = _make_big_tab(qtbot, fanout=500)
    initial_count = tab.undo_stack.count()

    # Re-applying the duplicate of an array element produces an identical
    # subtree; the no-op detector must skip the push.
    arr_idx = None
    for r in range(tab.model.rowCount(QModelIndex())):
        if tab.model.data(tab.model.index(r, 0, QModelIndex())) == "array":
            arr_idx = tab.model.index(r, 0, QModelIndex())
            break
    assert arr_idx is not None

    inner_value = tab.model.index(0, 2, arr_idx)
    same = tab.model.get_item(inner_value).to_json()
    # Setting the same value must not push (commit_mutation returns False).
    assert not tab.commit_set_data(inner_value, same, Qt.ItemDataRole.EditRole)
    assert tab.undo_stack.count() == initial_count


def test_duplicate_then_undo_redo_on_big_array(qtbot):
    tab = _make_big_tab(qtbot, fanout=1000)

    arr_idx = None
    for r in range(tab.model.rowCount(QModelIndex())):
        if tab.model.data(tab.model.index(r, 0, QModelIndex())) == "array":
            arr_idx = tab.model.index(r, 0, QModelIndex())
            break
    assert arr_idx is not None

    inner = tab.model.index(50, 0, arr_idx)
    tab.view.setCurrentIndex(inner)
    tab.view.selectionModel().select(inner, QItemSelectionModel.SelectionFlag.ClearAndSelect)

    before = tab._snapshot()
    assert duplicate_selection(tab.view)
    after = tab._snapshot()
    assert after != before

    tab.undo_stack.undo()
    assert tab._snapshot() == before

    tab.undo_stack.redo()
    assert tab._snapshot() == after
