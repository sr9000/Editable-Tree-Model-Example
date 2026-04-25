# Phase 3 — Tree Mutation Actions

## Goal

Make the tree fully **manipulable** through the UI: cut, copy, paste,
delete, duplicate, move up/down, sort keys, plus undo/redo. After this
phase, editing a JSON document feels like editing in a real outliner.

## Entry criteria

- Phase 2 complete: name/type editing works, model mutations go through
  a unified `JsonTreeModel` API.

## Exit criteria

- Context menu and keyboard shortcuts cover: Cut (Ctrl+X), Copy (Ctrl+C),
  Paste (Ctrl+V), Delete (Del), Duplicate (Ctrl+D), Move Up (Alt+↑),
  Move Down (Alt+↓), Insert Sibling Before / After, Sort Keys.
- All mutations go through a `QUndoStack`; Ctrl+Z / Ctrl+Y reverse and
  reapply them.
- Pasting clipboard JSON into a node either replaces (when types
  match) or inserts as child / sibling depending on the target.
- The dead "Insert Column" entry is gone.

## Work items

### Clipboard
- [ ] [tree] `Copy` action: serialize selection to JSON via
      `tree_view.to_json` (already exists). Multi-selection copies a JSON
      array.
      — `tree_view.py`
- [ ] [tree] `Cut` = `Copy` + `Delete`. Wire the missing
      `cut_action.triggered.connect(...)` in `tree_view.show_context_menu`.
      — `tree_view.py:show_context_menu`
- [ ] [tree] `Paste`: parse clipboard text as JSON; if target is
      OBJECT/ARRAY, insert as child; otherwise insert as sibling after.
      Reject if clipboard is not valid JSON.
- [ ] [tree] `Delete`: remove selected rows. Connect the orphan
      `delete_action`. Bind `Qt.Key_Delete`.

### Sibling / child insertion polish
- [ ] [tree] Add **Insert Sibling Before** action (the existing
      `rowInsertAction` was wired identically to "after"; split them).
      — `ui.py:setup_connections`
- [ ] [tree] Add **Insert Child** keyboard shortcut and toolbar button
      (already present in context menu).
- [ ] [tree] Add **Duplicate** (Ctrl+D): deep-copy the selected
      `JsonTreeItem` subtree and insert as next sibling.
- [ ] [tree] Add **Move Up / Move Down**: swap `child_items[i]` with
      neighbour, emitting `layoutChanged` or a row-move signal.
- [ ] [tree] Add **Sort Keys** (recursive option): only meaningful for
      `OBJECT` parents; sort `child_items` by `name`.

### Remove dead entries
- [ ] [hygiene] Drop the "Insert Column" context menu entry and its
      toolbar action; matches the model-side removal in Phase 1.
      — `tree_view.py:show_context_menu`, `mainwindow.ui`
- [ ] [hygiene] Drop `model_actions.action_insert_column` (or convert to
      a no-op + `DeprecationWarning`).
      — `model_actions.py`

### Undo / redo
- [ ] [tree] Introduce a `QUndoStack` per `JsonTab`. Wrap each mutation
      (set value, rename, change type, insert, remove, move, sort) in a
      `QUndoCommand`.
- [ ] [tree] Bind `MainWindow` Edit menu actions: Undo (Ctrl+Z),
      Redo (Ctrl+Shift+Z).
- [ ] [tree] Decide merge policy: consecutive value edits to the same
      cell should collapse into one undo step (`mergeWith`).
- [ ] [tests] Round-trip test: random sequence of mutations →
      `undo()` until empty → tree equals the original.

### Cross-cutting fixes
- [ ] [BUG] Audit dialog-based delegates (`MULTILINE`, `BYTES`, `ZLIB`,
      `GZIP`) so their commit goes through the new undo stack rather
      than directly calling `model.setData`. Stale-index risk shrinks
      because the `QPersistentModelIndex` form is preferred.
      — `delegate.py:ValueDelegate.createEditor`
- [ ] [BUG] In dialog callbacks, capture `QPersistentModelIndex(index)`
      instead of the raw `QModelIndex`.

## Risks / notes

- A `QUndoCommand` for an `OBJECT/ARRAY → primitive` type change has to
  remember the entire subtree to be reversible. Storage cost is
  acceptable because it is bounded by the user's edit history.
- Multi-selection editing: decide whether actions operate on the
  current index only or the full selection (Qt convention is usually
  full selection, with the menu disabled if the selection is
  inconsistent).
- Sort Keys is destructive without undo — make sure the undo command
  captures the original key order.
