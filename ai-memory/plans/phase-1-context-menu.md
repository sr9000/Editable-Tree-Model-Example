# Phase 1 — Context menu column awareness

**Risk:** low · **Files:** `tree_actions/context_menu.py`,
`tree_actions/clipboard.py` · **Tests:** `tests/test_tree_actions_clipboard.py`

## Issues addressed

- [ ] Disable **all** context actions when the menu opens on the *kind*
      column (col 1).
- [ ] When the menu opens on the *name* column (col 0), `Copy` puts a
      `name: value` payload on the clipboard.
- [ ] When the menu opens on the *value* column (col 2), `Copy` puts
      **only the value** on the clipboard.

## Current behaviour

`tree_actions/context_menu.show_context_menu` builds a single menu
regardless of which column was clicked. `copy_selection` always emits
the full json-tree MIME payload (which keeps the name).

## Plan

1. **Detect column at click time.** Read `index.column()` after
   `tree_view.indexAt(position)`. Three branches:
   - `column == 1` → return early *after* showing only Expand/Collapse
     All (or no menu at all if we want the simplest behaviour). We pick
     "no item-mutating actions": only the `Expand All` / `Collapse All`
     separator block.
   - `column == 0` → standard menu, but `Copy` calls a new
     `copy_selection_with_name(view)`.
   - `column == 2` (or invalid) → standard menu, `Copy` calls a new
     `copy_selection_value_only(view)`.

2. **Extend `tree_actions/clipboard.py`:**
   - keep `copy_selection` (full MIME payload, used by Ctrl+C — we do
     **not** change keyboard shortcut behaviour),
   - add `copy_selection_with_name(view)` → `text/plain` of
     `f"{name}: {value_str}"` plus the existing JSON-tree MIME blob,
   - add `copy_selection_value_only(view)` → `text/plain` of the
     formatted value (use `delegates.value_formatting.format_with_type`
     so PERCENT/BYTES render the human form), no JSON-tree MIME.

3. **Reuse formatting:** the new helpers must call into
   `delegates.value_formatting.format_with_type(value, json_type)` so
   text matches what the user sees in the cell.

4. **Tests** (`tests/test_tree_actions_clipboard.py`):
   - context menu opened on col 1 has zero item-mutating actions
     enabled,
   - context-menu Copy on col 0 puts `"foo: 42"` on clipboard,
   - context-menu Copy on col 2 puts `"42"` on clipboard.

## Out of scope

- Ctrl+C keyboard shortcut keeps the rich-payload behaviour
  (full JSON-tree MIME) — only the menu items are column-aware.
- No changes to Cut / Paste / Delete semantics.

## Acceptance

- Suite green.
- Manual: right-clicking on a type cell shows a context menu without
  Copy/Cut/Delete/etc. Right-clicking on a name cell and choosing Copy
  yields `name: value` text. Right-clicking on a value cell yields
  the value only.
