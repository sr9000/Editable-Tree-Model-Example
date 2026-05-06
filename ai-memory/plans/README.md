# Theming plan — colors now, icons later

Goal: give every `JsonType` a distinct, user-customizable visual
identity (color now, icon later) via human-friendly YAML theme files,
with built-in light/dark schemes and auto-selection.

## Design pillars

1. **Single choke-point.** All presentation flows through
   `delegates/value_formatting.py` (`ValueDelegate.initStyleOption`),
   `delegates/type_delegate.py` (combo box) and `tree/model_roles.py`
   (`DecorationRole`). The theme is read there only.
2. **Pure data theme object.** A `ThemeSpec` dataclass loaded from
   YAML; immutable; injected into delegates at tab construction time
   (`documents/tab_setup.py`).
3. **Total fallback.** Any missing key in a user theme falls back to
   the built-in default for that scheme (light or dark). Loader never
   raises on a partial file.
4. **Color and icons share the same theme file.** A single theme YAML
   declares both `palette:` and `icons:` blocks. Phase 1–3 implement
   the color path; the icons block is parsed but resolves to a
   `_StubIconProvider` until Phase 4–5.
5. **YAML is already a project dependency.** No new runtime deps.

## File layout introduced

```text
themes/
  __init__.py
  spec.py                 # ThemeSpec dataclass + JsonType keys
  loader.py               # YAML → ThemeSpec, with merge/fallback
  registry.py             # discover built-in + user themes
  icon_provider.py        # IconProvider protocol + stub impl
  builtin/
    light.yaml
    dark.yaml
    schema.md             # human-readable theme-file reference
```

User theme override directory:
`QStandardPaths.AppConfigLocation / themes/*.yaml`.

## Phase index

1. [`phase-1-theme-spec-and-loader.md`](phase-1-theme-spec-and-loader.md)
   — dataclass, YAML loader, total fallback, unit tests.
2. [`phase-2-builtin-and-autoselect.md`](phase-2-builtin-and-autoselect.md)
   — ship `light.yaml` / `dark.yaml`, system-mode detection,
   `ThemeRegistry` discovery, `QSettings` persistence.
3. [`phase-3-apply-colors-in-delegates.md`](phase-3-apply-colors-in-delegates.md)
   — wire `ThemeSpec` into `ValueDelegate` and friends, respect
   selection state, optional bold/italic per type.
4. [`phase-4-icon-provider-stub.md`](phase-4-icon-provider-stub.md)
   — `IconProvider` protocol, stub returning `QIcon()`, theme YAML
   `icons:` block parsed and resolved against an asset search path.
5. [`phase-5-icons-in-tree-and-combobox.md`](phase-5-icons-in-tree-and-combobox.md)
   — `DecorationRole` on col 1, `JsonTypeDelegate` combobox icons,
   bundle initial SVG set, hi-DPI handling.
6. [`phase-6-theme-switching-ui.md`](phase-6-theme-switching-ui.md)
   — View → Theme submenu, live switch via `dataChanged`, optional
   file-watcher hot reload.
7. [`phase-7-docs-and-tests.md`](phase-7-docs-and-tests.md)
   — schema reference, README screenshots, round-trip + snapshot
   tests, accessibility (WCAG-AA) check on built-ins.

Each phase is independently shippable. Phases 1–3 are the minimum
viable feature; phases 4–5 add icons; 6–7 polish.
