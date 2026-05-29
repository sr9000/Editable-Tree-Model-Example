# TODO & FIXME

_Last updated: **2026-05-26**_

Format: `- [ ] [scope] description — file:symbol`

## Validation follow-ups
- [ ] [validation] URL schema staleness — no `ETag` /
      `If-Modified-Since` conditional request on `reload()`; URL
      schemas are always re-fetched.
      — `validation/schema_registry.py`, `validation/schema_source.py`
- [ ] [validation] Inline `$schema` blocks / embedded schema literals
      have no content-hash dedup yet; dedup currently keys file paths
      and URLs only.
      — `validation/schema_registry.py`, `validation/schema_source.py`
- [ ] [feature] Remote `$ref` resolution against `http(s)://` — currently remote
      `$schema` URLs are silently ignored; implement via a configurable HTTP resolver
      passed to `jsonschema` or a pre-fetch cache.
      — `validation/schema_source.py`, `validation/_engine.py`
- [ ] [ux] Schema-authoring UX — "JSON Schema Draft picker" (Draft 7 ↔ Draft
      2020-12) combo in the dock; per-tab draft override for validation.
      — `app/validation_dock.py`, `validation/_engine.py`
- [ ] [ux] Per-issue quick-fix actions — context menu on a validation issue in
      the dock list (e.g., "Add missing required key", "Change type to string").
      — `app/validation_dock.py`, `tree_actions/structure.py`
- [ ] [tests] WCAG snapshot tests for validation-badge theme colours
      (`themes/_contrast.py` is available; `VALIDATION_SEVERITY_ROLE` paints
      cells, but no accessibility regression suite exists yet).

## Secret strings follow-ups (v2)
- [ ] [secret] Persist secret kind for non-matching field names (schema-sidecar
      or equivalent metadata), so sticky secrets survive reload after rename.
      — `tree/item.py`, `io_formats/{dump,load}.py`, `state/`
- [ ] [secret, security] Clipboard scrubbing policy for revealed secret values
      (clear/expire clipboard after copy operations).
      — `tree_actions/clipboard.py`, secret editor paths in `delegates/value.py`
- [ ] [secret, ux] Manual override surface for secret kinds (type delegate
      entry or context-menu action) rather than name-heuristic only.
      — `delegates/type_delegate.py`, `tree_actions/context_menu.py`
- [ ] [secret, ux] Reveal-in-view action with global timer (cell-level reveal,
      not editor-only reveal).
      — `delegates/value.py`, `tree_actions/context_menu.py`

- [ ] [tests] `tests/test_value_delegate.py`: full editor matrix.
      - editor widget class per `JsonType`
      - `setEditorData` / `setModelData` round-trip for INTEGER, mpq
        FLOAT/PERCENT, BOOLEAN, DATE/TIME/DATETIME/DATETIMEZONE,
        STRING/UNICODE
      - dispatch-by-widget-class survives stale editors
      - dialog-based delegates (MULTILINE/TEXT/BYTES/ZLIB/GZIP)
        commit via `QPersistentModelIndex` + `JsonTab.commit_set_data`
- [ ] [tests] `tests/test_io_roundtrip.py`: parametrized round-trip
      property tests against `data.json` and `data.yaml` (and the
      JSONL / YAML-multi variants), asserting mpq and datetimes
      (with timezone) survive both formats.
- [ ] [tests] Model invariants:
      - `setData` emits `dataChanged` covering cols 0..2 of the
        affected row
      - `removeRows` updates persistent indices correctly
      - `parent()` / `index()` round-trip on a 3-level tree
      - `change_type` `lossy=True` only when there were prior children
      - `unique_child_name` collision avoidance with a reserved-name
        set
- [ ] [tests] Theme snapshot + WCAG accessibility suites
      (`themes/_contrast.py` is already in place; nothing wires it
      into a test yet).
      - `tests/test_theme_snapshot.py` — deterministic built-in theme
        snapshots, partial-override coverage
      - `tests/test_theme_accessibility.py` — contrast regression
        coverage for built-in themes
- [ ] [tests] End-to-end smoke on a `MainWindow`: open → edit →
      Save → reopen → verify dirty marker cleared, recent-files
      populated.
- [ ] [tooling] Pin `pytest-qt` in `requirements.txt`.
- [ ] [tooling] Add a `make test` target running
      `QT_QPA_PLATFORM=offscreen pytest -q`.
- [ ] [tooling] Add `coverage` / `pytest-cov` and commit a short
      summary to `ai-memory/coverage.md`.
- [ ] [tooling] Add a `themes-check` `Makefile` target (lint built-in
      YAML against the schema once that exists).

## Theme / docs
- [ ] [docs] `themes/builtin/schema.md` covering YAML grammar, every
      `JsonType`, fallback semantics, icon path resolution, worked
      examples.
- [ ] [docs] README theming section with screenshots and the user
      theme directory location per OS
      (`QStandardPaths.AppConfigLocation/themes/*.yaml`).
- [ ] [ux] Watch user theme **icon asset folders** in addition to
      YAML files so custom SVG/PNG edits hot-reload without touching
      the YAML. — `app/theme_controller.py`

## UX polish
- [ ] [ux] Match-highlight delegate (`ValueDelegate.paint` override
      drawing a yellow background span over substring matches when
      a filter is active). — `delegates/value.py`

## Code hygiene (low priority)
- [ ] [hygiene] Drop the legacy `_demo_data()` seed and its
      `base64` / `gzip` / `zlib` / `gmpy2` imports from
      `documents/tab.py` once the remaining bare-`JsonTab(...)`
      tests migrate to explicit `data=` constructors.
- [ ] [hygiene] Decide whether to keep `header_view_editor.py`. The
      mixin is currently unused (commented out at the call site).
- [ ] [hygiene] Consider renaming the underscore-prefixed helpers
      that get re-imported across modules in `tree_actions/` so the
      cross-package public surface isn't named with a leading
      underscore (`_resolve_model`, `_to_source_index`, …).
- [ ] [hygiene] Simplify the multi-step Shiboken import fallback in
      `app/theme_controller.py` (`from PySide6.QtCore import Shiboken`
      → `import shiboken6` → `None`) once a single canonical import
      is chosen.

## Smells / footguns (very low priority, no functional impact)
- [ ] [smell] `JsonTreeItem.row()` returns `0` for the root (no
      parent) instead of `-1`; tolerable but a footgun for future
      code.
- [ ] [smell] `ValueDelegate.createEditor` raises `ValueError` for
      `OBJECT`, `ARRAY`, `NULL` (unreachable thanks to `flags()`); a
      defensive `return None` would degrade more gracefully.
- [ ] [smell] `state.view_state` persists expansion/current as
      positional `(int,…)` paths; structural mutations
      (sort/insert/paste) before a save→reload land on a different
      node. Consider keying by name where available.
- [ ] [smell] `JsonTab.save()` catches `Exception` broadly and
      reports via status bar; consider narrowing the catch and
      surfacing structured diagnostics for malformed datetime /
      bytes.

## Long-horizon wishlist

Captured here so future audits don't lose them. None of these are
specced or actively in progress — they're the original wishlist from
the repo root.

- [ ] [feature] Float/integer numeric **previews**: hex/oct/bin for
      integers; float16/float32/float64 representation preview
      (context menu).
- [ ] [feature] Multiline statistics: lines / words / runes (Unicode
      code points) on the multiline editor.
- [ ] [feature] Toggleable alphabet sort and custom array sort.
- [ ] [feature] Case transforms (Kebab / Snake / Camel / Caps) on
      file or selection.
- [ ] [feature] Configurable keymap via `settings.json`.
- [ ] [feature] `Ctrl+PgUp` / `Ctrl+PgDown` to switch between tabs.
