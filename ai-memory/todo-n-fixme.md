# TODO & FIXME

_Last updated: **2026-05-13**._

Tracks **missing/incomplete features** (TODO) and **bugs/issues**
(FIXME) discovered while auditing the editor codebase.
Cross-reference with `pros-n-cons.md` and `repo-map.md` for context.

Format: `- [ ] [scope] description — file:symbol`

> **Status (2026-05-13)** — All historical phases (0–6 + package
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
> `paste_insert_after_zip` / `paste_replace_zip`). The current tree
> collects **779 tests**; **776 pass and 3 fail** under
> `QT_QPA_PLATFORM=offscreen` (the 3 failures are platform-only — Qt's
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

### Test / tooling gaps
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
- [ ] [ux] Tighten `MainWindow.update_actions` to enable `Save` only
      when `tab.is_dirty`, or document that the current "always-on"
      behaviour is intentional. — `app/main_window_actions.py`

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

## Resolved (kept for posterity)

The following bugs/features were fixed or delivered in past phases;
listed once here so future audits don't reopen them.

### Drag-and-drop / multi-action plan — Steps 1–10 (shipped 2026-05-13)
- **Step 1 — multiselect foundation.** Promoted
  `_selected_rows` / `_top_level_selected_rows` to public
  `selected_source_rows` / `top_level_source_rows`; added
  `selection_spans_multiple_parents`. Back-compat underscore
  aliases retained. `tests/test_multiselect_foundation.py`.
- **Step 2 — reusable MIME (de)serializer.** Extracted
  `build_tree_mime(model, source_rows) -> QMimeData | None` and
  pure decoder `entries_from_mime(mime)`. `MIME_JSON_TREE`,
  both helpers re-exported from `tree_actions/__init__.py`.
  `tests/test_mime_payload.py`.
- **Step 3 — atomic multi-row undo move.** `_MoveRowsCmd` with
  pre-pop `target_row` arithmetic for same-parent forward/backward
  moves; `JsonTab.push_move_rows(sources, target_parent, target_row)`
  with cycle guard; `push_move_row` now delegates. `mergeWith` always
  `False`. `tests/test_undo_multimove.py`.
- **Step 4 — keyboard multimove with bubble-out.** Alt+Up/Down on
  any selection (single, contiguous, disjoint, multi-parent); at
  the parent boundary the selection promotes/demotes across the
  parent. `_select_placed_rows` preserves the multi-selection
  through redo/undo. `tests/test_keyboard_multimove*.py`.
- **Step 5 — preserve collapse / expansion state across moves.**
  Move commands capture subtree-relative expansion and selection
  state and replay them. `tests/test_move_preserves_expansion.py`.
- **Step 6 — native drag-and-drop wired to multi-move.**
  `JsonTreeModel.mimeTypes / mimeData / canDropMimeData /
  dropMimeData / supportedDrag,DropActions / flags()`;
  `tree_actions/dnd.py::can_drop / handle_drop`;
  `documents/tab_setup.py` flips on
  `setDragEnabled / setAcceptDrops / setDropIndicatorShown /
  setDragDropMode(DragDrop)`; `model.attach_view(view)` plumbing.
  `tree/view.py::JsonTreeView` overrides `startDrag` so Qt's
  `clearOrRemove` doesn't delete the freshly-placed destination
  rows. `tests/test_drag_drop_internal.py` +
  `test_drag_drop_matrix.py` + `test_drag_drop_property.py`.
- **Step 7 — drop policies, indicators & visual cues.** Cycle
  guard via `source_paths_from_mime` envelope key in MIME;
  `_resolve_drop_target` covers row≥0, row=−1 on container, row=−1
  on leaf (sibling-after), row=−1 on invalid root. Transient
  status message `"Moved N rows under $.foo"` /
  `"Copied N rows under $.bar"`. `tests/test_drop_policies.py`.
- **Step 8 — shortcuts, menu labels, repo-map refresh.** Hooked
  `Alt+Up/Down`, `Ctrl+Alt+Up/Down` (move out of parent),
  `Ctrl+Shift+V` (paste-insert-zip), `Ctrl+Alt+V` (paste-replace-zip)
  per-tab; documented in §4 / §5 of `repo-map.md`.
- **Step 9 — move-mechanics + multi-action redesign.** Collapsed
  the three move branches (`_move_same_parent`,
  `_multi_parent_common_grandparent_move`,
  `_move_multi_parent_fallback`) into a single anchor-based
  primitive in `tree_actions/anchors.py`
  (`MoveAnchor`, `anchor_at_end / before / after`,
  `resolve_anchor_target`, `pre_pop_target_row_to_anchor`,
  `anchor_is_cycle / no_op`).
  `JsonTab.push_move_rows_anchor` is the single entry point;
  `push_move_rows` is a thin shim. New filter-mode projection in
  multi-copy; new `paste_clones_at_targets`, `paste_insert_zip`
  helpers. `tests/test_anchor_move.py` +
  `test_multi_action_semantics.py`.
- **Step 10 — multi-action paste + context-menu fixes.** Renamed
  the original `paste_insert_zip` (which actually replaced values)
  to `paste_replace_zip` (Ctrl+Alt+V); added a real
  `paste_insert_after_zip` (Ctrl+Shift+V) that inserts each
  clipboard entry as sibling-after its matching target. Added
  `paste_auto` dispatcher (single ⇒ legacy paste,
  multi ⇒ `paste_clones_at_targets`) and routed Ctrl+V through it.
  `tree_actions/context_menu.py` now preserves multi-selection on
  right-click inside the selection and collapses to the hit row
  otherwise. `tests/test_context_menu_multiselect.py`.

### Former `plans/` phases (shipped between 2026-05-06 and 2026-05-08)
- **Phase 1 — context-menu polish.** Type column shows only
  Expand/Collapse; column-aware Copy on name (`copy_selection_with_name`)
  and value (`copy_selection_value_only`) columns;
  `tree_actions/clipboard.py` exposes the three variants.
- **Phase 2 — zoom-column preservation.** `JsonTab` now tracks
  `_user_sized_columns` and a `_programmatic_column_resize` guard so
  font-zoom and `resize_key_columns` no longer poison user-resized
  widths. Wired in `documents/tab_setup.py`.
- **Phase 3 — kind-switch coercion overhaul.**
  `tree/item_coercion.py::coerce_value_for_type(..., old_type=...)`
  with: bool→str lowercase; DATE/TIME/DATETIME/DATETIMEZONE "now"
  fallback; integer sec/ms ↔ DATETIME round-trip;
  BYTES/ZLIB/GZIP encode-on-switch and lossless cross-format
  re-encode when `old_type` is known; ARRAY↔OBJECT child preservation
  with `item1, item2, …` keys; `tree/stubs.py` random "famous"
  placeholders for unrecoverable cases. Tests in
  `tests/test_kind_switch_coercion.py`.
- **Phase 4 — display & preview.** Container preview
  `[N items]  v1, v2, …` / `{N keys}  k: v, …` with first 5 children,
  suppressed when row is expanded; PERCENT renders as `%` everywhere;
  multiline previews use `_MULTILINE_SEPARATOR = " | "`. Implementation
  in `delegates/value_formatting.py::_format_container_preview`; tests
  in `tests/test_container_preview.py`.
- **Phase 5 — full-app theming via Qt color scheme.**
  `app/theme_controller.py::_sync_app_color_scheme` calls
  `QStyleHints.setColorScheme(Qt.ColorScheme.{Light,Dark})` to flip
  Qt's bundled chrome to match the active theme's `mode`. No custom
  palette/stylesheet; per-type cell colouring stays in delegates.
  Tests in `tests/test_app_color_scheme.py` and
  `test_theme_switching::test_color_scheme_follows_selected_theme`
  (the 3 offscreen-only failures are tracked under FIXME above).
- **Phase 6 — tests / memory refresh.** This memory pass + the new
  test files above. `themes/_contrast.py` (WCAG luminance / contrast
  helpers) landed as scaffolding for the not-yet-written
  accessibility suite.

### Theme phases 1–6 (2026-05-06)
- Phase 1 — `themes/spec.py`, `themes/loader.py`,
  `themes/_defaults.py`: frozen/hashable theme dataclasses, YAML
  parsing, total fallback semantics, icon-block parsing.
- Phase 2 — `themes/builtin/light.yaml` / `dark.yaml`,
  `themes/registry.py`, `themes/auto.py`, `state/theme_settings.py`:
  built-in/user discovery, system-mode detection, persisted theme
  preferences.
- Phase 3 — `ValueDelegate` / `JsonTypeDelegate` became theme-aware;
  `JsonTab.set_theme(...)` repaints open tabs via `dataChanged`
  instead of rebuilding models/views.
- Phase 4 — `themes/icon_provider.py` with `StubIconProvider` /
  `FileIconProvider`, icon-path resolution, reloadable icon caching.
- Phase 5 — bundled SVG icons under `themes/builtin/icons/`,
  `JsonTreeModel` returns `DecorationRole` for col 1, the type
  combobox reuses the same icon provider.
- Phase 6 — live View → Theme switching, follow-system persistence,
  opt-in `QFileSystemWatcher` hot reload, `colorSchemeChanged`
  handling; follow-system selection bug fixed; logic refactored into
  `app/theme_controller.py`.

### Phase 0
- `tests/test_mpq2py.py::test_mpq_with_json` — fixed by returning
  `mpq_serialization(obj)[0]` from `mpq_json_default`.
- `MainWindow.copy_action` syntactically incomplete — replaced.
- `MainWindow.insert_row` / `insert_child` / `remove_row` referenced
  non-existent `self.view` — replaced with `_current_view()`.
- `MainWindow.close_tab` had a `pass` body — now Save/Discard/Cancel
  flow.
- `ui.py` unused imports stripped; embedded C++ docstring blocks
  removed from `tree_model.py`, `tree_item.py`, `ui.py`.

### Phase 1 (original)
- `JsonTreeModel` always-False column insert/remove API removed.
- `JsonTreeItem.insert_children` now seeds `value=None`
  (single NULL row) instead of `[None] * columns`.
- `unique_child_name` introduced for OBJECT children.
- `parse_json_type` made total (returns STRING with logger warning).
- `_looks_like_base64` strict + datetime-first heuristic.
- PERCENT auto-detection narrowed.
- `flags()` decode moved to cached `JsonTreeItem.editable`.

### Phase 2
- `JsonTypeDelegate.setModelData` / `setEditorData` — proper preselect
  + commit.
- `JsonTreeItem.set_data` total across columns 0/1/2 with
  `coerce_value_for_type`.
- Type pinning via `explicit_type`.
- `ValueDelegate.setEditorData` BOOLEAN branch fixed.

### Phase 3
- Cut / Delete / Paste actions wired.
- Insert before / after distinguished.
- Typed `QUndoCommand` subclasses replace whole-document snapshots.

### Phase 4
- `MainWindow.setup_model` loads CLI files into a tab.
- File menu (Open / Save / Save As / Recent / Close-confirm /
  closeEvent) wired.
- Atomic write via `os.replace`.
- `JsonTab` accepts `data` / `file_path`; dirty-state via
  `undo_stack.cleanChanged`; `*` tab marker; `dirtyChanged` signal.
- Recent-files persisted via `QSettings`, capped at 8, missing-file
  pruning.
- JSONL and YAML multi-document formats added beyond original
  Phase-4 scope.

### Phase 5.1 – 5.6
- 5.1: `JsonTypeDelegate._interactive` flag + `JsonTab._on_type_changed`
  auto-reopen via `QTimer.singleShot(0, ...)`; dialog-edit callbacks
  use `QPersistentModelIndex` and route through
  `ValueDelegate._commit` → `JsonTab.commit_set_data`; `QHexDialog`
  decode wrapped in try/except surfacing failures via `_notify_status`;
  `_RenameCmd` / `_EditValueCmd` `id()` + `mergeWith` 500 ms window.
- 5.2: `JsonTreeModel` exposes `JSON_TYPE_ROLE` and `Qt.ToolTipRole`
  for long values; `ValueDelegate.initStyleOption` / `displayText`
  formats PERCENT, mpq, BYTES family, long strings; `units.format_bytes`
  helper.
- 5.3: `permanent_message_callback`; breadcrumb
  `$.qualified.path  (type, size hint)`; transient action messages.
- 5.4: `view_state.py` (`state_key` / `save` / `restore` / `discard`);
  `MainWindow._add_tab` / `close_tab` / `closeEvent` / `_save_tab`
  wired; font zoom on `JsonTab` (`Ctrl++`, `Ctrl+-`, `Ctrl+0`,
  persisted).
- 5.5: `tree_filter_proxy.TreeFilterProxy` recursive name+value
  filter; `JsonTab.search_edit` with 150 ms debounce; Ctrl+F focus;
  proxy↔source mapping helpers in delegates and tree-action helpers.
- 5.6: `JsonTab.resize_key_columns` on tab switch / `model.modelReset`;
  Expand/Collapse all in tree context menu and View menu; Zoom
  actions in View menu.

### Package refactor (Phases 01–37, 2026-04-26)
- Top-level "god modules" split into cohesive packages and removed:
  `json_tab.py` → `documents/`, `ui.py` → `app/`,
  `tree_view.py` → `tree_actions/`, `tree_model.py` + `tree_item.py`
  + `enums.py` → `tree/`, `delegate.py` → `delegates/`,
  `file_io.py` → `io_formats/`, `view_state.py` → `state/`.
- Undo command classes and diff replay extracted to `undo/commands.py`
  + `undo/diff.py` (`DiffApplier`).
- Compatibility shims removed in Phase 37; all internal imports use
  canonical package paths. No source file (other than generated
  `mainwindow.py`) exceeds ~580 lines.
- Full suite stayed green at 401 passed throughout every phase.
