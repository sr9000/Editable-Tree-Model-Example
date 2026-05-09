# Step 4 — Keyboard multi-move + parent-boundary bubble-out

## Why
`Alt+Up` / `Alt+Down` currently move one row, only inside its parent.
Users expect a continuous "row moves up/down" feel: when the row hits
the top of its parent, the next press promotes it to be a sibling
**before** its parent (i.e., one level up at the grandparent). Same
for the bottom edge. Multi-selection should move as a contiguous block.

## Scope (single commit)

### Files to touch
1. `tree_actions/structure.py`
   - Replace `move_selection_up`/`move_selection_down` with
     versions that:
     - Read `top_level_source_rows(view)` (step 1).
     - Reject if the selection straddles parents AND no common
       grandparent path could host them — fall back to per-row move
       and report partial success.
     - Same-parent block: compute new `target_row`:
       - up: `min_row - 1` (no-op if already 0)
       - down: `max_row + 2` (no-op if already last; +2 because target
         is computed pre-pop)
     - Boundary bubble-out:
       - up at row 0: target = (grandparent, parent_row); fails if
         parent is the model root.
       - down at last row: target = (grandparent, parent_row + 1).
     - Always dispatches via `JsonTab.push_move_rows` (single undo).
2. `documents/tab_setup.py`
   - Keep the `Alt+Up` / `Alt+Down` shortcut bindings — they already
     call `move_selection_up`/`move_selection_down`. No new shortcut.
3. `model_actions.py`
   - Update headless fallbacks `action_move_up` / `action_move_down`
     for the bubble-out path so non-tab tests stay green.
4. `tests/test_keyboard_multimove.py` (new).
5. `ai-memory/repo-map.md` — note the new bubble-out semantics in §4.

### Edge-case matrix the tests must cover
| Setup                                              | Action     | Expected                                   |
| -------------------------------------------------- | ---------- | ------------------------------------------ |
| `[a, b, c]` with `b` selected                      | Alt+Up     | `[b, a, c]`                                |
| `[a, b, c]` with `b, c` selected                   | Alt+Up     | `[b, c, a]` (block)                        |
| `obj{x, y, z}` with `x` selected                   | Alt+Up     | bubble out: `x` becomes sibling before obj |
| Root-level row                                     | Alt+Up     | no-op, returns `False`                     |
| Discontinuous selection across two parents         | Alt+Down   | each row moves independently within parent |
| Single multi-row block at parent's bottom          | Alt+Down   | bubble out after parent                    |

## Definition of Done
- [ ] `pytest tests/test_keyboard_multimove.py -q` covers every row of
      the matrix above, asserting both the post-move tree shape AND
      that `tab.undo_stack.count()` increased by exactly one.
- [ ] Each test then issues a single `tab.undo_stack.undo()` and
      asserts the tree is byte-identical to the pre-move snapshot
      (`model.root_item.to_json()`).
- [ ] Existing `tests/test_tree_actions_structure.py::test_move_*`
      stays green (no behavioural regression for single-row moves).

## Manual smoke
```
QT_QPA_PLATFORM=offscreen pytest -q tests/test_keyboard_multimove.py tests/test_tree_actions_structure.py
python main.py data.yaml
# Select two adjacent leaves under an object → Alt+Up repeatedly →
# rows climb to position 0, next press lifts them out of the parent.
```
