# JSON Editor — Pros & Cons

_Last analysis: **2026-05-17**. All previous plans (drag-and-drop
Steps 1–10 + jsonschema Steps 1–7) are merged on `master`
(`cb7cca8`). The active `schema-registry` branch is at `a2b1acb` and
has shipped Steps 1–7 of `plans/00-overview.md`: shared
`SchemaRegistry`, identity-tracked `SchemaSource(kind="file"|"url")`,
`QFileSystemWatcher`-driven hot reload, URL-backed schema sources, and
a persisted recent-schemas picker plus this docs/memory close-out._

_The six original `plans/` phases plus
the full drag-and-drop / multi-action plan (Steps 1–10 — multiselect
foundation, MIME helpers, atomic multi-row undo, keyboard multimove,
expansion preservation, native QTreeView drag-and-drop, drop policies,
shortcuts/menu, anchor-based move primitive, multi-action paste
semantics) have all shipped.  **Step 7 — YAML schema support,
multi-doc validation, schema picker UI, persistence, and sanitization
— has also shipped.**  Earlier Phases 0–6 plus the package
refactor remain green. Test surface: **906 collected** as of this
memory pass. The known offscreen failures are platform-specific
(Qt offscreen ignores `QStyleHints.setColorScheme`); they pass on real
platforms._

This document evaluates the **current** state of the editor across
the canonical package layout: `app/`, `documents/`, `tree/`,
`delegates/`, `tree_actions/`, `undo/`, `io_formats/`, `state/`,
`themes/`, `validation/`, `tree_filter_proxy.py`, `model_actions.py`,
`settings.py`.
See `repo-map.md` for the full module breakdown.

---

## ✅ Pros

### Architecture & design
- **Clean separation of concerns** — data (`tree/item.py`), model
  (`tree/model.py`), filter (`tree_filter_proxy.py`), view+actions
  (`documents/tab.py` + `tree_actions/`), editing (`delegates/`),
  shell (`app/`), persistence (`state/` + `io_formats/`), theming
  (`themes/` + `app/theme_controller.py`).
- **No source file outside the generated `mainwindow.py` exceeds
  ~580 lines.** `JsonTab` sits at ~580; `tree/item_coercion.py` at
  ~430; everything else is smaller.
- **Tabbed multi-document architecture** — each `JsonTab` owns its
  model, proxy, view, delegates, undo stack, search bar, font zoom,
  shortcuts, dirty state, and status callbacks.
- **Three-column schema** (`Name | Type | Value`) is well chosen:
  the inferred type is a first-class, editable concept.
- **Rich `JsonType` enum** — INTEGER, FLOAT, PERCENT, BOOLEAN,
  STRING, UNICODE, MULTILINE, TEXT, DATE, TIME, DATETIME,
  DATETIMEZONE, BYTES, ZLIB, GZIP, OBJECT, ARRAY, NULL. The editor
  is a *structured-data* editor, not just JSON.
- **Total, conservative type detection** — `parse_json_type` returns
  STRING with a logger warning for unknown types; short ambiguous
  strings stay STRING; datetime is checked before bytes; PERCENT is
  reachable via the `[0,1]` heuristic or explicit pinning.
- **Type pinning** (`JsonTreeItem.explicit_type`) — pasted base64-like
  or newline strings can be kept as plain STRING.
- **Exact numeric arithmetic** — `gmpy2.mpq` end-to-end via
  `QBigIntSpinBox` / `QMpqSpinBox`; no float precision loss in either
  storage or display.
- **Specialist modal editors** — `BetterDateTimeEditor`, `QHexDialog`,
  `QMultilineDialog`, all persisting UI state via `QSettings`.
- **Typed-command undo/redo** — every mutation pushes an
  O(affected-subset) typed `QUndoCommand`. Path-based addressing
  sidesteps `QModelIndex` invalidation. Surgical Qt-signal replay
  via `DiffApplier` keeps view expansion and selection through
  undo/redo.
- **`mergeWith` collapsing** — `_RenameCmd` / `_EditValueCmd` collapse
  same-path edits within a 500 ms window into a single undo step.
- **History dialog** — `QUndoView` bound to the active tab's stack.

### UX / functional features
- **Multi-format file I/O** — JSON, JSONL/NDJSON, YAML, YAML
  multi-document; atomic writes via `os.replace`; `mpq2py` round-trip
  preserves exact rationals across all formats.
- **Recent files** — 8-entry persisted menu, missing-file pruning.
- **Close-confirm** — Save / Discard / Cancel; close all tabs on
  window close.
- **Recursive name+value filter** — debounced 150 ms via `QTimer`,
  Ctrl+F focus, ancestors of matches stay visible.
- **Per-file persisted view state** — column widths, expansion,
  current selection, font zoom, with safe coercion across QSettings
  shapes and a 5000-entry expansion cap.
- **Permanent breadcrumb** — `$.foo.bar[2].baz  (string, 24 chars)`
  plus transient action messages.
- **Type-aware presentation** — PERCENT → `50%`, BYTES family →
  `<24 byte>`, mpq → exact decimal, long strings elide at 80 chars,
  long values get a 4 KB `ToolTipRole`.
- **Container preview** (Phase 4) — `[N items] v1, v2, …` /
  `{N keys} k: v, …` (first 5 children) when the row is collapsed;
  preview disappears on expand so it doesn't duplicate visible data.
- **Column-aware context menu** (Phase 1) — type column shows only
  Expand/Collapse; name col uses `copy_selection_with_name`, value
  col uses `copy_selection_value_only`, otherwise full
  `copy_selection`.
- **Smart kind-switch coercion** (Phase 3) —
  - bool → str produces lowercase `"true"`/`"false"`
  - DATE/TIME/DATETIME/DATETIMEZONE fall back to `"now"` (correct
    timezone, sensible precision) instead of the 1970 epoch zero
  - integer seconds/milliseconds ↔ DATETIME round-trip
  - BYTES/ZLIB/GZIP encode-on-switch from text or int; cross-format
    re-encode is lossless when `old_type` is provided
  - ARRAY ↔ OBJECT preserves children with `item1, item2, …` keys on
    array→object and ordered drop on object→array
  - friendly `tree/stubs.py` placeholders (random pick of "famous"
    integers / floats / phrases / multiline / file-magic bytes) for
    unrecoverable cases — better than blank `0` / `""`
- **Zoom that respects user-resized columns** (Phase 2) — font zoom
  no longer overwrites column widths the user dragged; tracked via
  `_user_sized_columns` + `_programmatic_column_resize` guard.
- **App-level color-scheme sync** (Phase 5) —
  `ThemeController._sync_app_color_scheme` calls
  `QStyleHints.setColorScheme(Light/Dark)` whenever a theme is
  applied, so menus / dialogs / toolbars match the active theme's
  mode without any custom stylesheet (per-type cell colouring stays
  in delegates).
- **Native drag-and-drop with multi-selection** (Steps 1–10) —
  mouse-driven move/copy of any selection between OBJECT/ARRAY
  containers; Ctrl-drag = copy, plain drag = move; `JsonTreeView`
  overrides `startDrag` so the model fully owns internal moves and
  Qt's default `clearOrRemove` doesn't delete the freshly-placed
  destination rows; drop-on-leaf becomes sibling-after; self-into-
  descendant cycles are rejected via the MIME `source_paths`
  envelope; transient status feedback (`"Moved N rows under $.foo"`).
- **Anchor-based move primitive** (Step 9) — every move caller
  (`Alt+Up/Down`, `Ctrl+Alt+Up/Down` move-out, drag-drop,
  duplicate/paste cleanup) now feeds a single `MoveAnchor` into
  `JsonTab.push_move_rows_anchor`. The three pre-existing branches
  (same-parent, common-grandparent, multi-parent fallback) and their
  four overlapping `target_row` formulas were collapsed into one
  helper, removing a whole class of off-by-one bugs.
- **Multi-action paste semantics** (Step 10) — `Ctrl+V` routes
  through `paste_auto` (single ⇒ legacy paste, multi-selection ⇒
  `paste_clones_at_targets`, every selected row receives a clone of
  the entire clipboard payload). `Ctrl+Shift+V` is
  `paste_insert_after_zip` (zip-pair clipboard top-level entries
  with top-level selected targets, insert as sibling-after each
  target). `Ctrl+Alt+V` is `paste_replace_zip` (same pairing,
  in-place value replace).
- **Keyboard multimove with bubble-out** (Steps 3–4) —
  `Alt+Up/Down` move any selection by one row, including disjoint
  multi-selections under `SelectItems`; at the parent boundary the
  selection promotes/demotes across the parent.
  `Ctrl+Alt+Up/Down` is a one-shot promote-out-of-parent.
  `_select_placed_rows` keeps the multi-selection highlighted
  through both redo and undo.
- **Expansion preservation across moves** (Step 5) — moved
  subtrees keep their open/closed state at the destination, and
  redo/undo restores the same shape. Current index and selection
  follow the moved rows.

### Theming stack
- **Self-contained `themes/` package** — immutable, hashable
  `ThemeSpec` / `Palette` / `TypeStyle` dataclasses; YAML loading
  with total fallback semantics; built-in light/dark; user-folder
  overrides; opt-in `QFileSystemWatcher` hot reload (250 ms debounce).
- **`themes/_contrast.py`** — WCAG `relative_luminance` and
  `contrast_ratio` helpers, ready for accessibility checks.
- **Type icons fully wired** — `FileIconProvider` resolves
  `<key>.svg/.png/.ico` from theme search paths, caches per-`JsonType`,
  warns once per missing asset, supports `reload()`. The model serves
  `DecorationRole` on the Type column; the type combobox reuses the
  same provider.
- **Live theme switching** — open tabs keep undo history, expansion,
  and current selection; `JsonTab.set_theme` repaints in place.
- **Follow-system support** — reacts to
  `QGuiApplication.styleHints().colorSchemeChanged` and chooses the
  per-mode preferred theme, with `ThemeController.shutdown()`
  disconnecting cleanly to avoid stale-signal crashes after window
  close.

### Validation
- **Schema validation** (Step 7) — JSON Schema validation via optional
  `jsonschema-rs`; schema auto-detection (inline `$schema`, sibling
  `.schema.json`); YAML schemas load via the same `load_file_with_format`
  path; per-file schema binding persisted via `QSettings` sha1-keyed path
  and restored on reopen; `mpq`/`Decimal`/`datetime`/`bytes` sanitized
  to jsonschema-rs primitives in `validation._sanitize` (validation-only,
  never stored); YAML multi-doc validates each document independently with
  `[doc N]` prefix in `instance_path`; **manual schema picker UI** in
  the ValidationDock toolbar (Attach / Reload / Open / Clear); "Clear
  schema" also wipes the persisted binding; "Save As" to a new path
  also clears the old binding.
- **Centralised schema ownership** — one `SchemaEntry` per source
  shared across all bound tabs, with `QFileSystemWatcher`-driven
  hot reload for local files and a normalised URL identity for
  remote schemas. `state.recent_schemas` (cap 12) backs the dock's
  "Recent ▸" picker.
- **Schema source navigation is identity-based** — `SchemaTabPool`
  reuses an already-open schema tab for the same local path or URL;
  URL schemas open as read-only materialised tabs for rule navigation
  and as browser URLs from the dock's open action.

- **CapsLock-safe inline editing** — `_TextEditorDelegateBase` and
  `_CapsLockSafeLineEdit` swallow lock-key key events and
  layout-switch focus changes so xkb layout-switch keybinds don't
  collapse the editor mid-typing.
- **Dialog edits survive row mutations** — multiline / hex dialog
  callbacks capture `QPersistentModelIndex` and commit via
  `JsonTab.commit_set_data`, so the modal session never targets a
  stale row.
- **Decode failures degrade gracefully** —
  `(ValueError, OSError, zlib.error, binascii.Error)` are caught and
  surfaced through the status-bar callback; `flags()` keys
  editability off `JsonTreeItem.editable` so malformed binary stays
  non-editable rather than crashing on every paint.
- **Synthetic root row** — `JsonTreeModel.show_root` lets the user
  edit the root container without breaking legacy fixtures
  (`show_root=False`).
- **Substantial test coverage** — 906 tests collected; the new Phase 1–5
  surfaces are covered by `test_kind_switch_coercion.py`,
  `test_container_preview.py`, `test_app_color_scheme.py`, the
  existing 50-test theming surface, and the Phase-5 broader UX
  suites. The drag-and-drop sweep adds another **11 dedicated
  suites** (`test_multiselect_foundation`, `test_mime_payload`,
  `test_undo_multimove`, `test_keyboard_multimove[_app_mode]`,
  `test_move_preserves_expansion`, `test_drag_drop_internal`,
  `test_drag_drop_matrix`, `test_drag_drop_property`,
  `test_drop_policies`, `test_anchor_move`,
  `test_multi_action_semantics`, `test_context_menu_multiselect`).
  **Step 7 validation suites** add 3 dedicated test files:
  `test_validation_yaml` (7), `test_validation_yaml_multi` (11),
  `test_validation_persistence` (10). Schema-registry follow-up suites
  cover registry dedup/reload/watch behaviour, tab sharing,
  recent-schemas persistence, attach-dialog parsing, dock Recent UI,
  and the top-level Schemas menu.
- **Reusable widget stack** — `qhexedit`, `qmultiline_editor`,
  `datetime_editor`, `qbigint_spinbox`, `qmpq_spinbox` are
  independently useful packages.

### Code quality
- Modern Python (3.12+ `match`/`case`, `StrEnum`, type hints across
  most modules).
- `Makefile lint` enforces formatting (`autoflake`, `isort`, `black`).
- `pytest.ini` sets `pythonpath = .` for consistent runs.
- **No `TODO` / `FIXME` / `XXX` / `HACK` markers in production
  code.**

---

## ❌ Cons

### Active issues
- **3 failing tests under `QT_QPA_PLATFORM=offscreen`** —
  `tests/test_app_color_scheme.py::test_light_theme_sets_light_color_scheme`,
  `tests/test_app_color_scheme.py::test_dark_theme_sets_dark_color_scheme`,
  `tests/test_theme_switching.py::test_color_scheme_follows_selected_theme`.
  Root cause: Qt offscreen QPA ignores
  `QStyleHints.setColorScheme` and reports `Qt.ColorScheme.Unknown`.
  These tests should either skip on the offscreen platform or
  monkey-patch `setColorScheme`. Code is correct on real platforms.

### Schema validation follow-ups
- **URL schema staleness** — URL-backed schema `reload()` always
  re-fetches; no `ETag` / `If-Modified-Since` conditional request is
  persisted or sent yet.
- **No content-hash dedup for embedded inline schemas** — source
  identity deduplicates file paths and URLs. Literal inline schema
  bodies embedded in documents are still not coalesced by hash.

### Drag-and-drop caveats (low priority)
- `drag-n-drop.patch` is still committed at repo root as an
  ~328 kB historical archive of the full Step 1–10 work. Harmless,
  but could be removed once the plan is officially closed.
- `state.view_state` still persists expanded paths as positional
  `(int,…)` tuples; drag-drop reorders survive within the session
  thanks to Step 5 (in-memory snapshot+replay), but a save→reload
  on a moved subtree can still land on a different node.
  Mitigation is the same as before — key by name where available.

### Test / tooling gaps
- **Full delegate matrix** is still missing
  (`tests/test_value_delegate.py`): editor type per JsonType,
  `setEditorData` / `setModelData` round-trips for INTEGER, mpq
  FLOAT/PERCENT, BOOLEAN, DATE/TIME/DATETIME/DATETIMEZONE,
  STRING/UNICODE; dispatch-by-widget-class survives stale editors;
  dialog-based delegates (MULTILINE/TEXT/BYTES/ZLIB/GZIP) commit
  through `QPersistentModelIndex` + `commit_set_data`.
- **Round-trip property tests** for `data.json` / `data.yaml` —
  load → mutate → save → reload equality, with mpq + datetime + tz
  preservation across all four formats.
- **Model invariants**: `setData` emits `dataChanged` for the full
  row (cols 0..2), `removeRows` updates persistent indices, 3-level
  `parent()` / `index()` round-trip, `change_type` `lossy=True` only
  with prior children, `unique_child_name` collision avoidance with
  reserved-name set.
- **`pytest-qt`** is still not pinned in `requirements.txt`, even
  though theme tests use `qtbot`.
- **No `make test`** target; no `coverage.md` snapshot; no
  `themes-check` target.

### Theme / UX caveats
- **Hot reload watches user YAML files, not icon asset folders** —
  editing a custom SVG/PNG under a user theme directory will not be
  noticed unless the YAML changes or the user triggers a manual
  reload.
- **No match-highlight delegate** — `ValueDelegate.paint` overlay on
  filter matches is still optional/unimplemented.
- **No theme docs / contributor tooling** — no
  `themes/builtin/schema.md` covering YAML grammar, fallback
  semantics, icon path resolution, worked examples; no README
  theming section/screenshots; no theme snapshot or accessibility
  suites yet (despite `themes/_contrast.py` being ready).

### Tree/model semantic smells (low priority)
- `JsonTreeItem.row()` returns `0` for the root rather than
  signalling "no parent"; works but is a footgun.
- `ValueDelegate.createEditor` raises `ValueError` for unsupported
  `json_type` (`OBJECT`, `ARRAY`, `NULL`); these branches *should*
  be unreachable thanks to `flags()`, but a defensive `return None`
  would degrade more gracefully.
- `MainWindow.update_actions` enables `Save` whenever a tab exists;
  could be tightened to `tab.is_dirty` only, but matches the
  expectation of "Save anyway".

### Persistence / I/O remaining risks
- JSON load path cannot use `simplejson.load(..., use_decimal=True)`
  together with `parse_float=mpq` on the pinned `simplejson`; the
  compatible path is `parse_float=mpq` only. Save still uses
  `use_decimal=True`.
- Save-time validation is best-effort: malformed datetimes / bytes
  surface as Python exceptions caught generically in
  `documents/tab_io.py`. No structured user-facing diagnostics.
- `state.view_state` persists expanded paths as positional-only
  `(int,…)` tuples. After a structural mutation that reorders rows
  (sort, insert, paste), restoring to the same path can land on a
  different node. Acceptable trade-off given persistence is keyed
  per-file on close.

### Code hygiene
- `_demo_data()` with its `base64` / `gzip` / `zlib` / `gmpy2`
  imports remains in `documents/tab.py` for legacy
  bare-`JsonTab(...)` test paths. Removable once those tests
  migrate to explicit `data=` constructors.
- `header_view_editor.py` is dormant code (commented out at the call
  site) — keep or delete decision pending.
- `tree_actions/structure.py` and `tree_actions/clipboard.py` use
  underscore-prefixed names imported from sibling modules
  (`_resolve_model`, `_to_source_index`, …). Works, but the
  underscore convention is mildly misleading at package scope.
- `ThemeController` has multiple Shiboken-import fallbacks
  (`Shiboken` / `shiboken6` / `None`) for `_is_valid` — robust but
  worth simplifying once a single import path is settled.

---

## TL;DR

The editor is **functionally complete for daily use**:

- Multi-document file I/O across JSON / JSONL / YAML / YAML-multi.
- Typed undo/redo with merge collapsing and a History dialog.
- Persistent per-file layout (column widths, expansion, selection,
  font zoom) and a recent-files menu.
- Recursive search/filter with debounced input.
- Type-aware presentation (PERCENT, mpq, bytes-family,
  multiline-as-joined-preview, container preview when collapsed)
  plus full-text tooltips on long values.
- Column-aware context menu and smart kind-switch coercion that no
  longer drops user data on type changes.
- Zoom that preserves user-resized column widths.
- A breadcrumb-driven status bar with transient action feedback.
- App-global theme loading, live switching, per-type colors+fonts,
  bundled type icons, follow-system mode, opt-in hot reload, and
  app-level `Qt.ColorScheme` sync so menus / dialogs match the
  active theme.
- Multi-selection (`Shift+Click` contiguous, `Ctrl+Click` disjoint)
  with full copy/cut/paste/duplicate/delete coverage; multi-action
  paste dispatchers (`paste_auto`, `paste_insert_after_zip`,
  `paste_replace_zip`); keyboard multimove with parent-boundary
  bubble-out and one-shot promote-out (`Ctrl+Alt+Up/Down`); and
  full native QTreeView drag-and-drop with cycle guard, leaf
  fallback, copy modifier, indicator visuals and transient status
  feedback — all backed by a single anchor-based move primitive
  and a single undo step per move.

Outstanding work is contributor-facing rather than user-facing:
broader QA (full delegate matrix, round-trip property tests,
accessibility/theme-snapshot suites), tooling (`pytest-qt` pin,
`make test`, coverage snapshot), docs (theme schema, README theming
section, screenshots), and a small UX polish backlog (match
highlighting, watching icon-asset folders, narrowing
`MainWindow.update_actions`, fixing the offscreen-platform color
scheme tests).
