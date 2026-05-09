# Step 5 — Preserve expansion + selection across moves

## Why
`DiffApplier` already emits surgical signals so the view doesn't
collapse on most edits, but a row move physically detaches and
re-attaches the subtree. Without explicit state capture the destination
row appears collapsed even if the source was expanded. Users expect
"row moved" to feel like the same row sliding to a new position,
including its children's open/closed state.

## Scope (single commit)

### Files to touch
1. `documents/tab.py`
   - Wrap `push_move_rows` in `_with_view_state_preserved(...)`
     context manager:
     1. Before push: walk every source `QModelIndex` and record a list
        of "view-relative paths from each source root" that are
        expanded (`view.isExpanded(...)`). Also record the current
        selected paths in absolute form.
     2. Push the command (single undo).
     3. After redo (use `undo_stack.indexChanged` or call after
        `push_move_rows` returns): translate each recorded relative
        path against the new destination location and call
        `view.setExpanded(view_index, True)`.
     4. Re-select the moved rows by `index_from_path`; set the first
        as current.
   - Same wrapper is invoked by undo/redo via a one-shot connection
     so reversing a move also restores expansion.
2. `state/view_state.py`
   - Add helper `iter_expanded_relative_paths(view, source_index)`
     yielding tuples of relative row paths (excluding source itself).
     Counterpart `apply_expanded_relative_paths(view, source_index, paths)`.
3. `tests/test_move_preserves_expansion.py` (new).
4. `ai-memory/repo-map.md` — extend §10 (tab) and §13 (view state).

### Test plan
1. Build a fixture with `root.a.b.c` and `root.a.b.d.e` expanded;
   `root.x` collapsed.
2. Multi-row move `root.a.b` and `root.x` to a new parent.
3. Assert `view.isExpanded(<new path of a.b>)` and
   `view.isExpanded(<new path of a.b.d>)`, but
   `view.isExpanded(<new path of x>)` is `False`.
4. Assert the selection is exactly the two moved rows; the first is
   `currentIndex()`.
5. Issue `undo`; assert original expansion + selection paths are
   restored.

## Definition of Done
- [ ] `pytest tests/test_move_preserves_expansion.py -q` passes the 5
      assertions above.
- [ ] `pytest tests/test_keyboard_multimove.py -q` (step 4) keeps
      passing — the wrapper must not break the single-row path.
- [ ] Manual: in the GUI, drag-or-keyboard moving a row whose subtree
      was expanded keeps it expanded at the destination.

## Manual smoke
```
QT_QPA_PLATFORM=offscreen pytest -q tests/test_move_preserves_expansion.py tests/test_keyboard_multimove.py
python main.py data.yaml
# Expand a deep object → Alt+Down it across siblings → it stays expanded.
# Ctrl+Z restores both the layout and the original expansion.
```
