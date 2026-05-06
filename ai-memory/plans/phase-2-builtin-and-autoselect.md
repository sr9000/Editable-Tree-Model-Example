# Phase 2 — Built-in light/dark + auto-select

## Deliverable

Two shipped theme files (`themes/builtin/light.yaml`,
`themes/builtin/dark.yaml`), a `ThemeRegistry` that discovers built-in
and user themes, and an auto-selection rule based on the system color
scheme. No delegate wiring yet.

## Scope

### `themes/builtin/light.yaml` and `dark.yaml`

- Hand-tuned to the values in `_defaults.py` (Phase 1) so that
  `load_theme_yaml(builtin/light.yaml)` is structurally equal to
  `LIGHT_DEFAULT` (a Phase-1 test enforces this).
- Both pass a WCAG-AA contrast check against their `base_bg`
  (≥4.5:1 for non-italic styles, ≥3:1 for italic accents). A small
  helper `themes/_contrast.py` computes ratios for the test only.

### `themes/registry.py`

```python
class ThemeRegistry:
    def __init__(self, user_dir: Path | None = None) -> None: ...
    def reload(self) -> None
    def list_themes(self) -> list[ThemeHandle]    # name + mode + path
    def get(self, name: str) -> ThemeSpec
    def default_for_mode(self, mode: Literal["light","dark"]) -> ThemeSpec
```

- Discovery order: built-in (packaged via `importlib.resources`) →
  user dir (`QStandardPaths.AppConfigLocation / themes/*.yaml`).
- User themes with the same `name:` as a built-in **override** the
  built-in (logged at INFO).
- Broken user file → logged at WARNING, skipped, registry still
  serves the rest.

### `themes/auto.py`

```python
def detect_system_mode(app: QGuiApplication) -> Literal["light", "dark"]
```

Resolution order:
1. `app.styleHints().colorScheme()` (Qt 6.5+) if it returns
   `Qt.ColorScheme.Light` or `Qt.ColorScheme.Dark`.
2. Fallback heuristic: lightness of `app.palette().window().color()`
   (≥128 → light else dark).

### `state/theme_settings.py` (new, sibling of `view_state.py`)

- `QSettings(APPLICATION_ID, "theme")` keys:
  - `theme/follow_system: bool` (default `true`)
  - `theme/light_name: str` (default `"Default Light"`)
  - `theme/dark_name: str` (default `"Default Dark"`)
- `resolve_active_theme(registry, app) -> ThemeSpec` returns the
  spec to use right now.

## Tests (`tests/test_theme_registry.py`)

- Built-in light reproduces `LIGHT_DEFAULT`; built-in dark reproduces
  `DARK_DEFAULT` (structural equality on every `TypeStyle`).
- WCAG-AA contrast on both built-ins.
- User-dir override wins over built-in with the same `name`.
- Broken user file does not break registry init.
- `detect_system_mode` honours `Qt.ColorScheme.Dark` when set, else
  falls back to palette lightness (parametrised over both branches).

## Done criteria

- `themes/builtin/light.yaml` and `dark.yaml` exist and load without
  warnings.
- `ThemeRegistry().get("Default Light")` returns a
  `ThemeSpec` covering every `JsonType`.
- All Phase-2 tests green; Phase-1 tests still green.
- No `documents/` / `delegates/` import yet — registry is still
  self-contained.
