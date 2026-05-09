# Step 3 — Atomic multi-row move on the undo stack

## Why
Today `JsonTab.push_move_row(parent, src, dst, label)` moves exactly
one row inside one parent. Multi-row keyboard moves (step 4) and
drag-and-drop (step 6) need an N-row move that:
- is a single undo step,
- handles both same-parent block-moves (rows reorder together) and
  cross-parent moves (selection lifts and lands at a new
  `(parent_path, row)`),
- correctly translates source/destination indexes as items are popped
  from sources and inserted at the target.

## Scope (single commit)

### Files to touch
1. `undo/commands.py`
   - Add `_MoveRowsCmd(model, sources: list[tuple[parent_path, row]], target_parent_path, target_row, label)`.
   - `redo` removes rows in descending source order (so earlier indexes
     stay valid), captures detached items, then inserts them at the
     target position. If sources sit before the target inside the same
     parent, `target_row` is decremented by the number of removed
     siblings ahead of it.
   - `undo` rebuilds the inverse mapping recorded during `redo`
     (per-source `(parent_path, row)`), reinserts items from last to
     first to restore the original layout.
   - Reuses `DiffApplier` semantics — emit surgical `beginMove*` /
     `beginInsert*` / `beginRemove*` so the view's expansion + current
     index survive (step 5 builds on top of this).
2. `documents/tab.py`
   - Add `push_move_rows(sources: list[QModelIndex], target_parent: QModelIndex, target_row: int, *, label="move rows") -> bool`.
   - Translate every input `QModelIndex` to a path via `_index_path`
     before pushing — model mutations inside the redo invalidate the
     indices.
   - Reject moves where any source's path is an ancestor of
     `target_parent` (would create a cycle); return `False` and emit a
     status message.
3. `tests/test_undo_multimove.py` (new).
4. `ai-memory/repo-map.md` — list `_MoveRowsCmd` in §15 and
   `push_move_rows` in §10.

### Order-translation invariants (covered by tests)
- Same-parent forward block move `[2,3] → row 5`: after popping rows 2
  and 3 (descending), the in-flight `target_row` becomes
  `5 - 2 = 3` (because both sources sit before the target).
- Same-parent backward block move `[5,7] → row 2`: target stays 2.
- Cross-parent: target row stays as given since sources don't sit in
  the target parent.

## Definition of Done
- [ ] `pytest tests/test_undo_multimove.py -q` passes:
    1. Same-parent forward block move keeps relative order, single
       undo restores original layout.
    2. Same-parent backward block move ditto.
    3. Cross-parent multi-row move (e.g. lift `a.x` and `b.y` into
       `c`) places them at the target row in source order; undo
       restores both originating parents.
    4. Cycle guard: moving a parent into its own descendant returns
       `False`, model unchanged, no command pushed (`undo_stack.count()`
       unchanged).
    5. `mergeWith` for two distinct `_MoveRowsCmd` returns `False`
       (each move is its own undo step).
- [ ] All existing `tests/test_typed_undo_commands.py` and
      `tests/test_undo_redo*.py` still pass.
- [ ] `JsonTab.push_move_row` keeps working (delegates to
      `push_move_rows` internally if convenient — verify with existing
      `tests/test_tree_actions_structure.py::test_move_*`).

## Manual smoke
```
QT_QPA_PLATFORM=offscreen pytest -q tests/test_undo_multimove.py tests/test_typed_undo_commands.py tests/test_undo_redo.py
```
