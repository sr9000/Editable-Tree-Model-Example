# Phase 3 — Tree Mutation Actions

_Status: ✅ **complete** (2026-04-26). See
[`phase-3-compensating-undo-plan.md`](phase-3-compensating-undo-plan.md)
for the follow-up that replaced whole-document snapshot history with
typed action/compensation commands._

## Goal

Make the tree fully **manipulable** through the UI: cut, copy, paste,
delete, duplicate, move up/down, sort keys, plus undo/redo. After this
phase, editing a JSON document feels like editing in a real outliner.

## Entry criteria

- Phase 2 complete: name/type editing works, model mutations go through
  a unified `JsonTreeModel` API.
- ✅ `JsonTreeModel.change_type` and `JsonTreeModel.typeChanged` signal
  are available — Phase 3 commands hook into them.

## Phase 1 / 2 carry-over (already done)

These items appeared in earlier drafts of this phase but were already
shipped in Phases 1–2; they are listed here only for traceability.

- [x] [hygiene] Drop the "Insert Column" context menu entry and its
      toolbar action — already removed in Phase 1.
- [x] [hygiene] Drop `model_actions.action_insert_column` — already gone.

## Exit criteria

- ✅ Context menu and keyboard shortcuts cover: Cut (Ctrl+X), Copy (Ctrl+C),
  Paste (Ctrl+V), Delete (Del), Duplicate (Ctrl+D), Move Up (Alt+↑),
  Move Down (Alt+↓), Insert Sibling Before / After, Sort Keys
  (Ctrl+Alt+S).
- ✅ All mutations go through a `QUndoStack`; Ctrl+Z / Ctrl+Y reverse and
  reapply them (typed command per action — never a whole-document
  snapshot).
- ✅ Pasting clipboard JSON into a node either replaces (when types
  match) or inserts as child / sibling depending on the target.
- ⏳ Auto-reopen value editor after a successful type change is **still
  deferred** to a future polish phase — see open item below.

## Work items

### Clipboard
- [x] [tree] `Copy` action: serialize selection to JSON via
      `tree_view.to_json` (already exists). Multi-selection copies a JSON
      array. — `tree_view.copy_selection`. Uses the
      `application/x-json-tree` MIME so paste round-trips type tags.
- [x] [tree] `Cut` = `Copy` + `Delete`. — `tree_view.cut_selection`,
      wired into `show_context_menu` and the `Ctrl+X` shortcut.
- [x] [tree] `Paste`: parse clipboard text as JSON; if target is
      OBJECT/ARRAY, insert as child; otherwise insert as sibling after.
      — `tree_view.paste_from_clipboard` with name-collision avoidance
      under OBJECT parents.
- [x] [tree] `Delete`: remove selected rows. — `tree_view.delete_selection`,
      wired in the context menu and `Qt.Key_Delete` shortcut.
- [x] [shell] Replace the `MainWindow.copy_action` placeholder. —
      `JsonTab._run_tree_action(...)` is the single entry point; the
      old `copy_action` placeholder no longer applies.

### Sibling / child insertion polish
- [x] [tree] **Insert Sibling Before** action.
      — `tree_view.insert_sibling_before` /
        `JsonTab.insert_sibling_before`.
- [x] [tree] **Insert Child** keyboard shortcut + context-menu entry.
      — `tree_view.insert_child_current` /
        `JsonTab.insert_child`.
- [x] [tree] **Duplicate** (Ctrl+D): deep-copies the selected
      `JsonTreeItem` subtree and inserts as next sibling, with
      `_copy` / `_copy_2` collision suffixes under OBJECT parents.
      — `tree_view.duplicate_selection`.
- [x] [tree] **Move Up / Move Down**: in-place pop+insert with
      `beginMoveRows` / `endMoveRows` (no `layoutChanged`).
      — `JsonTreeModel.move_row`.
- [x] [tree] **Sort Keys** (recursive option): only meaningful for
      `OBJECT` parents; sort `child_items` by `name`.
      — `JsonTreeModel.sort_keys`,
        `tree_view.sort_selection_keys(recursive=...)`.

### Auto-reopen value editor (deferred)
- [ ] [ux] After `JsonTreeModel.typeChanged`, reopen the value editor
      with the new delegate **only when the change came from the user**,
      not from programmatic `setData`. Approaches to investigate:
      - Track an "interactive" flag on the type combo's commit path and
        forward it through the `typeChanged` signal.
      - Or: hook `view.commitData` from `JsonTypeDelegate` and call
        `view.edit(value_index)` only from there — the programmatic
        `model.setData` path bypasses delegates and so will not re-edit.
      - Either approach must keep
        `tests/test_smoke_mainwindow.py::test_cycling_inline_types_does_not_log_edit_failed`
        green.
      — `json_tab.py:JsonTab._on_type_changed`,
        `delegate.py:JsonTypeDelegate.setModelData`
      Carried forward to Phase 5 (UX polish).

### Remove dead entries
- [x] [hygiene] Drop the "Insert Column" context menu entry and its
      toolbar action — already done in Phase 1.
- [x] [hygiene] Drop `model_actions.action_insert_column` — already done.

### Undo / redo
- [x] [tree] Introduce a `QUndoStack` per `JsonTab`. Each mutation
      pushes a typed `QUndoCommand` (`_MoveRowCmd`, `_RenameCmd`,
      `_EditValueCmd`, `_ChangeTypeCmd`, `_InsertRowsCmd`,
      `_RemoveRowsCmd`, `_SortKeysCmd`).
      Whole-document `_SnapshotCommand` and `commit_mutation()` were
      added as a fallback during implementation, then **removed
      entirely** as part of the Phase 3 follow-up — see
      [`phase-3-compensating-undo-plan.md`](phase-3-compensating-undo-plan.md).
- [x] [tree] Bind `MainWindow` Edit menu actions: Undo (Ctrl+Z),
      Redo (Ctrl+Shift+Z). Each `JsonTab` owns its own `QUndoStack`;
      shortcuts are tab-local.
- [ ] [tree] Decide merge policy: consecutive value edits to the same
      cell should collapse into one undo step (`mergeWith`).
      *Status:* not implemented — each typed command currently pushes a
      distinct entry. Carried forward as a Phase 5 polish item; the
      typed-command shape supports a clean `mergeWith` later (see
      `_EditValueCmd` / `_RenameCmd`).
- [x] [tests] Round-trip tests:
      - `tests/test_undo_redo.py` — per-action undo/redo behaviour.
      - `tests/test_undo_redo_scenario.py` — comprehensive 16-step
        scenario covering every JsonType and every mutating action,
        with undo×N/redo×M/branch wipes.
      - `tests/test_typed_undo_commands.py` — asserts each routine
        action pushes the correct typed command class.
      - `tests/test_typed_undo_perf.py` — wall-clock + memory bounds
        proving typed commands are O(1)/O(affected subset) and never
        store the full document.

### Cross-cutting fixes (deferred)
- [ ] [BUG] `delegate.py:ValueDelegate.createEditor` for `MULTILINE` /
      `BYTES` / `ZLIB` / `GZIP` still captures the raw `QModelIndex` in
      its dialog callbacks (`_save_multiline`, `_save_binary`). Convert
      to `QPersistentModelIndex` so the callbacks survive intervening
      row insertions/removals.
      — `delegate.py:ValueDelegate.createEditor`
      *Status:* deferred to Phase 5. The dialog path still calls
      `model.setData` directly; with typed commands now in place the fix
      is to route those callbacks through `JsonTab.commit_set_data`
      instead.
- [ ] [BUG] Route the dialog callback commits through the new undo
      stack rather than directly calling `model.setData`.
      *Status:* deferred to Phase 5 (paired with the above).

## As-shipped architecture (2026-04-26)

The original "Tips & Deep Dives" section sketched a snapshot-based
`SetValueCommand` / `RemoveRowsCommand` design with `QPersistentModelIndex`.
That intermediate design was implemented during Phase 3 but **fully
replaced** by typed action/compensation commands in the Phase 3
follow-up. The current design is:

- **Per-tab `QUndoStack` on `JsonTab`** (`json_tab.py`).
- **One typed `QUndoCommand` per logical action**:
  | Command | Affected state stored |
  |---|---|
  | `_MoveRowCmd` | parent path + 2 ints |
  | `_RenameCmd` | path + 2 strings |
  | `_EditValueCmd` | path + old subtree + new value |
  | `_ChangeTypeCmd` | path + old subtree + old `explicit_type` + new type |
  | `_InsertRowsCmd` | list of `{parent_path, row, value, name}` |
  | `_RemoveRowsCmd` | list of `{parent_path, row, name, value}` (subtree subset) |
  | `_SortKeysCmd` | path + old subtree subset + recursive flag |
- **Path-based addressing**: commands store `(int, ...)` row paths and
  resolve them via `JsonTab._index_from_path()` at undo/redo time.
  Persistent `QModelIndex` is no longer used.
- **Surgical undo apply** via `JsonTab._diff_apply()` — emits only the
  necessary `beginInsertRows` / `beginRemoveRows` / `beginMoveRows` /
  `dataChanged` signals, never `beginResetModel`. Preserves view
  expansion and selection across undo/redo.
- **Public push API on `JsonTab`**: `push_move_row`, `push_rename`,
  `push_edit_value`, `push_change_type`, `push_insert_rows`,
  `push_remove_rows`, `push_sort_keys`. `commit_set_data(index, value,
  role)` dispatches by column.
- **No whole-document snapshot path remains** — `_SnapshotCommand` and
  `commit_mutation()` were deleted.
- **Action labels** are timestamped + path-qualified, e.g.
  `"[01:40:29] duplicate @ $.integer"` — implemented by
  `_make_label(text, qname)`.

Performance numbers measured on a 5000-row, ~1.35 MB array document:

- 50 move-up pushes: 9.3 ms total; per-cmd state 524 B (0.04 % of doc).
- 50 undo + 50 redo of those moves: 1.4 ms each (~0.03 ms/op).
- 200 leaf-edit undo/redo cycles on the same document: 2.7 ms total.
- `_RemoveRowsCmd` for one inner row: 1.2 KB (0.09 % of doc).

See `tests/test_typed_undo_perf.py` for the regression bounds and
`tests/test_typed_undo_commands.py` for class-identity assertions.

## Risks / notes

- A `QUndoCommand` for an `OBJECT/ARRAY → primitive` type change has to
  remember the old subtree to be reversible. `_ChangeTypeCmd` stores
  the affected subtree only — bounded, never the full document.
- Multi-selection actions act on the **full selection**, with
  reverse-row ordering for safe positional removal/insertion.
- Sort Keys captures the prior child order via the stored subtree
  subset; undo restores the original ordering exactly.
