# Step 8 — Shortcuts, context menu & docs

## Why
Final polish: register the explicit "move out of parent" shortcuts the
user asked for, refresh the context menu copy for multi-selection, and
update repo memory so the feature is discoverable.

## Scope (single commit)

### Files to touch
1. `documents/tab_setup.py::init_shortcuts`
   - `Alt+Up` / `Alt+Down` — already wired (step 4).
   - `Ctrl+Alt+Up` / `Ctrl+Alt+Down` — new: explicit
     "move selection out of parent (up / down)" regardless of position.
     Bind to `tree_actions.structure.move_selection_out_up` /
     `move_selection_out_down` (thin wrappers that call
     `push_move_rows` with the bubble-out target). When the parent
     is the root, no-op + status message.
2. `tree_actions/structure.py`
   - Implement `move_selection_out_up` / `move_selection_out_down`.
3. `tree_actions/context_menu.py`
   - Pluralise "Move Up" / "Move Down" labels to
     "Move N Rows Up" / "Move N Rows Down" when the selection has
     more than one top-level row.
   - Add "Move Out of Parent (Up)" / "(Down)" entries; disabled when
     parent is root.
4. `mainwindow.ui`
   - Optional: add `actionMoveOutUp` / `actionMoveOutDown` so they
     also appear in the **Actions** menu. (UI file edits stay tiny —
     two new `QAction` blocks plus menu entries.)
5. `tests/test_shortcuts_and_menu.py` (new).
6. `ai-memory/repo-map.md`
   - Update §4 shortcut table: add `Alt+Up/Down` (now multi-select),
     `Ctrl+Alt+Up/Down` (move out of parent), drag-and-drop note.
   - Update §5 context-menu list with the new entries.
   - Update §0 quick-orientation row "Drag & drop / multi-move" →
     `tree_actions/dnd.py`, `tree_actions/structure.py`,
     `documents/tab.py::push_move_rows`.
   - Bump scan date.
7. `ai-memory/todo-n-fixme.md` — strike out any "drag-drop" or
   "multi-row move" wishlist entries (sweep with `grep`).

### Test plan
1. `Ctrl+Alt+Up` on a row inside an object lifts it before the
   parent; `Ctrl+Alt+Down` lifts after the parent; both with single
   undo step.
2. Context-menu builder: with 1 row selected → label is "Move Up";
   with 3 rows selected → label is "Move 3 Rows Up".
3. Disabled-action coverage: at root, the "Move Out of Parent" entry
   is `enabled() == False`.
4. Smoke: a `JsonTab` constructed in tests carries both the new
   shortcuts and the existing Alt+Up/Down without ambiguous-shortcut
   warnings.

## Definition of Done
- [ ] `pytest tests/test_shortcuts_and_menu.py -q` passes the four
      cases above.
- [ ] `pytest -q` overall: only the 3 known offscreen-only failures
      remain (no new reds).
- [ ] `grep -nR "drag" ai-memory/` shows the feature documented as
      shipped.
- [ ] `ai-memory/repo-map.md` scan date is bumped.

## Manual smoke
```
QT_QPA_PLATFORM=offscreen pytest -q tests/test_shortcuts_and_menu.py
QT_QPA_PLATFORM=offscreen pytest -q
python main.py data.yaml
# Verify: Alt+Up/Down on multi-selection, Ctrl+Alt+Up/Down to bubble
# out, right-click menu shows pluralised labels.
```
