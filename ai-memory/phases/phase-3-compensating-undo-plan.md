# Phase 3 Follow-up: Compensating Undo/Redo Plan

_Status: ✅ **complete** (2026-04-26)._

Date: 2026-04-26

## Outcome (2026-04-26)

All goals of this plan are met. The full-document snapshot history was
not just downgraded to a fallback — `_SnapshotCommand` and
`commit_mutation()` were **deleted entirely** from `json_tab.py`. The
editor is now structurally incapable of producing a whole-document
snapshot undo entry.

### What was shipped

- Typed command classes on `json_tab.py`: `_MoveRowCmd`, `_RenameCmd`,
  `_EditValueCmd`, `_ChangeTypeCmd`, `_InsertRowsCmd`, `_RemoveRowsCmd`,
  `_SortKeysCmd`.
- Public push API on `JsonTab`: `push_move_row`, `push_rename`,
  `push_edit_value`, `push_change_type`, `push_insert_rows`,
  `push_remove_rows`, `push_sort_keys`.
- `commit_set_data(index, value, role)` dispatches by column to the
  three column-level helpers.
- `tree_view.py` mutating actions now call typed helpers when the
  view's parent is a `JsonTab`, falling back to direct model mutation
  otherwise.
- Surgical `_diff_apply()` family (`_diff_object`, `_diff_array`,
  `_convert_container`, `_convert_to_leaf`) drives undo/redo replay
  with minimal Qt model signals — no `beginResetModel`.
- Removed: `_SnapshotCommand`, `commit_mutation()`, `_capture_state()`,
  `_restore_state()`, `_restore_snapshot()`, `_diff_apply_root()`,
  `_tree_equals_data()`, `_ordered_repr()`. `json_tab.py` shrank from
  882 → 765 lines.

### Performance (5000-row, ~1.35 MB array document)

| operation | wall time | per-op | command state | vs full doc |
|---|---:|---:|---:|---:|
| 50 moves (push) | 9.3 ms | 0.19 ms | 524 B | 0.04 % |
| 50 undo (move) | 1.4 ms | 0.03 ms | — | — |
| 50 redo (move) | 1.4 ms | 0.03 ms | — | — |
| 200 leaf-edit undo/redo cycles | 2.7 ms | 0.01 ms | 645 B | 0.05 % |
| 1 inner-row delete | — | — | 1 224 B | 0.09 % |

### Tests covering the contract

- `tests/test_typed_undo_commands.py` — every routine action pushes the
  correct typed command class.
- `tests/test_typed_undo_perf.py` — wall-clock + transitive-state-size
  bounds, plus `_before` / `_after` attribute-presence checks.
- `tests/test_undo_redo.py` — per-action undo/redo behaviour and label
  format (`[HH:MM:SS] {action} @ {qname}`).
- `tests/test_undo_redo_scenario.py` — 16-step end-to-end scenario
  covering every JsonType + every mutating action with branched
  undo/redo.
- `tests/test_perf_smoke.py` — generic perf bounds (still green at
  3000-row fan-out).

Full suite: **343 / 343** passing in ~1 s.

## Goal (original)

Move undo/redo away from whole-document snapshot history and toward typed action/compensation commands.

Full-document snapshots should become a fallback only. Normal history entries should store the smallest practical affected subset:

- O(1) metadata for cheap actions like move/rename.
- Affected row/subtree JSON only for insert/delete/paste/duplicate/type-change.
- Sorted subtree JSON only for massive sort operations.
- Never dump the whole JSON document for routine history commands.

## Current State

Implemented before this plan:

- `JsonTab.commit_mutation()` snapshot path was optimized:
  - skips `QUndoStack.push()` implicit redo when already in the after-state;
  - uses `_tree_equals_data()` for no-op detection instead of building two ordered snapshots;
  - defers the after snapshot until a command is known to be meaningful.
- `JsonTreeItem.row()` was optimized with lazy cached row indexes.
- `_restore_state()` was changed from a full `beginResetModel()` rebuild to a surgical diff path where possible.
- History labels include timestamp and qualified JSON path.

Partially started during this refactor:

- `json_tab.py` now has typed command classes and `push_*` helper methods added/started:
  - `_MoveRowCmd`
  - `_RenameCmd`
  - `_EditValueCmd`
  - `_ChangeTypeCmd`
  - `_InsertRowsCmd`
  - `_RemoveRowsCmd`
  - `_SortKeysCmd`
  - `JsonTab.push_move_row()`
  - `JsonTab.push_rename()`
  - `JsonTab.push_edit_value()`
  - `JsonTab.push_change_type()`
  - `JsonTab.push_insert_rows()`
  - `JsonTab.push_remove_rows()`
  - `JsonTab.push_sort_keys()`
- `JsonTab.commit_set_data()` was switched to dispatch through typed helpers.

Still pending:

- Refactor `tree_view.py` tree actions to use the typed helpers instead of `commit_mutation()`.
- Run and fix full test suite after the refactor.
- Add targeted tests proving the undo stack no longer stores whole-document snapshots for routine commands.

## Desired Architecture

### Keep as fallback

`_SnapshotCommand` and `commit_mutation()` may remain for emergency compatibility or unconverted future operations.

They should not be used by normal tree actions once this refactor is complete.

### Normal typed commands

| Command | Stored data | Undo/redo cost |
|---|---:|---:|
| `_MoveRowCmd` | parent path, source row, destination row | O(1) plus Qt move signal |
| `_RenameCmd` | item path, old name, new name | O(1) |
| `_EditValueCmd` | item path, old affected subtree, new affected value/subtree | O(size of affected subtree) |
| `_ChangeTypeCmd` | item path, old affected subtree, old explicit flag, new type | O(size of affected subtree) |
| `_InsertRowsCmd` | inserted rows only: parent path, row, name, value subtree | O(inserted subset) |
| `_RemoveRowsCmd` | removed rows only: parent path, row, name, value subtree | O(removed subset) |
| `_SortKeysCmd` | sorted object subtree only | O(sorted subset) |

### Massive operations policy

Operations allowed to store JSON subset dumps:

- paste of large JSON subset;
- duplicate of complex nested object/array;
- delete/cut of complex nested object/array;
- sort keys / recursive sort of complex object subtree;
- type change that drops children.

But they must store only the affected subset, never `root_item.to_json()` for the full document.

## Remaining Implementation Steps

### 1. Verify `json_tab.py` typed helpers

Check these items after the current partial implementation:

- `commit_set_data()` dispatches correctly:
  - column 0 -> `push_rename()`;
  - column 1 -> `push_change_type()`;
  - column 2 -> `push_edit_value()`.
- `push_edit_value()` correctly handles:
  - explicit type coercion;
  - no-op edits;
  - leaf -> object/array conversion;
  - object/array -> leaf conversion;
  - complex subtree edits.
- `push_change_type()` correctly handles:
  - no-op same type;
  - lossy object/array -> leaf changes;
  - undo restoring dropped children.
- `_diff_apply()` always succeeds in-place for root/subtree type changes.

### 2. Refactor `tree_view.py`

Replace `_commit_on_tab()` usage for normal actions with typed helper calls.

Actions to convert:

- `insert_sibling_before()` -> `JsonTab.push_insert_rows()`
- `insert_sibling_after()` -> `JsonTab.push_insert_rows()`
- `insert_child_current()` -> `JsonTab.push_insert_rows()`
- `delete_selection()` -> `JsonTab.push_remove_rows()`
- `cut_selection()` -> copy + typed delete
- `paste_from_clipboard()` -> `JsonTab.push_insert_rows()`
- `duplicate_selection()` -> `JsonTab.push_insert_rows()` with copied subtree values
- `move_selection_up()` -> `JsonTab.push_move_row()`
- `move_selection_down()` -> `JsonTab.push_move_row()`
- `sort_selection_keys()` -> `JsonTab.push_sort_keys()`

Keep direct model fallback behavior for non-`JsonTab` usages where practical.

### 3. Remove old `model_actions` dependency from `tree_view.py`

After conversion, `tree_view.py` should no longer need:

- `action_duplicate`
- `action_insert_child`
- `action_insert_row_after`
- `action_insert_row_before`
- `action_move_down`
- `action_move_up`
- `action_sort_keys`

`model_actions.py` can remain for now if tests or old call sites still use it.

### 4. Add tests

Add/extend tests to prove compensation behavior.

Suggested tests:

1. `test_commit_set_data_uses_typed_commands`
   - edit value;
   - rename;
   - change type;
   - verify command class names are not `_SnapshotCommand`.

2. `test_tree_actions_use_typed_commands`
   - insert sibling;
   - insert child;
   - move up/down;
   - duplicate;
   - delete;
   - paste;
   - sort;
   - verify newest command is not `_SnapshotCommand`.

3. `test_large_leaf_edit_does_not_store_full_document`
   - create huge root array/object;
   - edit one leaf;
   - inspect command object does not contain full before/after root snapshots.

4. `test_delete_stores_removed_subset_only`
   - delete one nested subtree;
   - verify command stores that subtree, not full root.

5. `test_sort_stores_sorted_subtree_only`
   - sort a nested object;
   - verify command stores only that object subtree.

6. Keep existing comprehensive scenario test:
   - undo x3 -> redo x2 -> action -> redo no effect;
   - undo x2 -> action -> redo no effect;
   - undo past init no-op;
   - redo past final no-op.

### 5. Performance checks

Run existing perf smoke tests:

```bash
cd /home/sr9000/PycharmProjects/Editable-Tree-Model-Example
python -m pytest tests/test_perf_smoke.py -q
```

Then run full suite:

```bash
cd /home/sr9000/PycharmProjects/Editable-Tree-Model-Example
python -m pytest -q
```

Optional manual microbenchmark after refactor:

- create a 3k-row array;
- perform 20 move-up operations;
- undo all;
- redo all;
- expected move undo/redo should be close to pure `move_row()` cost.

## Important Edge Cases

### Object key uniqueness

When inserting/pasting/duplicating under an object parent:

- preserve clipboard/object entry names when unique;
- auto-generate or suffix collisions (`foo`, `foo_2`, etc.);
- undo must restore exact original names.

### Array row names

Array child names are virtual row numbers, not stored names.

Typed insert/remove commands should store `name=None` for array children.

### Row ordering for multi-row operations

For deletion:

- record rows sorted deepest-first and reverse row order;
- redo removes in recorded order;
- undo inserts in reverse recorded order.

For insertion:

- record rows in the order they should be inserted;
- undo removes in reverse order.

### QModelIndex invalidation

Typed commands should store paths and row numbers, not persistent `QModelIndex` objects.

At undo/redo time, resolve paths with `JsonTab._index_from_path()`.

### Type changes

Type changes can be lossy.

Undo must restore the old subtree subset and the old `explicit_type` flag.

Redo should call `model.setData(type_idx, new_type, EditRole)` or equivalent type conversion.

### View state

Typed commands should avoid `beginResetModel()`.

Selection, current index, and expansion should generally be preserved by Qt signals.

For commands that logically move/select newly inserted rows, explicitly set current index after redo.

## Success Criteria

- Full test suite passes.
- Routine edit/move/rename actions do not create `_SnapshotCommand` instances.
- Undo stack entries for normal actions store only affected data subsets.
- Massive operations store only affected subset, not full document.
- Undo/redo history labels remain timestamped and path-qualified.
- Undo/redo does not collapse unrelated expanded objects/arrays.
- Existing copy/cut/paste behavior remains compatible with current clipboard format.

## Suggested Next Work Order

1. Finish `tree_view.py` conversion to typed helpers.
2. Run `tests/test_undo_redo.py` and `tests/test_undo_redo_scenario.py`.
3. Fix behavior regressions.
4. Add command-type/no-full-snapshot tests.
5. Run `tests/test_perf_smoke.py`.
6. Run full suite.
7. If stable, consider deleting or deprecating snapshot `commit_mutation()` for tree actions.
