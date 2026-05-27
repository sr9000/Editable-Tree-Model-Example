"""Microbenchmarks proving typed action/compensation undo commands are
cheap and never store full-document snapshots.

These complement ``test_perf_smoke.py`` (which asserts wall-clock bounds
on routine operations) and ``test_typed_undo_commands.py`` (which asserts
class identity of pushed commands). Here we measure typed undo/redo on
a deliberately large document and also assert that the bytes stored on
each command are bounded by the affected subset, not the document.
"""

import sys
import time

from PySide6.QtCore import QItemSelectionModel, QModelIndex, Qt

from documents.tab import JsonTab, _EditValueCmd, _MoveRowsCmd, _RemoveRowsCmd
from tree.item import JsonTreeItem
from tree_actions.structure import delete_selection, move_selection_up


def _make_huge_array_tab(qtbot, *, n: int) -> JsonTab:
    tab = JsonTab(lambda *_: None)
    qtbot.addWidget(tab)
    big = [{"k": i, "v": f"item-{i}"} for i in range(n)]
    tab.model.beginResetModel()
    tab.model.root_item = JsonTreeItem(None, big)
    tab.model.endResetModel()
    return tab


def _select_row0(tab: JsonTab, row: int, parent: QModelIndex = QModelIndex()) -> None:
    source_index = tab.model.index(row, 0, parent)
    idx = tab._source_to_view(source_index)
    tab.view.setCurrentIndex(idx)
    tab.view.selectionModel().select(idx, QItemSelectionModel.SelectionFlag.ClearAndSelect)


def _deep_size(obj, _seen=None) -> int:
    """Approximate transitive size in bytes (for perf-bound assertions)."""
    if _seen is None:
        _seen = set()
    oid = id(obj)
    if oid in _seen:
        return 0
    _seen.add(oid)
    s = sys.getsizeof(obj)
    if isinstance(obj, dict):
        for k, v in obj.items():
            s += _deep_size(k, _seen) + _deep_size(v, _seen)
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for v in obj:
            s += _deep_size(v, _seen)
    return s


def test_move_undo_redo_is_o1_on_huge_array(qtbot):
    """20 move-ups on a 3000-row array: undo/redo should be near-instant.

    A snapshot-based history would re-walk the whole 3000-element array
    on every step (O(N) per undo/redo). Typed ``_MoveRowCmd`` runs in
    O(1), so 20 moves round-trip in well under 100ms on developer hw —
    we use a generous CI-stable bound here.
    """
    tab = _make_huge_array_tab(qtbot, n=3000)

    # 20 successive move-ups starting deep inside the array.
    _select_row0(tab, 1500)
    moves = 20
    for _ in range(moves):
        assert move_selection_up(tab.view)

    # Every recorded command is a typed move-rows command.
    for i in range(tab.undo_stack.count()):
        cmd = tab.undo_stack.command(i)
        assert isinstance(cmd, _MoveRowsCmd), f"step {i}: got {type(cmd).__name__}"

    # Time undo + redo round trip.
    start = time.perf_counter()
    for _ in range(moves):
        tab.undo_stack.undo()
    undo_elapsed = time.perf_counter() - start

    start = time.perf_counter()
    for _ in range(moves):
        tab.undo_stack.redo()
    redo_elapsed = time.perf_counter() - start

    # Each step is one ``move_row`` swap on the model. On a 3000-row
    # array, 20 steps complete in ~tens of ms typically; we assert a
    # generous 2.0s ceiling so the test stays green on slow CI.
    assert undo_elapsed < 2.0, f"20x typed undo too slow: {undo_elapsed:.3f}s"
    assert redo_elapsed < 2.0, f"20x typed redo too slow: {redo_elapsed:.3f}s"


def test_move_command_state_is_bounded_constant(qtbot):
    """Every ``_MoveRowCmd`` carries only the parent path + 2 ints —
    its memory footprint must not grow with document size."""
    tab_small = _make_huge_array_tab(qtbot, n=10)
    tab_huge = _make_huge_array_tab(qtbot, n=3000)

    for tab in (tab_small, tab_huge):
        _select_row0(tab, 5 if tab is tab_small else 1500)
        assert move_selection_up(tab.view)

    cmd_small = tab_small.undo_stack.command(0)
    cmd_huge = tab_huge.undo_stack.command(0)
    assert isinstance(cmd_small, _MoveRowsCmd)
    assert isinstance(cmd_huge, _MoveRowsCmd)

    # parent path is the same length, sources list has one entry.
    s_small = _deep_size(cmd_small.__dict__)
    s_huge = _deep_size(cmd_huge.__dict__)
    # Both should be tiny and independent of document size — assert the
    # huge-doc command's dict size doesn't balloon.
    assert s_huge < 4096, f"_MoveRowCmd state too large on huge doc: {s_huge} bytes"
    # And it's not orders of magnitude bigger than on the small doc.
    assert s_huge < s_small * 4 + 4096, f"_MoveRowCmd grows with doc size: small={s_small} huge={s_huge}"


def test_leaf_edit_undo_redo_is_constant_time_on_huge_array(qtbot):
    """Editing a single leaf in a 3000-element array must not pay O(N)
    on undo / redo. The typed command applies a localised diff to the
    affected leaf only.
    """
    tab = _make_huge_array_tab(qtbot, n=3000)

    # Edit the value of an inner element's "v" field.
    inner_obj = tab.model.index(1234, 0, QModelIndex())
    v_value = tab.model.index(1, 2, inner_obj)
    assert tab.commit_set_data(v_value, "PATCHED", Qt.ItemDataRole.EditRole)
    cmd = tab.undo_stack.command(tab.undo_stack.count() - 1)
    assert isinstance(cmd, _EditValueCmd)

    # The stored subtree on each side must be the leaf, not the array.
    assert cmd._old_subtree == "item-1234"
    assert cmd._new_value == "PATCHED"

    # Time 50 undo/redo cycles on a 3000-element document.
    start = time.perf_counter()
    for _ in range(25):
        tab.undo_stack.undo()
        tab.undo_stack.redo()
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, f"25x leaf-edit undo/redo cycles too slow: {elapsed:.3f}s"


def test_no_routine_action_pushes_full_document_snapshot(qtbot):
    """Stress the editor with a mix of typed actions and assert that
    no command holds a copy of the full root document — only affected
    subsets."""
    tab = _make_huge_array_tab(qtbot, n=2000)

    # Drive a representative mix of routine actions.
    _select_row0(tab, 100)
    assert move_selection_up(tab.view)
    _select_row0(tab, 200)
    assert delete_selection(tab.view)
    leaf_v = tab.model.index(1, 2, tab.model.index(300, 0, QModelIndex()))
    assert tab.commit_set_data(leaf_v, "tagged", Qt.ItemDataRole.EditRole)
    name_idx = tab.model.index(0, 0, tab.model.index(0, 0, QModelIndex()))
    assert tab.commit_set_data(name_idx, "renamed", Qt.ItemDataRole.EditRole)

    full_root_json = tab._snapshot()
    full_size = _deep_size(full_root_json)

    for i in range(tab.undo_stack.count()):
        cmd = tab.undo_stack.command(i)
        # Snapshot fields must not exist on the typed commands.
        for forbidden in ("_before", "_after"):
            msg = f"command {i} ({type(cmd).__name__}) has {forbidden}"
            assert not hasattr(cmd, forbidden), msg  # allow: asserts typed cmd shape
        # The transitive size of the command's state must be FAR below
        # the full document size: any single typed entry stores at most
        # one affected subtree (a single inner dict of ~2 fields here).
        cmd_size = _deep_size(cmd.__dict__)
        assert (
            cmd_size < full_size // 4
        ), f"command {i} ({type(cmd).__name__}) state {cmd_size} bytes vs root {full_size} bytes"


def test_delete_inner_stores_only_removed_subtree(qtbot):
    """Deleting one row out of a 3000-row array must not snapshot the
    surviving 2999 rows in the undo command."""
    tab = _make_huge_array_tab(qtbot, n=3000)
    _select_row0(tab, 1500)
    assert delete_selection(tab.view)

    cmd = tab.undo_stack.command(tab.undo_stack.count() - 1)
    assert isinstance(cmd, _RemoveRowsCmd)
    assert len(cmd._removals) == 1
    rec = cmd._removals[0]
    # Removed subtree is one tiny inner dict.
    assert rec["value"] == {"k": 1500, "v": "item-1500"}

    full_size = _deep_size(tab._snapshot())
    cmd_size = _deep_size(cmd.__dict__)
    assert cmd_size < full_size // 100, f"_RemoveRowsCmd state {cmd_size} bytes vs root {full_size} bytes"

    # Round-trip undo / redo timing.
    start = time.perf_counter()
    for _ in range(25):
        tab.undo_stack.undo()
        tab.undo_stack.redo()
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, f"25x delete-row undo/redo cycles too slow: {elapsed:.3f}s"
