# Phase 4 — Display & preview

**Risk:** medium · **Files:** `tree/item.py`,
`tree/model_roles.py`, `delegates/value_formatting.py`,
`delegates/value.py`, `delegates/name_delegate.py` ·
**Tests:** `tests/test_phase_5_2_display_formatting.py` (extend),
new `tests/test_container_preview.py`

## Issues addressed

- [ ] Object/array rows show no useful info when the user has not
      expanded them.
- [ ] Object/array rows still show no useful info when **expanded**
      (only `<no type>`-ish).
- [ ] Array indices in col 0 currently render as plain `0, 1, 2`. The
      user wants `#0, #1, #2` (or `#1, #2, …` — see decision below).
- [ ] PERCENT cells: there's a path where the *raw* mpq leaks instead
      of `"50%"` (status-bar size hint, possibly some EditRole
      consumers).
- [ ] Theme styling currently lives only on the *type* (kind) column.
      Per-type fg/bg/bold/italic should also colour the *value* cell
      (this is already half-done in `ValueDelegate.initStyleOption`,
      but the user reports it visually missing — investigate).

## Decisions

- **Array index format:** `#1, #2, #3, …` (1-based). This pairs with
  the Phase-3 placeholder names `item1, item2, …` and feels less
  techy than `#0`. (The internal row index stays 0-based.)
- **Container preview budget:** 80 chars total (matches existing
  long-string elision); ellipsise the joined preview, not individual
  values.
- **Container meta string:** 
  - OBJECT: `{N keys}` when collapsed, `{N keys}  k1, k2, …` short preview.
  - ARRAY: `[N items]` when collapsed, `[N items]  v1, v2, …` short preview.
  - When expanded, the same meta string still shows in the value cell
    so the user always sees the count even with the row open.

## Plan

### 4.1 Container value-cell text

Currently `JsonTreeItem.data(2)` returns `[]` / `{}` for ARRAY/OBJECT
and `format_default(value)` renders `"[]"` / `"{}"`. We move the
preview/meta into `delegates/value_formatting.format_with_type` so
the model stays primitive-only.

```python
def format_with_type(value, json_type, *, item=None):
    if json_type is JsonType.ARRAY and item is not None:
        return _format_array_preview(item)
    if json_type is JsonType.OBJECT and item is not None:
        return _format_object_preview(item)
    ...existing branches...
```

`_format_array_preview(item)`:
- `n = item.child_count()`
- header: `f"[{n} items]"` (singular: `1 item`)
- for first ≤ 5 children, append `format_default(child.value)` for
  primitive leaves; for nested containers append `[...]` / `{...}`
- joined with `", "`, total budget 80 chars, ellipsis if exceeded

`_format_object_preview(item)`: same, but render `f"{name}: {value}"`
per child.

`ValueDelegate.initStyleOption` reads the `JsonTreeItem` via
`source_index.internalPointer()` (already used elsewhere) and passes
it to `format_with_type`.

### 4.2 Array index `#i`

In `tree/item.py:data(0)`:

```python
if self.parent_item is not None and self.parent_item.json_type is JsonType.ARRAY:
    return f"#{self.row() + 1}"
```

`tree_actions/clipboard.copy_selection_with_name` (Phase 1) and the
breadcrumb in `documents/tab_status.py` must keep using
`_qualified_name`, which builds `$.foo[2]` — the **path** stays
0-based and bracketed; only the column-0 *display* label changes.
Document this in a comment.

### 4.3 Percent always shown as percent

Audit all DisplayRole / Edit-related sites:

1. `delegates/value_formatting.format_with_type` already does it
   (`f"{float(q*100):g}%"`).
2. `tree/model_roles.display_role_value` does **not** special-case
   PERCENT — it falls through to `mpq_serialization`. For consumers
   that read `Qt.DisplayRole` directly (filter proxy text-match,
   tooltip prefix, status bar) the user sees `1/2` instead of `50%`.
3. `documents/tab_status._size_hint_for_item` — check whether it
   reports PERCENT as text/size; if so, normalize through the same
   formatter.

Fix: add a PERCENT branch in `display_role_value` that mirrors
`format_with_type`'s output. Keep `EditRole` unchanged (editors get
the raw mpq).

### 4.4 Value-cell theme styling

`ValueDelegate.initStyleOption` already calls `_apply_type_style` —
verify that:

- `option.palette.setColor(QPalette.ColorRole.Text, style.fg)`
  actually wins over the QStyle override on the user's platform; if
  not, also set `option.palette.setColor(QPalette.ColorRole.WindowText, style.fg)`.
- `option.backgroundBrush` is honoured by the active style; some
  themes need `option.features |= QStyleOptionViewItem.HasDecoration`
  side effects. Smoke-test via the existing
  `test_value_delegate_theme.py`; if a regression slipped, the test
  should be updated to actually paint the cell into a `QPixmap` and
  sample colours. (The current test only asserts the option mutation;
  expand it.)

If the issue is platform-specific (QStyle eats fg), use a small
`QStyledItemDelegate.paint` override that calls
`option.widget.style().drawControl(CE_ItemViewItem, option, painter)`
after applying both palette colours.

### 4.5 Tests

- `tests/test_container_preview.py`:
  - empty array → `[0 items]`
  - 3-element primitive array → `[3 items]  1, 2, 3`
  - object preview shows `{N keys}` and `key: value, …`
  - long preview elides at 80 chars + `…`
- extend `test_phase_5_2_display_formatting.py`:
  - DisplayRole on PERCENT row returns `"50%"`
- `tests/test_value_delegate_theme.py`:
  - sample painted pixmap and assert pixel color matches the theme's
    PERCENT `fg` (only if expanded test runner allows it; otherwise
    keep option-level assertion).

## Acceptance

- Suite green.
- Manual: container rows are informative both collapsed and expanded;
  array indices read `#1, #2, …`; PERCENT renders consistently
  everywhere; value cells visibly take the theme's per-type colour.
