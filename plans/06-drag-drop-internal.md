# Step 6 — Native QTreeView drag-and-drop wired to multi-move

## Why
With multi-select MIME (step 2), atomic `push_move_rows` (step 3) and
expansion preservation (step 5) all in place, this step lights up
mouse-driven drag-and-drop for moving fields across the file.

## Scope (single commit)

### Files to touch
1. `documents/tab_setup.py`
   ```python
   tab.view.setDragEnabled(True)
   tab.view.setAcceptDrops(True)
   tab.view.setDropIndicatorShown(True)
   tab.view.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
   tab.view.setDefaultDropAction(Qt.DropAction.MoveAction)
   ```
2. `tree/model.py` — implement Qt's drag-drop hooks:
   - `mimeTypes()` → `[MIME_JSON_TREE, "text/plain"]`
   - `mimeData(indexes)` → `build_tree_mime(self, source_rows)` (only
     col-0 indexes; collapse multi-column duplicates).
   - `flags(index)` → add `ItemIsDragEnabled` for any non-root row;
     add `ItemIsDropEnabled` for OBJECT/ARRAY rows AND the empty area
     (`flags(QModelIndex())`).
   - `supportedDragActions()` → `MoveAction | CopyAction`.
   - `supportedDropActions()` → `MoveAction | CopyAction`.
   - `canDropMimeData(...)` → delegate to a new
     `tree_actions/dnd.py::can_drop(model, mime, action, row, col, parent)`.
   - `dropMimeData(...)` → delegate to
     `tree_actions/dnd.py::handle_drop(view, model, mime, action, row, col, parent)`.
3. `tree_actions/dnd.py` (new, ≈ 150 LOC):
   - `can_drop(...)` — accepts only `MIME_JSON_TREE` (or text JSON);
     rejects when target is a primitive AND `row == -1`
     (i.e., dropped *onto* a leaf row, not between rows).
   - `handle_drop(...)`:
     - Decode entries via `entries_from_mime(mime)`.
     - Resolve target `(parent_index, target_row)`:
       - If `row == -1` and parent is OBJECT/ARRAY → append (target_row
         = `rowCount(parent)`).
       - If `row == -1` and parent is a primitive → drop becomes
         "sibling after primitive" (target = primitive's parent at
         `primitive.row()+1`).
     - For internal `MoveAction` with a known source view (same
       process, same model): collect the source `QModelIndex`es from
       the originating selection (cached in
       `view.selectionModel().selectedIndexes()` because Qt resolves
       move synchronously) and call
       `tab.push_move_rows(sources, parent_index, target_row)`.
     - For `CopyAction` (Ctrl-drag) or cross-tab paste: route through
       `paste.paste_entries_at(tab, parent_index, target_row, entries)`
       (rename helper in step 2's `paste.py` cleanup).
   - Return `True` only when the underlying push succeeded; otherwise
     Qt undoes its own internal move.
4. `tests/test_drag_drop_internal.py` (new).
5. `ai-memory/repo-map.md` — extend §0 quick-orientation table with
   "Drag & drop" → `tree_actions/dnd.py`, mention the four
   `setDragDrop*` calls under §10.

### Test plan (no synthetic mouse events)
1. Build a tab; serialize 2 rows via
   `mime = model.mimeData([row_a_idx, row_b_idx])`.
2. Call `model.dropMimeData(mime, MoveAction, row=2, col=0, parent=other_obj_index)`.
3. Assert tree shape changed; both rows are now under `other_obj` at
   row 2 and 3 in source order.
4. `tab.undo_stack.undo()`; assert original shape restored (single
   undo step).
5. Cross-tab copy: drop the same MIME blob with `CopyAction` into a
   second `JsonTab`; assert source tab unchanged, target tab gained
   the entries.
6. `canDropMimeData` returns `False` when target is a primitive and
   `row == -1` (ON-row drop on a leaf).

## Definition of Done
- [ ] `pytest tests/test_drag_drop_internal.py -q` passes all 6 cases.
- [ ] Existing `tests/test_smoke_model.py` still passes — new model
      hooks must not break basic data/setData/flags coverage.
- [ ] Manual smoke: in the GUI, click and drag a row to a new sibling
      slot; row moves; expansion preserved (step 5); Ctrl+Z reverses.

## Manual smoke
```
QT_QPA_PLATFORM=offscreen pytest -q tests/test_drag_drop_internal.py tests/test_smoke_model.py
python main.py data.yaml
# Drag a row inside the same parent; drag across parents; Ctrl+drag
# to copy; Ctrl+Z to undo.
```
