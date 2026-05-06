# Phase 5 — App-level light/dark theme

**Risk:** low–medium · **Files:** `app/theme_controller.py`,
`main.py` (or `app/main_window.py` init) ·
**Tests:** `tests/test_theme_switching.py` (extend), new
`tests/test_app_color_scheme.py`

## Issue addressed

- [ ] Selecting a theme used to **only** colour the tree content
      (per-type fg/bg, type icons). The window chrome (menus,
      toolbars, dialogs) kept the system default. We want the app to
      flip between Qt's stock light and dark looks based on the
      active theme's `mode`, while keeping the existing per-type
      delegate colouring untouched.

## Scope (intentionally narrow)

- **No** custom `QPalette` overrides.
- **No** stylesheet template.
- **No** new fields on `Palette` / `ThemeSpec`.
- The only thing that changes app-wide is Qt's built-in colour
  scheme: `Qt.ColorScheme.Light` vs `Qt.ColorScheme.Dark`.
- Per-type fg/bg/bold/italic on cells stays where it is today
  (`ValueDelegate` / `JsonTypeDelegate`).

## Plan

### 5.1 Flip Qt's stock color scheme on theme apply

Qt 6.8+ exposes `QStyleHints.setColorScheme(Qt.ColorScheme)` which
toggles the bundled Fusion / native light vs. dark palette without
us authoring any colours.

`ThemeController.apply_theme(theme)` becomes:

```python
def apply_theme(self, theme: ThemeSpec) -> None:
    self._theme = theme
    self._icon_provider = self._theme_registry.build_icon_provider(theme)
    self._sync_app_color_scheme(theme)
    self._on_theme_changed(theme, self._icon_provider)
    self.refresh_theme_menu_checks()

def _sync_app_color_scheme(self, theme: ThemeSpec) -> None:
    app = QGuiApplication.instance()
    if not isinstance(app, QGuiApplication):
        return
    style_hints = app.styleHints()
    setter = getattr(style_hints, "setColorScheme", None)
    if setter is None:
        return  # older Qt — nothing to do, leave system default
    target = Qt.ColorScheme.Dark if theme.mode == "dark" else Qt.ColorScheme.Light
    if style_hints.colorScheme() != target:
        setter(target)
```

That's the entire app-chrome change.

### 5.2 Avoid feedback loop with `colorSchemeChanged`

`ThemeController.on_system_color_scheme_changed` is connected to
`styleHints().colorSchemeChanged`. Calling `setColorScheme` re-fires
that signal, so we must not let it re-resolve the theme. Two
options, pick the simpler one:

- **Preferred:** add a guard flag `self._suppress_scheme_signal` set
  while `_sync_app_color_scheme` runs; check at the top of
  `on_system_color_scheme_changed`.
- Alternative: only re-resolve in `on_system_color_scheme_changed`
  when `get_follow_system()` is true *and* the new scheme differs
  from the active theme's mode; the existing code already gates on
  `follow_system`, so adding the mode check is a one-liner.

Both are safe; the guard flag is easier to reason about.

### 5.3 Apply on launch

`MainWindow.__init__` already constructs `ThemeController` and calls
`_apply_theme(self._controller.theme)` during startup; no new wiring
needed — `_sync_app_color_scheme` runs as part of `apply_theme`.

If `MainWindow` doesn't currently call `apply_theme` at the end of
init, add a single explicit call so the very first paint already has
the right colour scheme.

### 5.4 Tests

- `tests/test_app_color_scheme.py` (new):
  - applying a `mode="light"` theme leaves
    `QGuiApplication.styleHints().colorScheme()` at
    `Qt.ColorScheme.Light`.
  - applying a `mode="dark"` theme flips it to
    `Qt.ColorScheme.Dark`.
  - guarded against feedback: handler does not call `apply_theme`
    again during the same flip.
- extend `tests/test_theme_switching.py` to assert the colour scheme
  follows the selected theme.

The tests must save and restore the original colour scheme around
each case (autouse fixture) so they don't leak global state into
other suites.

## Out of scope (deferred / dropped)

- Custom `QPalette` overrides per theme.
- Stylesheet selectors for QMenu / QToolBar / QToolTip / etc.
- New `Palette` keys (`window_bg`, `tooltip_*`, `border`, …).
- Author-driven full re-skinning. If a future user theme wants
  custom chrome, that's a new phase; this one is intentionally
  minimal.

## Acceptance

- Suite green.
- Manual: switching to a dark theme flips menus / status bar /
  dialogs to Qt's stock dark look; switching to a light theme flips
  back. Per-type cell colours from the active `ThemeSpec` remain
  visible and correct on both backgrounds.
