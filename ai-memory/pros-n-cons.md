# JSON Editor — Pros & Cons

_Last analysis: 2026-05-06. Phases 0–6 are shipped, including the
theming stack (loader → registry → delegate coloring → icon provider →
live theme switching) and a follow-up Phase-6 refactor that extracted
`app/theme_controller.py`. The package refactor (Phases 01–37) remains
complete and all old top-level "god modules" stay removed. The last
recorded full-suite baseline in memory is still **401 passed**
(`2026-04-26`), while the current tree now **collects 451 tests** and
the dedicated theming surface (**50 tests**) passes under
`QT_QPA_PLATFORM=offscreen pytest -q`._

This document evaluates the **current** state of the JSON tree editor
implementation across the canonical package layout: `main.py`, `app/`,
`documents/`, `undo/`, `tree/`, `delegates/`, `tree_actions/`,
`io_formats/`, `state/`, `tree_filter_proxy.py`, `model_actions.py`,
`settings.py`. See `repo-map.md` for the full module breakdown.

## ✅ Pros

### Architecture & design
- **Clean separation of concerns** — data layer (`tree/item.py`),
  model layer (`tree/model.py`), filter layer (`tree_filter_proxy.py`),
  view + action layer (`documents/tab.py` + `tree_actions/`),
  editing layer (`delegates/`), shell layer (`app/`), persistence
  (`state/` + `io_formats/`).
- **Package refactor delivered** — no source file (other than
  generated `mainwindow.py`) exceeds ~540 lines; `JsonTab` shrank from
  ~1050 to ~540 lines; `tree_view.py`/`delegate.py`/`json_tab.py`/`ui.py`
  monolith files were split into focused packages with narrow public
  APIs.
- **Tabbed multi-document architecture** — each `JsonTab` owns its
  model, proxy, view, delegates, undo stack, search bar, font zoom,
  shortcuts, dirty state, and status callbacks.
- **Three-column schema** (`Name | Type | Value`) is well chosen for
  JSON: the inferred type is a first-class, editable concept.
- **Rich type system** — `JsonType` enum covers integer, float,
  percent, boolean, string, unicode, multiline, text, date, time,
  datetime (+ tz), bytes, zlib, gzip, object, array, null. The editor
  is positioned as a *structured-data* editor, not just JSON.
- **Total, conservative type detection** — `parse_json_type` returns
  `STRING` with a logger warning for unknown values; short ambiguous
  strings stay `STRING`; datetime is checked before bytes; PERCENT is
  reachable via `[0,1]` numeric heuristic or explicit pinning.
- **Type pinning** (`JsonTreeItem.explicit_type`) — pasted base64-like
  or newline strings can be kept as plain `STRING`.
- **Exact numeric arithmetic** — `gmpy2.mpq` end-to-end via
  `QBigIntSpinBox` / `QMpqSpinBox`; no float precision loss in either
  storage or display.
- **Specialist modal editors** — `BetterDateTimeEditor`, `QHexDialog`,
  `QMultilineDialog`. All persist UI settings via `QSettings`.
- **Typed-command undo/redo** — every mutation pushes an
  O(affected-subset) typed `QUndoCommand`. Path-based addressing
  sidesteps `QModelIndex` invalidation. Surgical Qt-signal replay
  keeps view expansion and selection through undo/redo.
- **`mergeWith` collapsing** — `_RenameCmd` / `_EditValueCmd` collapse
  same-path edits within a 500 ms window into a single user-visible
  undo step.
- **History dialog** — `MainWindow._show_history_dialog` exposes the
  active tab's `QUndoStack` via `QUndoView`.
- **Begin/End signals as context managers** — `rows_insertion`,
  `rows_removal` make Qt model bookkeeping exception-safe.
- **Cached editability** — `JsonTreeItem.editable` is recomputed only
  on construction or `_apply_typed_value`, so `flags()` stays O(1).
  Malformed binary payloads silently degrade to non-editable instead
  of raising on every paint.
- **Phase 4 file I/O is complete** — JSON, JSON Lines, YAML, and YAML
  multi-document with `mpq2py` round-trip, atomic writes, dirty-state
  via `undo_stack.cleanChanged`, `*` tab marker, close-confirm,
  recent-files menu (8 entries, persisted, missing-file pruning).
- **Phase 5 UX is complete**:
  - Recursive name/value `TreeFilterProxy` with debounced (`QTimer`
    150 ms) search bar and Ctrl+F focus.
  - Per-file persisted `QSettings` view state: column widths,
    expansion, current selection, font zoom, with safe coercion for
    cross-platform `QSettings` shapes and a 5000-entry expansion cap.
  - Permanent breadcrumb on selection
    (`$.foo.bar[2].baz  (string, 24 chars)`) plus transient action
    messages.
  - `ValueDelegate.initStyleOption` does type-aware presentation
    (PERCENT → `50%`, BYTES family → `<24 byte>`, mpq → decimal, long
    strings elide to 80 chars). `EditRole` keeps raw values for
    editors; `ToolTipRole` gives full text up to 4 KB.
  - Expand All / Collapse All in both the tree context menu and the
    View menu; Ctrl+= / Ctrl+- / Ctrl+0 zoom shortcuts persist with
    view state.
- **Phase 1–6 theming shipped cleanly**:
  - `themes/` is now a self-contained package with immutable,
    hashable `ThemeSpec` / `Palette` / `TypeStyle` dataclasses,
    YAML loading with total fallback semantics, built-in light/dark
    themes, and a `ThemeRegistry` that merges built-in and user
    themes.
  - `state/theme_settings.py` persists follow-system mode, per-mode
    preferred theme names, a manual override, and the opt-in file
    watcher flag.
  - `ValueDelegate` and `JsonTypeDelegate` are theme-aware:
    per-`JsonType` foreground/font styling is applied without
    polluting model roles, and selection highlight still wins.
  - Type icons are fully wired: `FileIconProvider` resolves SVG/PNG/ICO
    assets from theme search paths, `JsonTreeModel` serves
    `DecorationRole` on the Type column, and the type combobox reuses
    the same provider.
  - Theme switching is live and non-destructive: open tabs keep undo
    history, expansion, and current selection while `JsonTab.set_theme`
    repaints in place.
  - The Phase-6 refactor extracted `ThemeController`, pulling menu
    building, follow-system logic, persistence, hot reload and watcher
    plumbing out of `MainWindow` into a cohesive helper.
- **Built-in theme assets are shipped** — `themes/builtin/` now carries
  `light.yaml`, `dark.yaml`, and a bundled monochrome SVG icon set used
  by both defaults.
- **CapsLock-safe inline editing** — `_TextEditorDelegateBase` and
  `_CapsLockSafeLineEdit` swallow lock-key key events and
  layout-switch focus changes so xkb layout-switch keybinds don't
  collapse the editor mid-typing.
- **Dialog edits route through typed undo** — multiline / hex dialog
  callbacks capture `QPersistentModelIndex` and commit via
  `JsonTab.commit_set_data`, surviving row mutations during the modal
  session.
- **Synthetic root row** — `JsonTreeModel.show_root` lets the user
  edit the root container in the app while keeping the existing
  test fixtures (which use `show_root=False`) green.
- **Substantial test coverage** — the old 401-test baseline is now
  supplemented by a 50-test theming surface:
  `test_theme_loader.py`, `test_theme_registry.py`,
  `test_icon_provider.py`, `test_value_delegate_theme.py`,
  `test_icons_in_view.py`, and `test_theme_switching.py`.
- **Reusable widget stack** — `qhexedit`, `qmultiline_editor`,
  `datetime_editor`, `qbigint_spinbox`, `qmpq_spinbox` are
  independently useful packages.

### Code quality
- Modern Python (3.12+ `match`/`case`, `StrEnum`, type hints across
  most modules).
- `Makefile` enforces formatting (`black`, `isort`, `autoflake`).
- `pytest.ini` sets `pythonpath = .` for consistent runs.
- Phase 0 stripped embedded C++ docstrings and unused imports from the
  ported core.
- No stray `TODO` / `FIXME` / `XXX` / `HACK` markers in production
  code.

---

## ❌ Cons

### Remaining test / tooling gaps
- **Full delegate matrix** is still missing
  (`tests/test_value_delegate.py`): editor type per JsonType,
  `setEditorData` / `setModelData` round-trips for integers, mpq,
  booleans, datetimes, dispatch-by-widget-class survives stale editors,
  dialog-based delegates committing through `QPersistentModelIndex`
  + `commit_set_data`.
- **Round-trip property tests** for `data.json` / `data.yaml` —
  load → mutate → save → reload equality, with mpq + datetime + tz
  preservation across both formats and the JSONL / YAML-multi
  variants. Current `test_file_io_phase4.py` is smoke-level.
- **Model invariants**: `setData` emits `dataChanged` for the full
  row (cols 0..2), `removeRows` updates persistent indices, 3-level
  `parent()` / `index()` round-trip, `change_type` lossy=True only
  with prior children, `_unique_child_name` collision avoidance with
  reserved-name set.
- **`pytest-qt`** is still not pinned in `requirements.txt`, even
  though newer theme-switching tests use `qtbot`.
- **`make test`** / `themes-check` targets and a `coverage.md`
  snapshot have not landed.

### Theme / UX caveats
- **Theme switching is content-scoped, not full-app chrome scoped** —
  the tree content, type column and icons update live, but the code does
  not currently install a full `QPalette` / stylesheet for menus,
  toolbars and dialogs.
- **Hot reload watches user YAML files, not icon asset folders** —
  editing a custom SVG/PNG under a user theme directory will not be
  noticed unless the YAML changes or the user triggers a manual reload.
- **Match-highlight delegate** — `ValueDelegate.paint` overlay on
  filter matches. Tracked as optional in `phase-5.5-search-filter.md`.
- **Phase 7 docs/tests remain open** — no `themes/builtin/schema.md`,
  no README theming section/screenshots, and no theme snapshot or
  accessibility suites yet.

### Tree/model semantic smells (low priority)
- `JsonTreeItem.row()` returns `0` for the root rather than signalling
  "no parent"; works but is a footgun.
- `ValueDelegate.createEditor` raises `ValueError` for truly
  unsupported `json_type` (`OBJECT`, `ARRAY`, `NULL`); these branches
  *should* be unreachable thanks to `flags()`, but a defensive
  `return None` would degrade more gracefully.
- `MainWindow.update_actions` enables `Save` whenever a tab exists;
  could be tightened to `tab.is_dirty` only, but matches the user
  expectation of "Save anyway".

### Persistence / I/O remaining risks
- JSON load path cannot use `simplejson.load(..., use_decimal=True)`
  together with `parse_float=mpq` on the pinned `simplejson`; the
  compatible path is `parse_float=mpq` only. Save still uses
  `use_decimal=True`.
- `simplejson` is now pinned, but `pytest-qt` still is not.
- Save-time validation is best-effort: malformed datetimes / bytes
  surface as Python exceptions caught generically in
  `documents/tab_io.py`. No structured user-facing diagnostics.
- `state.view_state` persists expanded paths as positional-only
  `(int,…)` tuples. After a structural mutation that reorders rows
  (sort, insert, paste), restoring to the same path can land on a
  different node. Acceptable trade-off given persistence is keyed
  per-file on close.

### Code hygiene
- `_demo_data()` and its base64 / gzip / zlib / gmpy2 imports remain
  in `documents/tab.py` purely for legacy bare-`JsonTab(...)` test
  paths. Removable once those tests migrate to explicit `data=`
  constructors.
- `header_view_editor.py` is dormant code (commented out at the call
  site) — keep or delete decision pending.

---

## TL;DR

The editor is **functionally complete for daily use**:

- Multi-document file I/O across JSON / JSONL / YAML / YAML-multi.
- Typed undo/redo with merge collapsing and a history dialog.
- Persistent per-file layout (column widths, expansion, selection,
  font zoom) and a recent-files menu.
- Recursive search/filter with debounced input.
- Type-aware presentation (PERCENT, mpq, bytes-family) plus
  full-text tooltips on long values.
- A breadcrumb-driven status bar with transient action feedback.
- App-global theme loading, live switching, per-type colors, bundled
  type icons, follow-system mode, and opt-in hot reload of user theme
  YAML files.
- The theming surface is verified by 50 passing targeted tests, and the
  repository currently collects 451 tests overall.

Outstanding work has shifted from Phase 6 into **Phase 7 polish**
(theme docs, snapshots, accessibility checks, contributor tooling),
plus a few broader QA and UX items (full delegate matrix,
round-trip/property tests, match highlighting, full-app palette
application). The codebase is structurally clean enough that those can
ship as targeted PRs without further restructuring.
