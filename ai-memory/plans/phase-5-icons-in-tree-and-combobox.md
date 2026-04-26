# Phase 5 — Icons in tree column 1 and the type combobox

## Deliverable

Type icons render:
- in the **Type** column (col 1) of every tree row, next to the type
  name;
- in the **`JsonTypeDelegate` combobox** when changing a row's type.

Icons are sourced from the active `IconProvider` (Phase 4). A bundled
default SVG set ships under `themes/builtin/icons/` and is referenced
by both built-in YAMLs.

## Scope

### Bundled SVG set

`themes/builtin/icons/` — one SVG per `JsonType`, monochrome where
possible so a single file works for both light and dark themes
(coloured by `QIcon` mode hints if needed). Initial keys (logical
names used in YAML):

```
integer, float, percent, boolean, string, unicode, multiline, text,
date, time, datetime, datetimezone, bytes, zlib, gzip,
null, object, array
```

Both `light.yaml` and `dark.yaml` get:

```yaml
icons:
  search_paths: ["./icons"]
  map:
    integer: integer
    float: float
    # ... full mapping for every JsonType
```

(Light and dark may point at different folders if monochrome SVGs are
not enough; the default ships one shared set.)

### `tree/model_roles.py`

- Extend the existing `data(index, role)` switch:
  - When `role == Qt.DecorationRole and column == 1`: return
    `self._icon_provider.for_type(item.json_type)` (the model gains
    an optional `icon_provider: IconProvider | None` set by
    `JsonTab`; falls back to `StubIconProvider` so headless tests
    that build a bare model keep working).
- No change for col 0 / col 2 in this phase.

### `JsonTreeModel`

- New ctor kwarg `icon_provider: IconProvider | None = None` (default
  → `StubIconProvider()`).
- `set_icon_provider(provider)` triggers `dataChanged` for col 1 of
  every visible row (use `layoutChanged` only as a last resort —
  `dataChanged` over the whole column is enough and preserves
  expansion).

### `delegates/type_delegate.py`

- `createEditor` populates the `QComboBox` with `addItem(icon, text,
  data)` using `self._icon_provider.for_type(t)`.
- `JsonTypeDelegate.__init__` gains `icon_provider: IconProvider`.

### Wiring

- `MainWindow` builds the icon provider once via
  `registry.build_icon_provider(self._theme)` and shares it with
  every `JsonTab` (themes are app-global, not per-tab).
- `JsonTab.set_theme(theme, icon_provider)` swaps both.

## Hi-DPI

- All SVGs are vector; `QIcon` handles DPR automatically.
- Set `QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)` only if
  not already set in `main.py` (Qt 6 enables it by default but verify).

## Tests (`tests/test_icons_in_view.py`)

- Bare model with `StubIconProvider`: `data(index_col1,
  DecorationRole).isNull()` is `True`.
- Themed model with `FileIconProvider` pointing at `themes/builtin/
  icons/`: every leaf row returns a non-null icon for col 1.
- `JsonTypeDelegate` combobox built with the same provider has a
  non-null icon for every entry.
- Switching theme via `JsonTab.set_theme(other, other_provider)`
  emits `dataChanged` for col 1 (any-row, any-leaf is enough).

## Done criteria

- Open `data.yaml`: every row shows a small icon next to its type
  name.
- Edit a row's type: dropdown shows the same icons.
- All previous tests still green; new icon-in-view tests green.
- The whole icon system is opt-out: a user theme with empty
  `icons.map` falls back to `StubIconProvider` and the UI still
  works (no empty rectangles, just no icons).
