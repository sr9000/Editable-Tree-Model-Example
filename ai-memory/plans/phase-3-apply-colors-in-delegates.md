# Phase 3 — Apply colors in delegates

## Deliverable

Per-`JsonType` colors visible in the tree view, sourced from the
active `ThemeSpec`. Selection highlight stays correct. Bold/italic
flags from the theme apply. No icons yet.

## Scope

### Where the theme is held

- `MainWindow.__init__` builds a `ThemeRegistry`, resolves the active
  `ThemeSpec` via `state.theme_settings.resolve_active_theme`, and
  stores it as `self._theme: ThemeSpec`.
- `MainWindow._add_tab` passes `theme=self._theme` into `JsonTab`.
- `JsonTab` stores `self._theme` and forwards it into
  `documents/tab_setup.py` when constructing delegates.
- `set_theme(theme)` on `JsonTab` swaps the spec and emits
  `model.dataChanged(top_left, bottom_right, [Qt.ForegroundRole,
  Qt.BackgroundRole, Qt.FontRole])` to repaint without rebuilding.

### `delegates/value.py` and `delegates/value_formatting.py`

- `ValueDelegate.__init__` gains a `theme: ThemeSpec` arg.
- `initStyleOption(option, index)`:
  1. Call super.
  2. Read `JSON_TYPE_ROLE`.
  3. Look up `style = self._theme.types[json_type]`.
  4. **If `option.state & QStyle.State_Selected`:** do *not* override
     fg/bg (let the platform highlight win). Optionally still apply
     bold/italic via `option.font`.
  5. Else: set `option.palette.setColor(QPalette.Text, style.fg)` and
     (if `style.bg`) `option.backgroundBrush = QBrush(style.bg)`.
  6. Apply bold/italic to `option.font`.

### `delegates/type_delegate.py` (col 1)

- Same theme injection. Color the *combo display text* in the cell
  (when not editing) using the same `TypeStyle` lookup, so the type
  column visually echoes the value column. When editing, leave the
  combobox alone (Phase 5 adds icons there).

### `delegates/name_delegate.py` (col 0)

- No color override in this phase. Keep the existing italic-on-
  non-ASCII rule from `tree/model_roles.py` `FontRole`.

### `tree/model_roles.py`

- **Unchanged in app flow.** The model still returns `FontRole` for
  non-ASCII names; delegates layer their theme styling on top via
  `option.font`. Keeping the model theme-agnostic preserves headless
  test invariants.

## Selection-aware color blending

If a theme is configured with strong backgrounds, selection over a
themed cell can wash out. Helper in `delegates/value_formatting.py`:

```python
def _apply_type_style(option, style, *, selected: bool) -> None:
    if selected:
        # only font weight/italic
        ...
    else:
        ...
```

Unit-tested with a fake `QStyleOptionViewItem`.

## Tests (`tests/test_value_delegate_theme.py`)

- For each `JsonType`, build a one-row model with a value of that
  type, call `initStyleOption`, assert
  `option.palette.color(QPalette.Text)` equals
  `theme.types[t].fg` (when `fg` is set).
- With `option.state |= QStyle.State_Selected`, foreground is **not**
  overridden.
- Bold/italic flags propagate to `option.font.bold()` /
  `option.font.italic()`.
- Switching theme via `JsonTab.set_theme(other)` triggers
  `dataChanged` covering the value column for every leaf row (count
  of emissions ≥ 1, top-left/bottom-right span verified).

## Done criteria

- Visual smoke: open `data.yaml`, integers/floats/strings/bytes/null
  each render in distinct colors under both built-ins.
- Headless tests for delegate color application pass.
- All previously-green tests stay green (model/role tests must not
  regress; if any started asserting plain-default palette, update
  them to take a theme fixture).
