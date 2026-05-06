# TODO & FIXME

_Last updated: 2026-05-06._

Tracks **missing/incomplete features** (TODO) and **bugs/issues** (FIXME)
discovered while auditing the JSON editor codebase. Cross-reference with
`pros-n-cons.md` and `repo-map.md` for context.

Format: `- [ ] [scope] description — file:symbol`

> **Active shipping plan (2026-05-06):** `plans/README.md` lists six
> phases (context-menu polish → zoom-column preservation → kind-switch
> coercion → display & preview → full-app theming → cross-phase
> tests/memory). New issues from the 2026-05-06 user request are
> tracked there until the corresponding phase lands; resolved entries
> migrate back into this file's Resolved section.

> **Status (2026-05-06)** — Phases 0–6 are fully shipped, including the
> full theming stack and the Phase-6 `ThemeController` refactor. The
> package refactor (Phases 01–37) is complete:
> all old top-level "god modules" (`json_tab.py`, `ui.py`, `tree_view.py`,
> `tree_model.py`, `tree_item.py`, `delegate.py`, `enums.py`, `file_io.py`,
> `view_state.py`) have been split into the canonical packages and removed.
> The current tree collects **451 tests**; the dedicated Phase-1–6
> theming surface contributes **50 passing tests** under
> `QT_QPA_PLATFORM=offscreen pytest -q`. The older full-suite baseline in
> memory remains 401 passing tests (`2026-04-26`); the post-test segfault
> previously tracked is still not reproducible.

---

## TODO — open items

### Active UX/correctness batch (2026-05-06 — see `plans/`)
- [ ] [ux] Disable all context-menu actions on the kind column;
      column-aware Copy on name/value columns.
      → `plans/phase-1-context-menu.md`
- [ ] [ux] Zoom in/out/reset preserves user-resized column widths.
      → `plans/phase-2-zoom-columns.md`
- [ ] [bug] Kind-switch coercion overhaul: bool→str lowercase;
      bytes/zlib/gzip encode-on-switch; date/time/datetime "now"
      placeholder + epoch sec/ms parsing; object↔array preserves
      children (`item1, item2, …`).
      → `plans/phase-3-coercion.md`
- [ ] [ux] Object/array meta + collapsed preview; `#i` array
      indices; PERCENT always renders as `%`; theme styling visible
      on value cells (not only kind column).
      → `plans/phase-4-display-preview.md`
- [ ] [ux] Flip Qt's bundled light/dark color scheme to match the
      active theme's `mode` (no custom palette or stylesheet —
      per-type cell colouring stays in the delegate). Replaces the
      old "Apply the active theme to more of the application chrome"
      stretch item.
      → `plans/phase-5-app-theme.md`
- [ ] [tests] Cross-phase regression smoke + `ai-memory/` refresh.
      → `plans/phase-6-tests-memory.md`

### Broader QA / tooling gaps
- [ ] [tests] `tests/test_value_delegate.py`: full editor matrix.
      - editor widget class per JsonType
      - `setEditorData` / `setModelData` round-trip for INTEGER, mpq
        FLOAT/PERCENT, BOOLEAN, DATE/TIME/DATETIME/DATETIMEZONE,
        STRING/UNICODE
      - dispatch-by-widget-class survives stale editors
      - dialog-based delegates (MULTILINE / TEXT / BYTES / ZLIB / GZIP)
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
      - `_unique_child_name` collision avoidance with a reserved-name
        set
- [ ] [tooling] Add `pytest-qt` to `requirements.txt`.
- [ ] [tooling] Add a `make test` target running
      `QT_QPA_PLATFORM=offscreen pytest -q`.
- [ ] [tooling] Add `coverage`/`pytest-cov` and commit a short
      summary to `ai-memory/coverage.md`.
- [ ] [tests] Smoke-cover Phase 4+ actions in `test_smoke_mainwindow.py`
      end-to-end (open → edit → Save → reopen → verify dirty marker
      cleared, recent-files menu populated).

### Phase 7 — theme docs / contributor tooling
- [ ] [docs] Add `themes/builtin/schema.md` covering YAML grammar,
      every `JsonType`, fallback semantics, icon path resolution, and
      worked examples.
- [ ] [docs] Add a README theming section with screenshots and the user
      theme directory location per OS.
- [ ] [tests] Add `tests/test_theme_snapshot.py` for deterministic
      built-in theme snapshots and partial-override coverage checks.
- [ ] [tests] Add `tests/test_theme_accessibility.py` for WCAG-style
      contrast regression coverage on built-in themes.
- [ ] [tooling] Add a `themes-check` target to `Makefile`.

### Stretch UX items (optional, deferred from Phase 5)
- [ ] [ux] Match-highlight delegate (`ValueDelegate.paint` override
      drawing a yellow background span over substring matches when
      a filter is active). — `delegates/value.py:ValueDelegate.paint`
- [ ] [ux] Apply the active theme to more of the application chrome
      (menus/toolbars/dialog palette), not just tree content and icons.
      — `app/theme_controller.py`, `app/main_window.py`
      _(superseded by `plans/phase-5-app-theme.md`)_
- [ ] [ux] Watch user theme icon asset folders in addition to YAML
      files so custom SVG/PNG edits hot-reload without touching the YAML.
      — `app/theme_controller.py`

### Code hygiene (low priority)
- [ ] [hygiene] Drop the legacy `_demo_data()` seed and its
      `base64` / `gzip` / `zlib` / `gmpy2` imports from
      `documents/tab.py` once the remaining bare-`JsonTab(...)` tests
      migrate to explicit `data=` constructors.
- [ ] [hygiene] Decide whether to keep `header_view_editor.py`. The
      mixin is currently unused (commented out at the call site).
- [ ] [hygiene] Either tighten `MainWindow.update_actions` to enable
      `Save` only when `tab.is_dirty`, or document that the current
      "always-on" behaviour is intentional. —
      `app/main_window_actions.py`

### Smells / footguns (very low priority, no functional impact)
- [ ] [smell] `JsonTreeItem.row()` returns `0` for the root (no parent)
      instead of `-1`; tolerable but a footgun for future code.
- [ ] [smell] `ValueDelegate.createEditor` raises `ValueError` for
      `OBJECT`, `ARRAY`, `NULL` (unreachable thanks to `flags()`);
      a defensive `return None` would degrade more gracefully.
- [ ] [smell] `view_state` persists expansion/current as positional
      `(int,…)` paths; structural mutations (sort/insert/paste) before
      a save→reload land on a different node. Consider keying by name
      where available.
- [ ] [smell] `JsonTab.save()` catches `Exception` and reports via
      status bar; consider narrowing the catch and surfacing structured
      diagnostics for malformed datetime / bytes.

---

## FIXME — bugs & known issues

_All previously-tracked bugs from Phases 0–4 (column-API leak,
malformed-binary `flags()` raise, dialog `model.setData` bypass, decode
failure escaping `createEditor`, post-test segfault) are resolved as of
2026-04-26._

### Currently open
- (none) — production code contains no `TODO` / `FIXME` / `XXX` /
  `HACK` markers, and the suite is green and stable.

### Notes carried over from earlier audits (kept as historical context)
- The post-pytest interpreter segfault tracked from Phase 4 is no
  longer reproducible against the current tree. If it returns,
  re-attach this FIXME with a fresh repro.
- `simplejson.load(..., use_decimal=True)` cannot be combined with
  `parse_float=mpq` on the pinned version; the compatible load path
  is `parse_float=mpq` only. Saves still use `use_decimal=True`. Not
  a bug — documented incompatibility.

---

## Resolved (kept for posterity)

The following bugs/features were fixed or delivered during Phases 0–6;
they're listed once
here so future audits don't reopen them.

### Theme phases 1–6 (2026-05-06)
- Phase 1 — `themes/spec.py`, `themes/loader.py`, and
  `themes/_defaults.py` landed with frozen/hashable theme dataclasses,
  YAML parsing, total fallback semantics, and icon-block parsing.
- Phase 2 — built-in `themes/builtin/light.yaml` / `dark.yaml`,
  `themes/registry.py`, `themes/auto.py`, and
  `state/theme_settings.py` landed with built-in/user discovery,
  system-mode detection, and persisted theme preferences.
- Phase 3 — `ValueDelegate` / `JsonTypeDelegate` became theme-aware;
  `JsonTab.set_theme(...)` repaints open tabs via `dataChanged`
  instead of rebuilding models/views.
- Phase 4 — `themes/icon_provider.py` landed with
  `StubIconProvider` / `FileIconProvider`, icon-path resolution, and
  reloadable icon caching.
- Phase 5 — bundled SVG icons now ship under `themes/builtin/icons/`,
  `JsonTreeModel` returns `DecorationRole` for column 1, and the type
  combobox reuses the same icon provider.
- Phase 6 — live View → Theme switching, follow-system persistence,
  opt-in `QFileSystemWatcher` hot reload, and
  `colorSchemeChanged` handling shipped; the follow-system selection bug
  was fixed and the logic was refactored into `app/theme_controller.py`.

### Phase 0
- `tests/test_mpq2py.py::test_mpq_with_json` — fixed by returning
  `mpq_serialization(obj)[0]` from `mpq_json_default`.
- `MainWindow.copy_action` syntactically incomplete — replaced.
- `MainWindow.insert_row` / `insert_child` / `remove_row` referenced
  non-existent `self.view` — replaced with `_current_view()`.
- `MainWindow.close_tab` had a `pass` body — now Save/Discard/Cancel
  flow.
- `ui.py` unused imports stripped (`functools`, `yaml`,
  `HeaderViewEditorMixin`, `JsonTypeDelegate`, `JsonTreeModel`,
  `show_context_menu`).
- Embedded C++ docstring blocks removed from `tree_model.py`,
  `tree_item.py`, `ui.py`.

### Phase 1
- `JsonTreeModel` always-False column insert/remove API removed.
- `JsonTreeItem.insert_children` now seeds `value=None`
  (single NULL row) instead of `[None] * columns`.
- `_unique_child_name` introduced for OBJECT children.
- `parse_json_type` made total (returns STRING with logger warning).
- `_looks_like_base64` strict + datetime-first heuristic.
- PERCENT auto-detection narrowed.
- `flags()` decode moved to cached `JsonTreeItem.editable`.

### Phase 2
- `JsonTypeDelegate.setModelData` / `setEditorData` — proper preselect
  + commit.
- `JsonTreeItem.set_data` total across columns 0/1/2 with
  `_coerce_value_for_type`.
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
- `JSONL` and `YAML multi-document` formats added beyond original
  Phase-4 scope.

### Phase 5.1
- `JsonTypeDelegate._interactive` flag + `JsonTab._on_type_changed`
  auto-reopen via `QTimer.singleShot(0, ...)`.
- Dialog-edit callbacks use `QPersistentModelIndex` and route through
  `ValueDelegate._commit` → `JsonTab.commit_set_data`.
- `QHexDialog` decode wrapped in try/except, surfacing failures via
  `_notify_status`.
- `_RenameCmd` / `_EditValueCmd` `id()` + `mergeWith` 500 ms window.

### Phase 5.2
- `JsonTreeModel` exposes `JSON_TYPE_ROLE` and `Qt.ToolTipRole` for
  long values.
- `ValueDelegate.initStyleOption` / `displayText` formats PERCENT,
  mpq, BYTES family, long strings.
- `units.format_bytes` helper.

### Phase 5.3
- `JsonTab` accepts `permanent_message_callback`;
  `_on_current_changed` writes `$.qualified.path  (type, size hint)`.
- Transient messages on Open / Save / tree actions.

### Phase 5.4
- `view_state.py` (`state_key` / `save` / `restore` / `discard`).
- `MainWindow._add_tab` / `close_tab` / `closeEvent` / `_save_tab`
  wired.
- Font zoom on `JsonTab` (`Ctrl+=`, `Ctrl+-`, `Ctrl+0`, persisted).

### Phase 5.5
- `tree_filter_proxy.TreeFilterProxy` recursive name+value filter.
- `JsonTab.search_edit` with 150 ms debounce; Ctrl+F focus.
- All delegates and `tree_view.py` helpers map proxy indices to source.

### Phase 5.6
- `JsonTab.resize_key_columns` on tab switch / `model.modelReset`.
- Expand / Collapse all in tree context menu and View menu.
- Zoom actions in View menu.

### Package refactor (Phases 01–37, 2026-04-26)
- Top-level "god modules" split into cohesive packages and removed:
  `json_tab.py` → `documents/`, `ui.py` → `app/`,
  `tree_view.py` → `tree_actions/`, `tree_model.py` + `tree_item.py`
  + `enums.py` → `tree/`, `delegate.py` → `delegates/`,
  `file_io.py` → `io_formats/`, `view_state.py` → `state/`.
- Undo command classes and diff replay extracted to `undo/commands.py`
  + `undo/diff.py` (`DiffApplier`).
- `tree_view._commit_on_tab` dead code removed during Phase 22.
- All internal imports migrated to canonical package paths in Phase 35;
  compatibility shims removed in Phase 37. No source file (other than
  generated `mainwindow.py`) exceeds ~510 lines.
- Full suite stayed green at 401 passed throughout every phase.
