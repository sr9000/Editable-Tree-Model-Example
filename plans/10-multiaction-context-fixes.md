# Step 10 — Multi-action paste semantics + context-menu selection preservation

_Status: **plan / next implementation step**. This is a corrective follow-up
to Step 9. Step 9 made the move core much healthier, but the paste/action
wiring still mixes old single-current-index behaviour with the new
multi-selection semantics.

## 0) User-visible bugs to fix

1. **Multi-paste does not actually operate on all selected indices.**
   It appears to paste at the last/current index only.
2. **Multi-insert currently replaces values.**
   It should behave as a paste-after operation, pairing clipboard top-level
   entries with selected targets, top-level only, no deep scan.
3. **Multi-replace needs a separate action.**
   The current `paste_insert_zip()` implementation is really a multi-replace.
4. **Context menu breaks multi-selection workflows.**
   Right-clicking one selected value should preserve the whole selection;
   right-clicking outside the selection should keep the current single-row
   behaviour.

---

## 1) Root-cause analysis

### 1.1 Ctrl+V still calls the old single-target paste path

Current wiring in `documents/tab.py`:

```python
elif paste:
    changed = paste_from_clipboard(self.view)
```

`paste_from_clipboard()` in `tree_actions/paste.py` only reads:

```python
current = _to_source_index(tree_view.currentIndex())
target = _resolve_paste_target(model, current, "auto")
```

So no matter how many rows are selected, `Ctrl+V` pastes relative to
`currentIndex()` only. This explains the observed "last index" behaviour:
`currentIndex()` is usually the last clicked/selected row, so paste lands
there and nowhere else.

A Step-9 helper already exists:

```python
paste_clones_at_targets(tree_view)
```

but it is **not wired** to the normal paste action. `documents/tab_setup.py`
even imports it, but does not use it. `tree_actions/context_menu.py` also
routes menu Paste to `paste_from_clipboard()`.

**Fix direction:** normal paste (`Ctrl+V`, context `Paste (auto)`) should call
a dispatcher:

```python
paste_auto(tree_view):
    if len(selected_source_rows(tree_view)) > 1:
        return paste_clones_at_targets(tree_view)
    return paste_from_clipboard(tree_view)
```

or simply make `paste_from_clipboard()` multi-aware internally. Prefer a
new dispatcher name (`paste_auto`) to avoid hiding legacy semantics.

### 1.2 Existing `paste_clones_at_targets()` has two design hazards

Even after wiring it, the helper should be tightened before relying on it:

1. It calls `_paste_entries_at()` once per target. `_paste_entries_at()`
   rereads the clipboard each time and creates its own `_InsertRowsCmd`.
   That works, but makes tests and future changes fragile.
2. It sorts target descriptors descending by `(parent_path, insert_pos)`.
   Descending is correct for leaf sibling-after inserts in the same parent,
   but mixed container/leaf targets are harder to reason about because
   child-appends and sibling-inserts use different coordinate spaces.

**Fix direction:** extract a pure planner:

```python
plan_paste_clones(model, tab, targets, entries) -> list[InsertRec]
```

The planner should:

- snapshot selected targets before mutations,
- decide each target's placement (`child append` for containers,
  `sibling after` for leaves),
- group inserts by parent path,
- for each parent, sort target insert anchors descending and generate
  stable `row` values,
- pass one flat insert list to `tab.push_insert_rows(...)` when possible.

This removes clipboard rereads and turns multi-paste into one typed command
instead of a macro of nested insert commands.

### 1.3 `paste_insert_zip()` is misnamed and implements multi-replace

Current implementation:

```python
for target, entry in zip(targets, entries):
    value_index = model.index(target.row(), 2, target.parent())
    tab.push_edit_value(value_index, entry["value"], label="paste at each")
```

That replaces the target's subtree. It is useful, but it is **not** the
requested `multi-insert`.

Requested semantics:

> "multi-insert — uses separate shortcut and pastes each value/key at its own
> selection, top level only, no deep scan"

With the latest clarification:

> "multi-insert just replace values, while should work as paste after; assign
> different action to multireplace"

So the action split must be:

| Action | Shortcut | Behaviour |
| --- | --- | --- |
| **Paste / multi-paste** | `Ctrl+V` | Clone *all* clipboard entries at *every* selected target (`child append` for containers, `sibling after` for leaves). |
| **Multi-insert** | `Ctrl+Shift+V` | Zip top-level clipboard entries with top-level selected rows and insert each entry **after** its paired target. Does not scan into selected descendants. |
| **Multi-replace** | proposed `Ctrl+Alt+V` or menu-only initially | Zip top-level clipboard entries with top-level selected rows and replace each target's value. This is the current `paste_insert_zip()` behaviour under a corrected name. |
| **Single replace** | context menu `Paste — Replace Value` | Existing single-target replace, requires one clipboard entry. |

**Fix direction:** rename/split functions in `tree_actions/paste.py`:

- `paste_clones_at_targets(tree_view)` — multi-paste clones everywhere.
- `paste_insert_after_zip(tree_view)` — new true multi-insert.
- `paste_replace_zip(tree_view)` — extracted from current `paste_insert_zip()`.
- keep `paste_insert_zip` as a short-lived alias only if needed by tests;
  better to update callers/tests immediately.

### 1.4 Context menu selection is not selection-preserving

Current code in `tree_actions/context_menu.py`:

```python
index = tree_view.indexAt(position)
...
if index.isValid():
    tree_view.setCurrentIndex(index)
```

That unconditionally promotes the clicked index to current. Depending on
Qt selection mode/platform event handling, this can collapse the
multi-selection before the menu action runs. Even when it does not clear the
selection itself, it changes the action target to the clicked/current row,
which is fatal while the paste code still uses `currentIndex()`.

The desired behaviour is standard multi-select context-menu UX:

- If right-click is on a row/cell that is already part of the current
  selection, **preserve selection** and only update current index with
  `NoUpdate`.
- If right-click is outside the selection, **reset to clicked item** and keep
  the existing single-target context-menu behaviour.

This matters especially for value-column cells: clicking a selected value
cell should not drop the rest of the selected rows.

**Fix direction:** add a helper in `tree_actions/context_menu.py`:

```python
def _prepare_context_selection(tree_view, index):
    if not index.isValid():
        return
    sm = tree_view.selectionModel()
    if _clicked_row_is_selected(tree_view, index):
        sm.setCurrentIndex(index, QItemSelectionModel.NoUpdate)
    else:
        sm.select(index, ClearAndSelect | Rows or Current?)
        sm.setCurrentIndex(index, NoUpdate)
```

The selected check should compare **source row identity**, not raw proxy
indexes, so it works through the filter proxy and across columns:

```python
clicked_row = _row0(source_model, _to_source_index(index))
selected_rows = selected_source_rows(tree_view)
return any(_index_path(_row0(source_model, r)) == _index_path(clicked_row)
           for r in selected_rows)
```

Then `show_context_menu()` should call `_prepare_context_selection(...)`
instead of `tree_view.setCurrentIndex(index)`.

### 1.5 Context-menu enable flags are still current-row based

`show_context_menu()` computes:

```python
can_move_up = row0.row() > 0
can_move_down = row0.row() < source_model.rowCount(row0.parent()) - 1
can_sort_keys = item.json_type is JsonType.OBJECT
```

These are based on the clicked/current row only. For a multi-selection,
menus should not imply that an action only applies to the clicked row.

**Fix direction:** after `_prepare_context_selection`, compute capabilities
from the selection:

- `has_selection = bool(selected_source_rows(tree_view))`
- `is_root = all/any root?` — destructive actions enabled iff at least one
  selected row is non-root; actual action helpers already prune root.
- `can_move_up/down` can be permissive: enabled iff there is at least one
  non-root selected row. The move helper itself returns `False` if no block
  can move. This avoids fragile per-selection preview logic.
- paste submenu should enable `Multi Paste` / `Multi Insert` / `Multi Replace`
  based on `clipboard_has and has_selection`.

---

## 2) Correct target semantics

### 2.1 Paste / multi-paste (`Ctrl+V`)

**Single selected row / no multi-selection:** existing auto behaviour:

- current container → append clipboard entries as children,
- current leaf → insert clipboard entries after current leaf,
- no selection → append at root.

**Multi-selection:** paste all clipboard entries at every selected target:

- selected container → append all entries as children,
- selected leaf → insert all entries after that leaf,
- one undo step.

### 2.2 Multi-insert (`Ctrl+Shift+V`)

Top-level-only, no deep scan:

1. `targets = top_level_source_rows(view)` sorted by source path.
2. `entries = entries_from_clipboard()` top-level only.
3. Pair by `zip(targets, entries)`.
4. For each pair, insert the paired entry **after** its target.
5. Count mismatch policy: zip-to-shortest. Extra targets untouched; extra
   entries ignored. Optional status message.
6. One undo step.

Examples:

```python
# Tree:        a, b, c
# Selection:   a     c
# Clipboard: [100, 200]
# Result:     a, 100, b, c, 200
```

For OBJECT parents, inserted names come from clipboard entry name when
available, otherwise `new_key`, with existing collision avoidance.
For ARRAY parents, names are ignored.

### 2.3 Multi-replace (`Ctrl+Alt+V` proposed, or menu-only first)

Top-level-only, no deep scan:

1. `targets = top_level_source_rows(view)` sorted by source path.
2. `entries = entries_from_clipboard()`.
3. Pair by `zip(targets, entries)`.
4. For each pair, replace target's entire subtree with the entry's value.
5. Names of target rows are preserved.
6. One undo step.

This is the current `paste_insert_zip()` implementation, but it must be
renamed and separately exposed so "insert" no longer means replace.

---

## 3) Implementation plan

### 3.1 Tests first — add/adjust failing coverage

Create or update tests in `tests/test_multi_action_semantics.py` and
`tests/test_context_menu_multiselect.py`.

#### Multi-paste tests

1. `test_ctrl_v_dispatches_to_multi_paste_when_multiple_rows_selected`
   - Select two leaves, set clipboard to scalar.
   - Call the same function used by `_run_tree_action(paste=True)`.
   - Assert two inserts, one after each selected leaf.
   - This currently fails because `_run_tree_action` calls
     `paste_from_clipboard()` and only current row receives the paste.

2. `test_multi_paste_same_parent_inserts_after_each_target_not_only_last`
   - Tree `a,b,c,d`, select `a,c`, clipboard `99`.
   - Expected order: `a,new_key,b,c,new_key_2,d` (or equivalent unique names).
   - Assert two inserted values are present and placed after both targets.

3. `test_multi_paste_preserves_single_undo_step`
   - Multi target paste.
   - Assert `undo_stack.count()` increments by exactly one and undo restores.

#### Multi-insert tests

1. Replace existing `test_multi_insert_zip_replaces_each_target_with_paired_entry`
   with `test_multi_insert_zip_inserts_after_each_paired_target`.
   - Tree `a,b,c`, select `a,c`, clipboard `[100,200]`.
   - Expected: values after `a` and after `c`; original `a`/`c` unchanged.

2. `test_multi_insert_zip_no_deep_scan`
   - Select `a` and `a.x`; clipboard `[42]`.
   - Only top-level `a` is a target; insert after `a`, not after `a.x`.

3. `test_multi_replace_zip_replaces_values_separately`
   - New action name.
   - Assert current replacement semantics still exist under `paste_replace_zip()`.

#### Context-menu tests

Use direct helper tests rather than invoking a modal `QMenu.exec()`.

1. `test_context_menu_prepare_preserves_selection_when_clicking_selected_value_cell`
   - Select two rows (value column cells or rows).
   - Call `_prepare_context_selection(view, value_cell_of_selected_row)`.
   - Assert both rows remain selected.

2. `test_context_menu_prepare_resets_selection_when_clicking_unselected_row`
   - Select two rows.
   - Right-click third row.
   - Assert selection becomes only third row.

3. `test_context_menu_paste_action_uses_preserved_multiselect`
   - Prepare selection with helper.
   - Trigger paste dispatcher.
   - Assert multi-paste, not single paste.

### 3.2 Paste API changes (`tree_actions/paste.py`)

Add explicit function names:

```python
def paste_auto(tree_view):
    rows = selected_source_rows(tree_view)
    if len(rows) > 1:
        return paste_clones_at_targets(tree_view)
    return paste_from_clipboard(tree_view)


def paste_insert_after_zip(tree_view):
    ...  # true multi-insert


def paste_replace_zip(tree_view):
    ...  # current paste_insert_zip body
```

Refactor shared insert planning:

```python
def _entries_for_parent(parent_item, entries, used_names): ...
def _insert_entry_records_at(tab, parent_index, insert_pos, entries, label): ...
def _plan_insert_after_zip(tab, targets, entries): ...
```

Important invariants:

- `paste_auto()` is the only normal paste entrypoint used by shortcuts and
  context menu.
- `_paste_entries_at()` may remain for placement submenu actions, but
  multi-actions should not repeatedly reread clipboard.
- Multi-action insertion planners must sort by parent path + row descending
  before producing command records, so same-parent inserts do not shift later
  target positions.

### 3.3 Tab/action wiring

`documents/tab.py`:

```python
from tree_actions.paste import paste_auto, paste_insert_after_zip, paste_replace_zip

elif paste:
    changed = paste_auto(self.view)
elif paste_zip:
    changed = paste_insert_after_zip(self.view)
elif replace_zip:
    changed = paste_replace_zip(self.view)
```

`documents/tab_setup.py`:

- `Ctrl+V` stays paste auto.
- `Ctrl+Shift+V` should call true multi-insert.
- Proposed `Ctrl+Alt+V` for multi-replace if no shortcut conflict is found;
  otherwise menu-only initially.

### 3.4 Context menu fixes (`tree_actions/context_menu.py`)

Imports:

```python
from PySide6.QtCore import QItemSelectionModel
from tree_actions.selection import selected_source_rows, _row0, _index_path
from tree_actions.paste import paste_auto, paste_insert_after_zip, paste_replace_zip
```

Add:

```python
def _clicked_row_is_selected(tree_view, index) -> bool: ...
def _prepare_context_selection(tree_view, index) -> None: ...
```

Replace:

```python
if index.isValid():
    tree_view.setCurrentIndex(index)
```

with:

```python
_prepare_context_selection(tree_view, index)
```

Paste submenu:

- `Paste (auto)` → `paste_auto`.
- `Paste After` remains explicit single/current placement; if selection is
  preserved and multiple rows are selected, decide whether it should:
  - remain current-row only, or
  - become multi-aware too.

Recommendation: keep explicit placement actions current-row only for now, but
label them clearly if multi-selection exists:

- `Paste After Current Row`
- `Paste as Child of Current Row`

Add multi-action entries:

- `Paste at All Selected` → `paste_clones_at_targets`
- `Paste Each After Selected` → `paste_insert_after_zip`
- `Replace Each Selected Value` → `paste_replace_zip`

Enable them only when `clipboard_has and selection_count > 1`.

---

## 4) Expected final shortcuts/menu

| Action | Shortcut | Menu label | Function |
| --- | --- | --- | --- |
| Paste auto / multi-paste | `Ctrl+V` | `Paste (auto)` | `paste_auto` |
| Multi-insert after | `Ctrl+Shift+V` | `Paste Each After Selected` | `paste_insert_after_zip` |
| Multi-replace | proposed `Ctrl+Alt+V` or menu-only | `Replace Each Selected Value` | `paste_replace_zip` |
| Single replace | menu-only | `Paste — Replace Current Value` | `paste_replace_value` |

---

## 5) Acceptance criteria

- Right-click on an already-selected value cell preserves the entire
  multi-selection.
- Right-click on an unselected row collapses selection to that row, preserving
  current single-target UX.
- `Ctrl+V` with multiple selected rows inserts at every selected target.
- `Ctrl+V` with one selected row preserves existing single auto paste.
- `Ctrl+Shift+V` inserts paired clipboard entries after paired top-level
  selected targets; it does **not** replace target values.
- Multi-replace remains available under a separate function/action and keeps
  the old replacement semantics.
- All multi-action operations are a single undo step.
- Existing placement-specific context menu actions remain predictable and do
  not accidentally consume a hidden multi-selection unless explicitly labelled
  as multi-actions.
- Tests fail before the implementation and pass after:
  - multi-paste all targets,
  - multi-insert after not replace,
  - multi-replace separate,
  - context-menu preserve/reset selection.

---

## 6) Suggested implementation order

1. Add the failing tests listed in § 3.1.
2. Add `_prepare_context_selection` and test it in isolation.
3. Split `paste_insert_zip` into `paste_insert_after_zip` and
   `paste_replace_zip`.
4. Add `paste_auto` and wire `Ctrl+V` / context `Paste (auto)` to it.
5. Update `Ctrl+Shift+V` to true multi-insert.
6. Add menu entries for multi-insert and multi-replace.
7. Run targeted tests:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q \
  tests/test_multi_action_semantics.py \
  tests/test_context_menu_multiselect.py \
  tests/test_paste_placement.py \
  tests/test_tree_actions_clipboard.py
```

8. Run the known-green suite excluding the documented offscreen-only
   color-scheme failure:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q \
  --ignore=tests/test_app_color_scheme.py \
  --deselect tests/test_theme_switching.py::test_color_scheme_follows_selected_theme
```
