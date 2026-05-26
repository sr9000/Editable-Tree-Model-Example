# TODO & FIXME

_Last updated: **2026-05-26** (branch `file-ux`; reload/close-reopen,
YAML clipboard, search-aware Go To, hide-inactive context menu,
field-case tokenizer fix, undo collision-rename fix)._

Tracks **missing/incomplete features** (TODO) and **bugs/issues**
(FIXME) discovered while auditing the editor codebase.
Cross-reference with `pros-n-cons.md` and `repo-map.md` for context.
The archived "Resolved (kept for posterity)" changelog has been
moved to [`history.md`](history.md) — see the pointer at the bottom.

Format: `- [ ] [scope] description — file:symbol`

> **`file-ux` branch — closed items (2026-05-26):**
> - [x] [ux] **Reload from Disk** action (`Ctrl+R`) with dirty-conflict
>       dialog (Discard / Overwrite / Cancel).
> - [x] [ux] **Close Tab** (`Ctrl+W`) and **Reopen Closed Tab**
>       (`Ctrl+Shift+T`), LIFO stack capped at 10; discard-on-close
>       reopens from disk; empty untitled tabs close without prompt.
> - [x] [ux] **New From Clipboard** (`Ctrl+Space`) accepts JSON or
>       YAML (single + multi-doc); rejects bare scalars.
> - [x] [ux] **Copy as YAML text** toggle (File menu); persisted via
>       `state/clipboard_settings.py`.
> - [x] [ux] **YAML interop on paste** — `entries_from_mime` accepts
>       YAML dict/list payloads after JSON parsing fails.
> - [x] [ux] Context menu **hides** disabled actions instead of
>       greying them; type column shows no menu.
> - [x] [ux] **Expand / Collapse Recursively** scoped to selected
>       subtree (root selection = whole document).
> - [x] [ux] **Go To** context-menu action while filter is active —
>       clears search and focuses the clicked cell.
> - [x] [ux] Tighten `update_actions`: `Save` enabled only when
>       `tab.is_dirty`; menus refreshed via `aboutToShow`.
> - [x] [ux] Tab tooltip shows the full file path.
> - [x] [bug] Field-case switch preserves non-standard punctuation
>       (`.`, `:`) and supports Unicode letters; digit/letter
>       boundaries handled (`tree_actions/field_case.py` tokenizer
>       rewrite).
> - [x] [bug] Cross-parent move undo restored the auto-renamed source
>       name on collision; `_MoveRowsCmd` now snapshots
>       `source_names` and restores them on undo.

> **`new-kinds` branch — closed items:**
> - [x] [feature] UTC datetime kind (`JsonType.DATETIMEUTC`) with
>       trailing `Z`; full conversion lattice across the date/time
>       family in `tree/types_datetime.py::convert_datetime`
>       (real tz-shift on `DATETIMEZONE → DATETIMEUTC`); editor
>       extensions in `datetime_editor/{enums,regex,validator,
>       better_dt_editor}.py`. Plan: `plans/01-utc-datetime.md`.
> - [x] [feature] Number-affix kinds (`INTEGER_CURRENCY`,
>       `INTEGER_UNITS`, `FLOAT_CURRENCY`, `FLOAT_UNITS`).
>       Structured `NumberAffix(kind, affix, space, number)` storage
>       in `units/number_affix.py`; `AffixCompositeEditor` in
>       `delegates/number_affix_delegate.py`; per-tab MRU
>       `state/affix_mru.py`; round-trip in
>       `io_formats/{dump,load}.py`. Plan: `plans/02-number-affix.md`.
> - [x] [feature] Secret strings (`SECRET_LINE` / `SECRET_TEXT`).
>       Word-prefix name detection in `validation/secret_names.py`;
>       runtime-configurable prefix list in `state/secret_settings.py`
>       backed by **File ▸ Secret word prefixes…**
>       (`dialogs/secret_prefixes_dlg.py`); sticky promotion in
>       `tree/item.py::_promote_secret_from_name`; masked rendering +
>       fixed glyph count in `delegates/value_formatting.py`;
>       masked editors with reveal toggle and focus-out auto-hide in
>       `delegates/value.py` + `qmultiline_editor.py` (sensitive
>       mode). Plan: `plans/03-secret-strings.md`.
> - [x] [ux] Pseudo text family (`EMPTY_STRING`, `EMPTY_MULTILINE`,
>       `WS_STRING`, `WS_UNICODE`, `WS_MULTILINE`, `WS_TEXT`)
>       surfaces empty / whitespace-only string values as
>       previewable type chips; excluded from `USER_SELECTABLE_TYPES`;
>       `PSEUDO_TEXT_PARENT` / `canonical_text_type` map back to the
>       editable parent.

> **PR #9 `improve-ux` — closed items (now on `master`):**
> - [x] [ux] Window geometry / maximized / fullscreen mode persisted
>       across sessions (`app/main_window.py::_restore_window_geometry`,
>       `show_with_restored_mode`, `closeEvent`).
> - [x] [ux] Drop one or more local files onto the main window to
>       open each as a tab (`dragEnterEvent` / `dropEvent` +
>       `_local_paths_from_mime`).
> - [x] [ux] Base64 cells gain **Attach from…** and **Save as…**
>       context-menu actions
>       (`tree_actions/context_menu.py::attach_base64_from_file`,
>       `save_base64_as_file`).
> - [x] [ux] Configurable Edit Warning Limits (File ▸ submenu;
>       `state/edit_limits.py`); editors confirm before opening large
>       strings, multiline blobs, or binary payloads.
> - [x] [validation] Remove `ValidationIssue.severity` and the
>       severity map from `IssueIndex`; downstream UI now reports a
>       single "Validation: N issue(s)" count.
> - [x] [ui] Compact K/M/B counts via `units.counts()` in
>       breadcrumb, validation summary, hex dialog, and limit labels.

> **Schema-registry plan (branch `schema-registry`, now merged)** —
> Steps 1–7 of `plans/00-overview.md` are on `master`:
> shared `SchemaEntry` per `SchemaSource`,
> `QFileSystemWatcher`-driven hot reload for local schemas, URL
> source identity, extracted attach dialog, schema-tab pooling,
> persisted recent schemas, and the docs/memory close-out.

## Schema-registry plan — closed items

- [x] [validation] **Shared schema instance across tabs.**
      `documents/tab.py::set_schema` now delegates to
      `SchemaSource.from_ref` + `schema_registry.acquire`, and tabs
      bound to the same source share `SchemaEntry.inline`.
- [x] [validation] **Schema loads are deduplicated.**
      `validation/schema_registry.py::SchemaRegistry.acquire` loads a
      source once, tracks bound tabs / `ref_count`, and releases the
      entry when the last tab closes.
- [x] [validation] **Local schema file edits hot-reload.**
      `SchemaRegistry` owns a `QFileSystemWatcher`; changed local
      schemas reload in place and emit `schemaReloaded`, causing bound
      tabs to revalidate.
- [x] [validation] **Recent schemas list.**
      `state/recent_schemas.py` persists a cap-12 MRU list and the
      attach dialog plus Validation dock expose recent pickers.
- [x] [validation, cleanup] **Typed URL identity.**
      URL-backed schemas use `SchemaSource(kind="url", key=...)`,
      `JsonTab.schema_source`, and `SchemaTabPool`; no free-floating
      `_schema_url_source` attribute remains.
- [x] [validation, cleanup] **Attach dialog extracted.**
      `dialogs/attach_schema_dlg.py::AttachSchemaDialog` handles file
      paths, URLs, and recent-source selection outside `MainWindow`.

> **Status (2026-05-16)** — All historical phases (0–6 + package
> refactor + the six former-`plans/` phases on context-menu polish,
> zoom-column preservation, kind-switch coercion, container preview,
> app-color-scheme theming, and tests/memory) are shipped, **and** the
> drag-and-drop / multi-action plan (Steps 1–10 under `plans/`) is now
> complete: multiselect foundation, MIME helpers, atomic multi-row
> undo move, keyboard Alt±Up/Down with parent-boundary bubble-out,
> Ctrl+Alt+Up/Down move-out, expansion preservation across moves,
> native QTreeView drag-and-drop (with `JsonTreeView.startDrag`
> override so the model fully owns internal moves), drop policies +
> cycle guards, the anchor-based move primitive (`tree_actions/anchors.py`),
> and multi-action paste dispatchers
> (`paste_auto` / `paste_clones_at_targets` /
> `paste_insert_after_zip` / `paste_replace_zip`).
> **Step 7 (validation: YAML schemas, multi-doc, schema picker UI,
> persistence, sanitization) is now complete**: `validation._sanitize`,
> `validation.yaml_validate`, `validation.json_pointer` `[doc N]`
> support, `state.validation_settings.clear_schema_path`,
> `app.validation_dock` schema picker toolbar, `JsonTab._init_validation_state`
> persistence lookup, `JsonTab.revalidate` routing via sanitize +
> yaml multi. The schema-registry branch adds registry/tab/watch/recents/UI
> suites on top of those validation tests.
> The current tree collects **1023 tests**; the known offscreen failures are
> platform-only — Qt's
> offscreen QPA ignores `QStyleHints.setColorScheme`). Production code
> still contains **zero `TODO` / `FIXME` / `XXX` / `HACK` markers**.

---

## FIXME — bugs & known issues

### Currently open
- [ ] [bug, env-only] **Offscreen Qt platform breaks color-scheme
      tests.** Qt's offscreen QPA ignores
      `QStyleHints.setColorScheme` and reports
      `Qt.ColorScheme.Unknown`, so 3 tests fail under
      `QT_QPA_PLATFORM=offscreen`:
      `tests/test_app_color_scheme.py::test_light_theme_sets_light_color_scheme`,
      `tests/test_app_color_scheme.py::test_dark_theme_sets_dark_color_scheme`,
      `tests/test_theme_switching.py::test_color_scheme_follows_selected_theme`.
      Fix: skip on offscreen, or monkey-patch `setColorScheme` /
      `colorScheme()` to round-trip the requested value. Production
      `app/theme_controller.py::_sync_app_color_scheme` is correct;
      tests pass on real platforms.

### Historical context (kept so audits don't re-open them)
- The post-pytest interpreter segfault tracked from Phase 4 is no
  longer reproducible against the current tree. If it returns,
  re-attach this FIXME with a fresh repro.
- `simplejson.load(..., use_decimal=True)` cannot be combined with
  `parse_float=mpq` on the pinned version; the compatible load path
  is `parse_float=mpq` only. Saves still use `use_decimal=True`. Not
  a bug — documented incompatibility.
- **Drag-and-drop "disappearing item" bug** (fixed mid-Step-6):
  Qt's default `QAbstractItemView::startDrag` calls
  `d->clearOrRemove()` for `MoveAction` results, which removed the
  freshly-placed destination rows after the model had already moved
  them. Fix: `tree/view.py::JsonTreeView` overrides `startDrag` and
  skips `clearOrRemove` whenever the drop was handled internally
  (signalled by `view.mark_drag_handled_internally()` from
  `tree_actions/dnd.py::handle_drop`).
- **Bigint overflow in `ValueDelegate.initStyleOption`** (fixed
  alongside the drag-and-drop work, commit `cdea82e`):
  reading `model.data(index, EditRole)` boxes the Python `int` into a
  C++ `long long` via Shiboken, overflowing for integers > 2^63−1.
  Fix: when `index.internalPointer()` is a `JsonTreeItem`, read the
  raw value and `json_type` directly from the item so the QVariant
  round-trip is bypassed. Regression test in
  `tests/test_value_delegate_theme.py`.
- **Multi-row Alt+Up/Down under `SelectItems`** (fixed during Step 4):
  `_selected_rows` fell back to `currentIndex()` when `selectedRows(0)`
  returned empty — which is always the case under `SelectItems`, the
  selection mode the live `JsonTab` uses. Only one row moved despite
  multiple cells being selected. Fix: collect `selectedIndexes()`,
  normalise each hit to col-0, dedup by `(row, parent)`. Regression
  test in `tests/test_keyboard_multimove_app_mode.py`.
- **Multi-selection collapsed after Alt+Up/Down** (fixed during Step
  4): `_MoveRowsCmd.redo/undo` used `view.setCurrentIndex()`, which
  internally issues `SelectCurrent` and shrinks the selection to a
  single row. Fix: `_select_placed_rows` helper builds a full
  `QItemSelection` over every placed row and commits it with
  `ClearAndSelect | Rows`, then moves the focus via
  `selectionModel().setCurrentIndex(NoUpdate)`. Same treatment in
  the macro-fallback path. Regression coverage in
  `tests/test_keyboard_multimove_app_mode.py`.
- **`paste_insert_zip` semantics swap** (fixed in Step 10): the
  original `paste_insert_zip()` was actually doing replace-in-place
  semantics; renamed to `paste_replace_zip` (Ctrl+Alt+V) and a fresh
  `paste_insert_after_zip` (Ctrl+Shift+V) was written that inserts
  each clipboard entry as sibling-after its matching target.
- **Ctrl+V single-target paste under multi-selection** (fixed in
  Step 10): `paste_from_clipboard()` only looked at
  `currentIndex()`, so multi-paste landed at the last clicked row
  only. Fixed by routing Ctrl+V through `paste_auto()` which
  dispatches to `paste_clones_at_targets` for multi-selection.
- **Context-menu eats the multi-selection** (fixed in Step 10):
  right-clicking on one row of an existing multi-selection used to
  collapse to that single row. Fixed in
  `tree_actions/context_menu.py::show_context_menu` — preserve the
  selection iff the hit row is inside it, otherwise fall back to the
  legacy single-row behaviour.
- **Insert-as-child at the synthetic root** (fixed mid-DnD work,
  commit `18915db`): inserting a child directly under the synthetic
  root produced an invalid index path. Fixed by routing the root
  case through `JsonTreeModel._root_index()` consistently.
- **Cycle drag into descendant** (covered by Step 7): dragging a
  parent onto its own descendant used to corrupt the tree (orphaned
  subtree). `tree_actions/dnd.py::can_drop` now rejects any move
  where a source path is a prefix of the resolved
  `target_parent_path`; `tests/test_drop_policies.py` covers it.

---

## TODO — open items

### Validation follow-ups (deferred from Step 7)
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

### Secret strings follow-ups (v2)
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

### Theme / docs
- [ ] [docs] `themes/builtin/schema.md` covering YAML grammar, every
      `JsonType`, fallback semantics, icon path resolution, worked
      examples.
- [ ] [docs] README theming section with screenshots and the user
      theme directory location per OS
      (`QStandardPaths.AppConfigLocation/themes/*.yaml`).
- [ ] [ux] Watch user theme **icon asset folders** in addition to
      YAML files so custom SVG/PNG edits hot-reload without touching
      the YAML. — `app/theme_controller.py`

### UX polish
- [ ] [ux] Match-highlight delegate (`ValueDelegate.paint` override
      drawing a yellow background span over substring matches when
      a filter is active). — `delegates/value.py`

### Code hygiene (low priority)
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

### Smells / footguns (very low priority, no functional impact)
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

### Long-horizon wishlist (`plan.txt`, not yet planned/scheduled)

Captured here so future audits don't lose them. None of these are
specced or actively in progress — they're the original wishlist from
the repo root.

- [ ] [feature] Float/integer numeric **previews**: hex/oct/bin for
      integers; float16/float32/float64 representation preview
      (context menu).
- [ ] [feature] Multiline statistics: lines / words / runes (Unicode
      code points) on the multiline editor.
- [ ] [feature] Toggleable alphabet sort and custom array sort.
- [ ] [feature] Array multi-cursor edit.
- [ ] [feature] Case transforms (Kebab / Snake / Camel / Caps) on
      file or selection.
- [ ] [feature] File translation pipeline (ru/en).
- [ ] [feature] Configurable keymap via `settings.json`.
- [ ] [feature] `Ctrl+PgUp` / `Ctrl+PgDown` to switch between tabs.

> _Delivered in 2026-05-13 drag-and-drop sweep:_
> - ~~Drag-and-drop value reordering with mouse~~ — native
>   `QTreeView` drag/drop via `tree_actions/dnd.py` +
>   `tree/view.py::JsonTreeView`.
> - ~~Multi-select on `Ctrl+A`; copy-as-array / copy-as-object;
>   contiguous-selection drag-and-drop~~ — multiselect foundation
>   (Step 1), MIME helpers with array/dict shape selection (Step 2),
>   multi-row undo (Step 3), keyboard multimove (Step 4), expansion
>   preservation (Step 5), drag-drop (Step 6), drop policies (Step 7),
>   shortcuts/menu (Step 8), anchor primitive + multi-action paste
>   semantics (Steps 9–10).
> - ~~`Shift+Up/Down/Right/Left` field reordering~~ — replaced by
>   `Alt+Up/Down` (same parent) and `Ctrl+Alt+Up/Down` (promote out of
>   parent) at the keyboard layer.

---

## Resolved (archived)
The "Resolved (kept for posterity)" changelog (drag-and-drop Steps 1–10,
schema-registry plan, validation Step 7, Theme phases 1–6, Phases 0–5.6,
package refactor 01–37, every per-phase fixed bug) lives in
[`history.md`](history.md). It is not re-summarized here to keep this
file compact for active-context use. Add new entries there when closing
multi-commit feature work; cross-reference from `repo-map.md` § 19 if
needed.
