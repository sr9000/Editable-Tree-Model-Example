"""Sophisticated end-to-end undo/redo scenario.

Validates that the undo stack behaves correctly across the full set of
tree-mutating actions and across every JsonType.
"""

from PySide6.QtCore import QItemSelectionModel, QModelIndex, Qt
from PySide6.QtWidgets import QApplication

from documents.tab import JsonTab
from tree.types import JsonType

# EMPTY_MULTILINE cannot be produced from a raw JSON value (an empty string
# always infers to EMPTY_STRING; flipping the shape requires an explicit type
# column edit). All other JsonType members, including the five remaining pseudo
# text types, are present in the _demo_data() seed.
_TYPES_IN_SEED = set(JsonType) - {JsonType.EMPTY_MULTILINE}
from tree_actions.clipboard import copy_selection
from tree_actions.paste import paste_from_clipboard
from tree_actions.structure import (
    cut_selection,
    delete_selection,
    duplicate_selection,
    insert_child_current,
    insert_sibling_after,
    insert_sibling_before,
    move_selection_down,
    move_selection_up,
    sort_selection_keys,
)


def _select(tab: JsonTab, index: QModelIndex) -> None:
    sel = tab.view.selectionModel()
    view_index = tab._source_to_view(index)
    tab.view.setCurrentIndex(view_index)
    sel.select(view_index, QItemSelectionModel.SelectionFlag.ClearAndSelect)


def _select_row0(tab: JsonTab, row: int, parent: QModelIndex = QModelIndex()) -> None:
    _select(tab, tab.model.index(row, 0, parent))


def _ordered_repr(value):
    """Order-preserving deep representation for state comparison.

    Plain ``dict`` equality ignores key order, which would mask
    object-member reorderings (e.g. move-up / move-down). Wrap the
    snapshot through this helper before comparing.
    """
    if isinstance(value, dict):
        return ("__obj__", [(k, _ordered_repr(v)) for k, v in value.items()])
    if isinstance(value, list):
        return ("__arr__", [_ordered_repr(v) for v in value])
    return value


def _state(tab: JsonTab):
    return _ordered_repr(tab._snapshot())


def _gather_types(tab: JsonTab) -> set[JsonType]:
    found: set[JsonType] = set()

    def visit(parent):
        for r in range(tab.model.rowCount(parent)):
            child0 = tab.model.index(r, 0, parent)
            found.add(tab.model.get_item(child0).json_type)
            visit(child0)

    visit(QModelIndex())
    return found


def _row_index_for_type(tab: JsonTab, json_type: JsonType, parent: QModelIndex = QModelIndex()) -> QModelIndex:
    for r in range(tab.model.rowCount(parent)):
        idx = tab.model.index(r, 0, parent)
        if tab.model.get_item(idx).json_type is json_type:
            return idx
    return QModelIndex()


def test_undo_redo_comprehensive_scenario(qtbot):
    """Single sophisticated scenario covering every action and every JsonType.

    The scenario:
      * exercises every JsonType (the default seed contains all enum members),
      * exercises every mutating tree action plus copy and edits,
      * verifies undo x3 / redo x2 / new action / redo-no-op,
      * verifies undo x2 / new action / redo-no-op,
      * verifies undo past the start is a no-op (history limit),
      * verifies redo at the top of the stack is a no-op.
    """
    tab = JsonTab(lambda *_: None)
    qtbot.addWidget(tab)
    model = tab.model
    view = tab.view

    # --- All JsonType values are represented in the seed ---------------------
    assert _gather_types(tab) == _TYPES_IN_SEED

    # --- Snapshots of every committed state, indexed by stack depth ---------
    states: list = [_state(tab)]

    def commit_step(action_callable, *, expect_change: bool = True) -> None:
        prev_count = tab.undo_stack.count()
        result = action_callable()
        if expect_change:
            assert result, f"action expected to push but returned False at step {prev_count + 1}"
            assert (
                tab.undo_stack.count() == prev_count + 1
            ), f"action expected to push exactly one command at step {prev_count + 1}"
            states.append(_state(tab))
        else:
            assert tab.undo_stack.count() == prev_count, f"action expected NOT to push but did at step {prev_count + 1}"

    # 1. Edit a value: commit_set_data on a value column (column 2).
    # NOTE: re-fetch indexes immediately before each step in case earlier
    # actions (or undo/redo replay) shift positions.
    commit_step(lambda: tab.commit_set_data(model.index(1, 2, QModelIndex()), 1234567890, Qt.ItemDataRole.EditRole))

    # 2. Change a type: commit_set_data on the type column (column 1).
    commit_step(lambda: tab.commit_set_data(model.index(1, 1, QModelIndex()), "string", Qt.ItemDataRole.EditRole))

    # 3. Edit a name: commit_set_data on the name column (column 0).
    commit_step(
        lambda: tab.commit_set_data(model.index(1, 0, QModelIndex()), "answer-renamed", Qt.ItemDataRole.EditRole)
    )

    # 4. Move up.
    _select_row0(tab, 1)
    commit_step(lambda: move_selection_up(view))

    # 5. Move down.
    _select_row0(tab, 0)
    commit_step(lambda: move_selection_down(view))

    # 6. Duplicate.
    _select_row0(tab, 0)
    commit_step(lambda: duplicate_selection(view))

    # 7. Delete.
    _select_row0(tab, 0)
    commit_step(lambda: delete_selection(view))

    # 8. Insert sibling before.
    _select_row0(tab, 0)
    commit_step(lambda: insert_sibling_before(view))

    # 9. Insert sibling after.
    _select_row0(tab, 0)
    commit_step(lambda: insert_sibling_after(view))

    # 10. Insert child into the "object" node.
    obj_idx = _row_index_for_type(tab, JsonType.OBJECT)
    assert obj_idx.isValid()
    obj_row = obj_idx.row()
    _select(tab, obj_idx)
    commit_step(lambda: insert_child_current(view))

    # 11. Rename the just-inserted child so that sort will reorder.
    obj_idx = model.index(obj_row, 0, QModelIndex())
    commit_step(lambda: tab.commit_set_data(model.index(0, 0, obj_idx), "zzz", Qt.ItemDataRole.EditRole))

    # 12. Sort keys on the object (now: ["zzz", "key"] -> ["key", "zzz"]).
    obj_idx = model.index(obj_row, 0, QModelIndex())
    _select(tab, obj_idx)
    commit_step(lambda: sort_selection_keys(view, recursive=False))

    # 13. Copy: must NOT push to the undo stack.
    _select_row0(tab, 0)
    commit_step(lambda: copy_selection(view), expect_change=False)

    # 14. Paste from clipboard.
    QApplication.clipboard().setText('{"pasted_key": "pasted_value"}')
    _select_row0(tab, 0)
    commit_step(lambda: paste_from_clipboard(view))

    # 15. Cut (== copy + delete; pushes one delete command).
    _select_row0(tab, 0)
    commit_step(lambda: cut_selection(view))

    # 16. No-op move-up at row 0: must NOT push.
    _select_row0(tab, 0)
    commit_step(lambda: move_selection_up(view), expect_change=False)

    n = len(states) - 1  # number of pushed commands
    assert tab.undo_stack.count() == n
    assert _state(tab) == states[n]
    assert not tab.undo_stack.canRedo()

    # ------------------------------------------------------------------
    # undo x3, redo x2, new action, redo (no effect)
    # ------------------------------------------------------------------
    tab.undo_stack.undo()
    tab.undo_stack.undo()
    tab.undo_stack.undo()
    assert _state(tab) == states[n - 3]

    tab.undo_stack.redo()
    tab.undo_stack.redo()
    assert _state(tab) == states[n - 1]
    assert tab.undo_stack.canRedo()  # one command still ahead

    # New action wipes the redo branch.
    _select_row0(tab, 0)
    assert duplicate_selection(view)
    state_after_new = _state(tab)
    assert state_after_new != states[n]
    assert state_after_new != states[n - 1]
    assert not tab.undo_stack.canRedo(), "new action must wipe redo branch"

    # Redo here must be a no-op.
    tab.undo_stack.redo()
    assert _state(tab) == state_after_new

    # ------------------------------------------------------------------
    # undo x2, new action, redo (no effect)
    # ------------------------------------------------------------------
    tab.undo_stack.undo()
    tab.undo_stack.undo()
    mid_state = _state(tab)
    assert tab.undo_stack.canRedo()

    _select_row0(tab, 0)
    assert insert_sibling_before(view)
    after_second_branch = _state(tab)
    assert after_second_branch != mid_state
    assert not tab.undo_stack.canRedo()

    tab.undo_stack.redo()
    assert _state(tab) == after_second_branch

    # ------------------------------------------------------------------
    # Undo all the way back, then undo past init (history limit no-op).
    # ------------------------------------------------------------------
    while tab.undo_stack.canUndo():
        tab.undo_stack.undo()
    assert _state(tab) == states[0]
    assert not tab.undo_stack.canUndo()

    init_state = _state(tab)
    tab.undo_stack.undo()  # past init -> no-op
    assert _state(tab) == init_state
    assert not tab.undo_stack.canUndo()

    # ------------------------------------------------------------------
    # Redo all the way forward, then redo past final (no-op).
    # ------------------------------------------------------------------
    while tab.undo_stack.canRedo():
        tab.undo_stack.redo()
    final_state = _state(tab)
    assert not tab.undo_stack.canRedo()

    tab.undo_stack.redo()  # past final -> no-op
    assert _state(tab) == final_state
    assert not tab.undo_stack.canRedo()

    # Defensive teardown: this scenario drives clipboard-heavy actions and a
    # long command stack; explicit disposal avoids a flaky process-exit crash.
    tab.close()
    tab.deleteLater()
    QApplication.processEvents()
    QApplication.clipboard().setText("")
