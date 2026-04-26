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


def _view_idx(tab: JsonTab, source_index: QModelIndex) -> QModelIndex:
    return tab._source_to_view(source_index)


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


def test_commit_set_data_on_big_tree_is_responsive(qtbot):
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
    v_inner = _view_idx(tab, inner)
    tab.view.setCurrentIndex(v_inner)
    tab.view.selectionModel().select(v_inner, QItemSelectionModel.SelectionFlag.ClearAndSelect)

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
    """``push_edit_value`` skips pushing when nothing changed (subset compare)."""
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
    # Setting the same value must not push.
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
    v_inner = _view_idx(tab, inner)
    tab.view.setCurrentIndex(v_inner)
    tab.view.selectionModel().select(v_inner, QItemSelectionModel.SelectionFlag.ClearAndSelect)

    before = tab._snapshot()
    assert duplicate_selection(tab.view)
    after = tab._snapshot()
    assert after != before

    tab.undo_stack.undo()
    assert tab._snapshot() == before

    tab.undo_stack.redo()
    assert tab._snapshot() == after


def test_expansion_preserved_across_undo_redo(qtbot):
    """The view's expansion state must survive undo / redo.

    Typed commands emit minimal model signals (no ``beginResetModel``),
    so any sibling that was expanded before the mutation must remain
    expanded after undo / redo.
    """
    tab = _make_big_tab(qtbot, fanout=200)

    # Expand the seeded "object" node and the big "array" node.
    obj_idx = None
    arr_idx = None
    for r in range(tab.model.rowCount(QModelIndex())):
        name = tab.model.data(tab.model.index(r, 0, QModelIndex()))
        if name == "object":
            obj_idx = tab.model.index(r, 0, QModelIndex())
        elif name == "array":
            arr_idx = tab.model.index(r, 0, QModelIndex())
    assert obj_idx is not None and arr_idx is not None
    v_obj = _view_idx(tab, obj_idx)
    v_arr = _view_idx(tab, arr_idx)
    tab.view.setExpanded(v_obj, True)
    tab.view.setExpanded(v_arr, True)
    assert tab.view.isExpanded(v_obj)
    assert tab.view.isExpanded(v_arr)

    # Edit a leaf inside the array — sibling expansion must survive
    # the resulting commit + the subsequent undo + redo.
    inner_v = tab.model.index(10, 2, arr_idx)
    assert tab.commit_set_data(inner_v, {"k": 99, "v": "edited"}, Qt.ItemDataRole.EditRole)

    # Re-fetch indexes (model identity may shift after restore-then-redo).
    obj_idx = None
    arr_idx = None
    for r in range(tab.model.rowCount(QModelIndex())):
        name = tab.model.data(tab.model.index(r, 0, QModelIndex()))
        if name == "object":
            obj_idx = tab.model.index(r, 0, QModelIndex())
        elif name == "array":
            arr_idx = tab.model.index(r, 0, QModelIndex())
    assert tab.view.isExpanded(_view_idx(tab, obj_idx))
    assert tab.view.isExpanded(_view_idx(tab, arr_idx))

    tab.undo_stack.undo()
    assert tab.view.isExpanded(_view_idx(tab, obj_idx))
    assert tab.view.isExpanded(_view_idx(tab, arr_idx))

    tab.undo_stack.redo()
    assert tab.view.isExpanded(_view_idx(tab, obj_idx))
    assert tab.view.isExpanded(_view_idx(tab, arr_idx))


def test_undo_walking_is_responsive(qtbot):
    """Undo / redo on a 3000-row array should stay responsive."""
    import time

    tab = _make_big_tab(qtbot, fanout=3000)
    arr_idx = None
    for r in range(tab.model.rowCount(QModelIndex())):
        if tab.model.data(tab.model.index(r, 0, QModelIndex())) == "array":
            arr_idx = tab.model.index(r, 0, QModelIndex())
            break
    inner = tab.model.index(1500, 0, arr_idx)
    v_inner = _view_idx(tab, inner)
    tab.view.setCurrentIndex(v_inner)
    tab.view.selectionModel().select(v_inner, QItemSelectionModel.SelectionFlag.ClearAndSelect)

    # 10 mutations.
    for _ in range(10):
        assert move_selection_up(tab.view)

    start = time.perf_counter()
    for _ in range(10):
        tab.undo_stack.undo()
    undo_elapsed = time.perf_counter() - start

    start = time.perf_counter()
    for _ in range(10):
        tab.undo_stack.redo()
    redo_elapsed = time.perf_counter() - start

    # Generous bound for slow CI machines; on developer hardware these
    # complete in ~150-200ms total.
    assert undo_elapsed < 5.0, f"10x undo too slow: {undo_elapsed:.2f}s"
    assert redo_elapsed < 5.0, f"10x redo too slow: {redo_elapsed:.2f}s"
