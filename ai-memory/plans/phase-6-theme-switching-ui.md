# Phase 6 — Theme switching UI & live reload

## Deliverable

A user-facing way to pick a theme without restarting, plus optional
hot reload when a user theme YAML on disk changes.

## Scope

### View → Theme submenu

Built in `app/main_window_actions.py` from
`MainWindow._theme_registry.list_themes()`:

```
View
└── Theme
    ├── ✓ Follow system
    ├── ─────────
    ├── Light themes
    │   ├── ● Default Light
    │   └── ○ Solarized Light
    ├── Dark themes
    │   ├── ● Default Dark
    │   └── ○ Solarized Dark
    ├── ─────────
    ├── Reload themes        (re-scans user dir)
    └── Open themes folder…  (opens AppConfigLocation/themes in OS file manager)
```

- When **Follow system** is checked, picking a theme updates the
  matching slot (light name when system is light, dark name when
  dark) and persists it via `state.theme_settings`.
- When **Follow system** is unchecked, picking a theme switches
  immediately to that theme regardless of system mode.
- All checkmarks are radio-style within their light/dark group.

### Live switching

`MainWindow._apply_theme(theme)`:

1. Build a fresh `IconProvider` via
   `registry.build_icon_provider(theme)`.
2. For each open tab: `tab.set_theme(theme, icon_provider)`.
3. Emit `dataChanged` from each tab's model spanning all visible
   rows × all columns with roles `[ForegroundRole, BackgroundRole,
   FontRole, DecorationRole]`.
4. Update menu checkmarks.

No tab rebuild, no model rebuild, no view reset — undo stack and
expansion state must survive the switch.

### Hot reload (optional, gated by setting)

`QSettings(APPLICATION_ID, "theme")` key
`theme/watch_user_dir: bool = false` (default off, opt-in).

When on:
- A `QFileSystemWatcher` watches
  `QStandardPaths.AppConfigLocation / themes/` for changes.
- Debounced 250 ms via `QTimer.singleShot`. On fire:
  `registry.reload(); _apply_theme(registry.get(active_name))`.

### Style on system colour-scheme change

Connect to `QGuiApplication.styleHints().colorSchemeChanged` (Qt
6.5+) when **Follow system** is on. On signal: re-resolve the active
theme via `state.theme_settings.resolve_active_theme` and apply it.

## Tests (`tests/test_theme_switching.py`)

- Switching theme on a tab preserves: undo stack `count()`,
  `cleanIndex()`, the set of expanded paths, and the current
  selection path.
- `Follow system` toggling persists to `QSettings` and is restored
  on next `MainWindow` instantiation.
- Hot reload: write a new YAML to a tmp user dir, fire the
  filesystem watcher, assert that
  `MainWindow._theme_registry.list_themes()` includes it.
- `_apply_theme` emits `dataChanged` over all leaf rows of every
  open tab (parametrised over 0, 1, 3 tabs).

## Done criteria

- Theme can be changed without closing the file or losing undo
  history.
- Recent-files / view-state continue to round-trip identically.
- Hot reload (when enabled) picks up edits to a user theme YAML
  within ~½ second.
- All previous tests still green; new switching tests green.
