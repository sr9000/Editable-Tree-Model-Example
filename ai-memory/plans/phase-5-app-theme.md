# Phase 5 — Full-app theme application

**Risk:** high · **Files:** `app/theme_controller.py`,
`app/main_window.py`, `themes/spec.py` (extend `Palette`),
`themes/_defaults.py`, `themes/builtin/*.yaml`,
`themes/loader.py` ·
**Tests:** `tests/test_theme_switching.py`, new
`tests/test_app_palette.py`

## Issue addressed

- [ ] Selecting a custom theme used to **only** colour the tree
      content (per-type fg/bg, type icons). The window chrome (menus,
      toolbars, scrollbars, status bar, tab bar, dialogs) kept the
      system default. Selecting the user's custom theme had no
      visible effect on the surrounding window.

## Current behaviour

`ThemeController.apply_theme` calls `_on_theme_changed` →
`MainWindow.on_theme_changed` → each `JsonTab.set_theme(...)`. This
only emits `dataChanged(...)` against the model and updates the
`ValueDelegate` / `JsonTypeDelegate` snapshots. Nothing touches
`QApplication.setPalette` / `setStyle` / `setStyleSheet`.

## Plan

### 5.1 Extend `themes/spec.py:Palette`

Today: `base_fg, base_bg, selection_fg, selection_bg, accent`.

Add (all optional, default = derived from `base_*` / `selection_*`):

- `window_bg, window_fg`
- `disabled_fg`
- `button_bg, button_fg`
- `tooltip_bg, tooltip_fg`
- `link, link_visited`
- `border` (used by stylesheet)

Each new field has a `_derive_*` fallback so existing YAML keeps
working.

### 5.2 Build a `QPalette` from `Palette`

New module `themes/qt_palette.py`:

```python
def build_qpalette(palette: Palette) -> QPalette: ...
```

Maps every `QPalette.ColorRole` to the closest `Palette` field. For
disabled state, multiply alpha or honour `disabled_fg`.

### 5.3 Build a stylesheet from `ThemeSpec`

`themes/qt_stylesheet.py` — small templated string that styles:

- `QMenu` / `QMenuBar`
- `QToolBar`
- `QStatusBar`
- `QTabWidget::pane`, `QTabBar::tab`
- `QHeaderView::section`
- `QTreeView` (only the chrome — the per-cell colours stay in the
  delegate so they keep winning)
- `QToolTip`
- `QLineEdit`, `QPlainTextEdit` (so dialog editors match)

The stylesheet is a function `build_stylesheet(theme) -> str` so a
test can assert specific selectors / colours appear.

### 5.4 Apply on theme change

`ThemeController.apply_theme` becomes:

```python
def apply_theme(self, theme):
    self._theme = theme
    self._icon_provider = self._theme_registry.build_icon_provider(theme)
    app = QApplication.instance()
    if isinstance(app, QApplication):
        app.setPalette(build_qpalette(theme.palette))
        app.setStyleSheet(build_stylesheet(theme))
    self._on_theme_changed(theme, self._icon_provider)
    self.refresh_theme_menu_checks()
```

The order matters: set palette **before** the stylesheet so style
inheritance picks up palette role colours first.

### 5.5 Style respect on app launch

`main.py` constructs `QApplication`, then `MainWindow`. `MainWindow`
constructs `ThemeController` and calls `apply_theme(self._theme)`
**after** the window is shown so menus / status bar exist when the
stylesheet is set.

Add an explicit `controller.apply_theme(controller.theme)` at the end
of `MainWindow.__init__` (or wherever the controller is created — see
existing wiring; `_apply_theme` compatibility wrapper is already in
place for tests).

### 5.6 Built-in YAML coverage

Update `themes/builtin/light.yaml` and `dark.yaml` to set the new
palette keys. Where a theme author omits them, `themes/loader.py`
falls back via the `_derive_*` helpers in 5.1 so missing keys remain
non-fatal (matches existing total-fallback semantics).

### 5.7 Tests

- `tests/test_app_palette.py` (new):
  - applying `LIGHT_DEFAULT` sets `QApplication.palette().window()` to
    the expected colour,
  - applying `DARK_DEFAULT` flips it,
  - stylesheet contains `QMenuBar` / `QToolTip` selectors,
  - applying twice is idempotent.
- extend `tests/test_theme_switching.py`:
  - switching themes via the menu propagates palette change to a
    sibling widget (e.g. a freshly-constructed `QMenu`).
- existing `test_value_delegate_theme.py` stays unchanged (per-cell
  colour still wins because the delegate sets it on `option.palette`).

## Risks / mitigations

- **Stylesheet vs. native style** — heavy stylesheets can override
  Fusion / system styles in surprising ways. Mitigation: keep the
  stylesheet minimal and *additive* (only colour properties, no
  border-radius experiments).
- **Test parallelism** — `QApplication.setPalette` is global. Tests
  that rely on the default palette may break; gate with a fixture
  that snapshots-and-restores palette/stylesheet around each test.
- **Hot reload** — `ThemeController.reload_themes` already calls
  `apply_theme`, so the new palette/stylesheet path is exercised on
  every YAML edit. Watcher latency is unchanged (250 ms debounce).

## Acceptance

- Suite green (with the new fixture).
- Manual: switching to a dark user theme darkens menus, tabs, status
  bar, dialogs, tooltips. Switching back to a light theme reverts.
