# Phase 7 — Docs, screenshots, accessibility tests

## Deliverable

Project-grade documentation and a tightened test surface so that
third-party theme authors can ship working themes without reading
source code.

## Scope

### `themes/builtin/schema.md`

A reference document covering:

- Top-level keys: `name`, `mode`, `palette`, `types`, `icons`.
- Every `JsonType` key (with a one-line semantic note linking back
  to `tree/types.py`).
- `TypeStyle` fields: `fg`, `bg`, `bold`, `italic`, `icon`.
- Color value formats accepted by the loader.
- Search-path resolution rules for icons.
- Fallback behaviour: every missing key falls back to the built-in
  default for the declared `mode`.
- Five worked-example themes (light minimal, dark minimal, high-
  contrast, mono-only icons, icons-only-no-color).

### `README.md` updates

- "Theming" section with two screenshots (light + dark) of
  `data.yaml` open in the editor.
- Pointer to `themes/builtin/schema.md` and the user-themes
  directory location per OS:
  - Linux: `~/.config/<APPLICATION_ID>/themes/`
  - macOS: `~/Library/Application Support/<APPLICATION_ID>/themes/`
  - Windows: `%APPDATA%/<APPLICATION_ID>/themes/`

### Round-trip and snapshot tests

`tests/test_theme_snapshot.py`:

- Snapshot test: for each built-in theme, serialize the resolved
  `ThemeSpec` to a deterministic dict and compare against a checked-
  in JSON snapshot under `tests/snapshots/themes/`. Catches
  accidental changes to default palettes.
- Property test (Hypothesis-style, hand-rolled if no Hypothesis
  dep): random partial overrides on top of `LIGHT_DEFAULT` always
  produce a `ThemeSpec` whose `types` covers every `JsonType`.

### Accessibility tests

`tests/test_theme_accessibility.py`:

- For each built-in theme, every `TypeStyle.fg` against the
  theme's `palette.base_bg` clears WCAG-AA contrast (≥4.5:1).
- Selection text against `palette.selection_bg` clears AA.
- A regression test: changing a built-in colour to an AA-failing
  value causes this test to fail loudly (sanity check that the
  guard works).

### `requirements.txt` review

- Confirm `PyYAML` is pinned (already is per `repo-map.md`).
- No new runtime deps required.

### `Makefile`

Add a target:

```make
themes-check:
	QT_QPA_PLATFORM=offscreen pytest -q tests/test_theme_loader.py \
	    tests/test_theme_registry.py \
	    tests/test_value_delegate_theme.py \
	    tests/test_icon_provider.py \
	    tests/test_icons_in_view.py \
	    tests/test_theme_switching.py \
	    tests/test_theme_snapshot.py \
	    tests/test_theme_accessibility.py
```

So a theme contributor can validate just the theming surface in
isolation.

### `ai-memory/` updates

- `repo-map.md`: add a `themes/` package section under "Top-level
  module / package layout"; add the new test files to section 13;
  bump the test count.
- `pros-n-cons.md`: move "Type icons in column 1" out of "Stretch
  UX items deferred from Phase 5" and into "Pros". Add a new line
  in Pros for the colorscheme system. If anything new becomes a
  con (e.g. extra startup IO from theme loading), record it.
- `todo-n-fixme.md`: tick off any items the theming work resolved.

## Done criteria

- A new contributor can author a working theme YAML using only
  `themes/builtin/schema.md` and one of the built-ins as a
  template.
- `make themes-check` runs the full theming-related test surface
  cleanly.
- `make test` (when it lands per Phase 6 of the master plan)
  includes the theming tests.
- All Phase 1–6 tests still green; new docs/tests green.
