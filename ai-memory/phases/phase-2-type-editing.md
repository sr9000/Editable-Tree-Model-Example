# Phase 2 — Type & Name Editing

## Goal

Make the `Name` and `Type` columns first-class editable cells. After this
phase a user can rename any object key and change any node's `JsonType`
through the UI, with sensible value coercion.

## Entry criteria

- Phase 1 complete: model insertions are correct, `set_data` already
  recomputes `json_type` from the value.

## Exit criteria

- Editing column 0 (Name) renames the underlying `JsonTreeItem.name`.
  Duplicate names under the same `OBJECT` parent are rejected.
- Editing column 1 (Type) via `JsonTypeDelegate` mutates `json_type` and
  coerces `value` to a sane default for the new type.
- The Type combo preselects the **current** type when opened.
- Auto-classification can be **overridden**: a node explicitly typed as
  `STRING` stays `STRING` even if the value would parse as datetime /
  base64 / multiline.

## Work items

### Name column
- [ ] [type] Extend `JsonTreeItem.set_data(0, value)` to update `self.name`.
      Reject empty names and duplicates under an `OBJECT` parent (return
      `False`).
      — `tree_item.py:JsonTreeItem.set_data`
- [ ] [type] In `JsonTreeModel.flags()`, mark column 0 as editable only
      when the parent is an `OBJECT`. ARRAY children expose their index
      as read-only.
      — `tree_model.py:JsonTreeModel.flags`
- [ ] [type] In `JsonTreeItem.data(0)`, return the row index for ARRAY
      children instead of `<no name>`.
      — `tree_item.py:JsonTreeItem.data`
- [ ] [tests] Unit tests: rename success, rename to duplicate fails,
      ARRAY child rename refused.

### Type column
- [ ] [BUG] Implement `JsonTypeDelegate.setModelData` to push the
      selected `JsonType` through `model.setData(index, type, EditRole)`.
      — `delegate.py:JsonTypeDelegate.setModelData`
- [ ] [BUG] Move combo population from `setEditorData` into `createEditor`,
      and have `setEditorData` set the current text from
      `index.internalPointer().json_type`.
      — `delegate.py:JsonTypeDelegate`
- [ ] [type] Extend `JsonTreeItem.set_data(1, json_type)` to mutate
      `self.json_type` and coerce `self.value`. Define a coercion table:
      | from\to | NULL | BOOLEAN | INTEGER | FLOAT/PERCENT | STRING/MULTILINE | DATE/TIME/DT/DTZ | BYTES/ZLIB/GZIP | ARRAY | OBJECT |
      |---------|------|---------|---------|---------------|------------------|------------------|-----------------|-------|--------|
      Cells are filled with reasonable defaults (e.g. INTEGER → 0, ARRAY
      → []). Where the existing value is convertible, prefer it
      (`"42"` → `42`).
      — `tree_item.py:JsonTreeItem.set_data`
- [ ] [type] When switching to/from `OBJECT` or `ARRAY`, clear
      `child_items` and emit the proper
      `beginRemoveRows`/`endRemoveRows` (or `beginInsertRows`) sequence
      via the model. Likely needs a model-level helper
      `JsonTreeModel.change_type(index, new_type)` that owns the
      bookkeeping.

### Type pinning (override auto-classification)
- [ ] [type] Persist an `explicit_type: bool` flag on `JsonTreeItem`. When
      `True`, `set_data(2, value)` does **not** re-run `parse_json_type`
      — it only validates against the existing `json_type`.
      — `tree_item.py:JsonTreeItem`
- [ ] [type] Setting `json_type` via column 1 sets `explicit_type=True`.
      Rebuilding from raw input (load) clears it.
- [ ] [tests] Unit tests for pinning: assign STRING to a value that looks
      like base64, confirm it stays STRING after `set_data`.

### Editor wiring
- [ ] [type] After a successful type change, the view must reopen the
      `Value` editor with the right delegate. The model can emit
      `dataChanged` for the (col-2) sibling index to nudge the view.
- [ ] [ux] When a coercion drops information (e.g. OBJECT → STRING),
      show a confirmation dialog or status-bar warning.

## Risks / notes

- The coercion table is the largest design decision in this phase.
  Document it in `enums.py` next to `JsonType`.
- Be careful with `PERCENT`: storage stays in the `[0, 1]` `mpq`
  fraction; the editor multiplies by 100. Type changes must respect
  this.
- Renaming under an `OBJECT` must preserve sibling order
  (`child_items` is a list). Re-keying must not move the row.
