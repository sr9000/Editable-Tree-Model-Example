# Step 7 — Drop policies, indicators & visual cues

## Why
Step 6 wires the pipeline; this step makes the pipeline safe and
discoverable: forbid invalid drops, fall back gracefully on primitive
targets, surface the action (move vs copy) to the user.

## Scope (single commit)

### Files to touch
1. `tree_actions/dnd.py`
   - `can_drop(...)` extended:
     - Reject if any source path is an ancestor of `parent_index`
       (self-into-descendant cycle). Source paths are decoded from the
       MIME blob's `entries` list — but entries don't carry source
       paths. Fix: when calling `model.mimeData`, additionally encode
       a `"source_paths": [[i,j,…],…]` array INSIDE the
       `application/x-json-tree` JSON envelope (back-compat: optional
       key, decoders unaware of it ignore it).
     - Reject `MoveAction` when source paths are unknown (cross-tab
       drop) — Qt should still allow `CopyAction` in that case.
   - `_resolve_drop_target(model, row, parent_index)`:
     - `row >= 0` → `(parent_index, row)`
     - `row == -1` and parent is OBJECT/ARRAY → append
     - `row == -1` and parent is primitive → bubble up:
       `(parent_index.parent(), parent_index.row() + 1)`
     - `row == -1` and `parent_index` invalid (drop on empty viewport)
       → root-level append
2. `tree/model.py`
   - `mimeData` writes the `source_paths` envelope key.
3. `documents/tab_setup.py`
   - `tab.view.setDropIndicatorShown(True)` (already in step 6) —
     verify behaviour matches `QAbstractItemView.AboveItem` /
     `BelowItem` / `OnItem` indicators.
   - Wire `dragEnterEvent` / `dragMoveEvent` so the cursor reflects
     the resolved action: when Ctrl is held → CopyAction, otherwise
     MoveAction.
4. `tab_status.py`
   - After a successful drop, push a transient status message:
     `"Moved 3 rows under $.foo"` or `"Copied 1 row under $.bar"`.
5. `tests/test_drop_policies.py` (new).
6. `ai-memory/repo-map.md` — extend §0/§11 with the drop-policy notes.

## Definition of Done
- [ ] `pytest tests/test_drop_policies.py -q` covers:
    1. Self-into-descendant move is rejected (`canDropMimeData` →
       `False`) and the tree is unchanged.
    2. Drop ON a primitive (`row == -1`, parent is INTEGER) becomes a
       drop AS sibling-after.
    3. Drop on the empty viewport (parent invalid, `row == -1`) is
       accepted only when the model has a non-show-root setup, else
       rejected with a status message.
    4. Ctrl-drag: source unchanged after a successful drop (CopyAction);
       no-Ctrl drag: source rows are removed (MoveAction).
    5. Status callback receives a `"Moved N rows"` / `"Copied N rows"`
       message.
- [ ] Steps 1 – 6 tests still green.

## Manual smoke
```
QT_QPA_PLATFORM=offscreen pytest -q tests/test_drop_policies.py
python main.py data.yaml
# Try dragging a parent into its own child → cursor shows forbidden.
# Drop ON a leaf → row lands as sibling-after.
# Hold Ctrl while dragging → cursor shows "+" copy hint, source stays.
```
