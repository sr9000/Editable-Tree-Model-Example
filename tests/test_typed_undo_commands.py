"""Tests proving the undo stack uses typed action/compensation commands
instead of full-document snapshots for routine tree mutations.

See ai-memory/phases/phase-3-compensating-undo-plan.md for context.
"""

from PySide6.QtCore import QItemSelectionModel, QModelIndex, Qt
from PySide6.QtWidgets import QApplication

from documents.tab import (
    JsonTab,
    _ChangeTypeCmd,
    _EditValueCmd,
    _InsertRowsCmd,
    _MoveRowsCmd,
    _RemoveRowsCmd,
    _RenameCmd,
    _SortKeysCmd,
)
from tree_actions.paste import paste_from_clipboard
from tree_actions.structure import (
    delete_selection,
    duplicate_selection,
    insert_child_current,
    insert_sibling_after,
    insert_sibling_before,
    move_selection_down,
    move_selection_up,
    sort_selection_keys,
)


def _select_row0(tab: JsonTab, row: int, parent: QModelIndex = QModelIndex()) -> None:
    source_index = tab.data_store.model.index(row, 0, parent)
    idx = tab.view_controller.source_to_view(source_index)
    tab.view.setCurrentIndex(idx)
    tab.view.selectionModel().select(idx, QItemSelectionModel.SelectionFlag.ClearAndSelect)


def _last_command(tab: JsonTab):
    return tab.data_store.undo_stack.command(tab.data_store.undo_stack.count() - 1)


def test_commit_set_data_uses_typed_commands(qtbot):
    tab = JsonTab(lambda *_: None)
    qtbot.addWidget(tab)

    # Edit value (column 2).
    assert tab.editing.commit_set_data(tab.data_store.model.index(1, 2, QModelIndex()), 999, Qt.ItemDataRole.EditRole)
    assert isinstance(_last_command(tab), _EditValueCmd)

    # Rename (column 0).
    assert tab.editing.commit_set_data(
        tab.data_store.model.index(0, 0, QModelIndex()), "renamed", Qt.ItemDataRole.EditRole
    )
    assert isinstance(_last_command(tab), _RenameCmd)

    # Change type (column 1).
    assert tab.editing.commit_set_data(
        tab.data_store.model.index(1, 1, QModelIndex()), "string", Qt.ItemDataRole.EditRole
    )
    assert isinstance(_last_command(tab), _ChangeTypeCmd)


def test_tree_actions_use_typed_commands(qtbot):
    tab = JsonTab(lambda *_: None)
    qtbot.addWidget(tab)
    view = tab.view
    model = tab.data_store.model

    _select_row0(tab, 0)
    assert insert_sibling_before(view)
    assert isinstance(_last_command(tab), _InsertRowsCmd)

    _select_row0(tab, 0)
    assert insert_sibling_after(view)
    assert isinstance(_last_command(tab), _InsertRowsCmd)

    # Insert child into the "object" entry.
    obj_row: int | None = None
    for r in range(model.rowCount(QModelIndex())):
        idx = model.index(r, 0, QModelIndex())
        if model.get_item(idx).name == "object":
            obj_row = r
            break
    assert obj_row is not None
    _select_row0(tab, obj_row)
    assert insert_child_current(view)
    assert isinstance(_last_command(tab), _InsertRowsCmd)

    # Move up / move down.
    _select_row0(tab, 1)
    assert move_selection_up(view)
    assert isinstance(_last_command(tab), _MoveRowsCmd)

    _select_row0(tab, 0)
    assert move_selection_down(view)
    assert isinstance(_last_command(tab), _MoveRowsCmd)

    # Duplicate.
    _select_row0(tab, 0)
    assert duplicate_selection(view)
    assert isinstance(_last_command(tab), _InsertRowsCmd)

    # Delete.
    _select_row0(tab, 0)
    assert delete_selection(view)
    assert isinstance(_last_command(tab), _RemoveRowsCmd)

    # Paste.
    QApplication.clipboard().setText('{"pasted": 1}')
    _select_row0(tab, 0)
    assert paste_from_clipboard(view)
    assert isinstance(_last_command(tab), _InsertRowsCmd)

    # Sort keys on an object child.
    obj_row = None
    for r in range(model.rowCount(QModelIndex())):
        idx = model.index(r, 0, QModelIndex())
        if model.get_item(idx).name == "object":
            obj_row = r
            break
    assert obj_row is not None
    obj_idx = model.index(obj_row, 0, QModelIndex())
    # Insert a child first so a non-trivial sort actually happens.
    _select_row0(tab, obj_row)
    assert insert_child_current(view)
    # Rename it so the sort reorders.
    new_child = model.index(0, 0, obj_idx)
    assert tab.editing.commit_set_data(new_child, "zzz", Qt.ItemDataRole.EditRole)
    _select_row0(tab, obj_row)
    assert sort_selection_keys(view, recursive=False)
    assert isinstance(_last_command(tab), _SortKeysCmd)

    # Verify all expected typed commands were pushed.
    for i in range(tab.data_store.undo_stack.count()):
        cmd = tab.data_store.undo_stack.command(i)
        assert cmd is not None and cmd.text(), f"command at {i} has no label"


def test_large_leaf_edit_does_not_store_full_document(qtbot):
    tab = JsonTab(lambda *_: None)
    qtbot.addWidget(tab)

    # Replace the model with a huge array containing one tiny leaf to edit.

    big = list(range(3000))
    big[7] = "before"
    tab.data_store.model.beginResetModel()
    from tree.item import JsonTreeItem

    tab.data_store.model.root_item = JsonTreeItem(None, big)
    tab.data_store.model.endResetModel()

    target_idx = tab.data_store.model.index(7, 2, QModelIndex())
    assert tab.editing.commit_set_data(target_idx, "after", Qt.ItemDataRole.EditRole)

    cmd = _last_command(tab)
    assert isinstance(cmd, _EditValueCmd)
    # Affected subtree on each side is the leaf only — never the whole 3000-element array.
    assert cmd._old_subtree == "before"
    assert cmd._new_value == "after"
    # Defensive: there is no attribute holding the full document on the cmd.
    for attr in ("_before", "_after"):
        msg = f"_EditValueCmd unexpectedly stores {attr}"
        assert not hasattr(cmd, attr), msg  # allow: asserts typed cmd has no diff fields


def test_delete_stores_removed_subset_only(qtbot):
    tab = JsonTab(lambda *_: None)
    qtbot.addWidget(tab)

    # Find the "object" child {"key": "value"} and delete it.
    obj_row: int | None = None
    for r in range(tab.data_store.model.rowCount(QModelIndex())):
        idx = tab.data_store.model.index(r, 0, QModelIndex())
        if tab.data_store.model.get_item(idx).name == "object":
            obj_row = r
            break
    assert obj_row is not None
    _select_row0(tab, obj_row)
    assert delete_selection(tab.view)

    cmd = _last_command(tab)
    assert isinstance(cmd, _RemoveRowsCmd)
    assert len(cmd._removals) == 1
    rec = cmd._removals[0]
    assert rec["name"] == "object"
    # Stored subtree is the deleted subset only.
    assert rec["value"] == {"key": "value"}
    # Sanity: no full-document field on the command.
    assert not hasattr(cmd, "_before")  # allow: asserts typed cmd has no diff field
    assert not hasattr(cmd, "_after")  # allow: asserts typed cmd has no diff field


def test_sort_stores_sorted_subtree_only(qtbot):
    tab = JsonTab(lambda *_: None)
    qtbot.addWidget(tab)

    # Find the nested "object" entry, add a child so sort reorders.
    obj_row: int | None = None
    for r in range(tab.data_store.model.rowCount(QModelIndex())):
        idx = tab.data_store.model.index(r, 0, QModelIndex())
        if tab.data_store.model.get_item(idx).name == "object":
            obj_row = r
            break
    assert obj_row is not None
    obj_idx = tab.data_store.model.index(obj_row, 0, QModelIndex())
    _select_row0(tab, obj_row)
    assert insert_child_current(tab.view)
    new_child = tab.data_store.model.index(0, 0, obj_idx)
    assert tab.editing.commit_set_data(new_child, "zzz", Qt.ItemDataRole.EditRole)

    _select_row0(tab, obj_row)
    assert sort_selection_keys(tab.view, recursive=False)
    cmd = _last_command(tab)
    assert isinstance(cmd, _SortKeysCmd)
    # Stored subtree is the OBJECT subset, not the whole document.
    assert set(cmd._old_subtree.keys()) == {"zzz", "key"}
    # Defensive: command does not store full document.
    assert not hasattr(cmd, "_before")  # allow: asserts typed cmd has no diff field
    assert not hasattr(cmd, "_after")  # allow: asserts typed cmd has no diff field


def test_move_row_command_is_o1(qtbot):
    """Move rows command should store paths, not a full snapshot."""
    tab = JsonTab(lambda *_: None)
    qtbot.addWidget(tab)

    _select_row0(tab, 1)
    assert move_selection_up(tab.view)
    cmd = _last_command(tab)
    assert isinstance(cmd, _MoveRowsCmd)
    # Compact state only — no snapshot fields.
    assert isinstance(cmd._sources, list) and len(cmd._sources) == 1
    # Step 9: anchor-based addressing replaces target_parent_path / target_row.
    from tree_actions.anchors import MoveAnchor

    assert isinstance(cmd._anchor, MoveAnchor)
    assert isinstance(cmd._anchor.parent_path, tuple)
    assert not hasattr(cmd, "_before")  # allow: asserts typed cmd has no diff field
    assert not hasattr(cmd, "_after")  # allow: asserts typed cmd has no diff field


def test_insert_child_on_empty_root_container(qtbot):
    tab = JsonTab(lambda *_: None, data={}, show_root=True)
    qtbot.addWidget(tab)

    root_src = tab.data_store.model.index(0, 0, QModelIndex())
    root_view = tab.view_controller.source_to_view(root_src)
    tab.view.setCurrentIndex(root_view)
    tab.view.selectionModel().select(root_view, QItemSelectionModel.SelectionFlag.ClearAndSelect)

    assert insert_child_current(tab.view)
    assert tab.data_store.model.root_item.to_json() == {"new_key": None}
    assert isinstance(_last_command(tab), _InsertRowsCmd)
