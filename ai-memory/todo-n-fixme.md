# TODO & FIXME

_Last updated: 2026-04-26._

Tracks **missing/incomplete features** (TODO) and **bugs/issues** (FIXME)
discovered while auditing the JSON editor codebase. Cross-reference with
`pros-n-cons.md` and `phases/` for context.

Format: `- [ ] [scope] description — file:symbol`

> **Status (2026-04-26)** — Phases 0–5 are fully shipped (all sub-phases
> of Phase 5 included). Phase 6 testing is the only milestone still
> open. **401 tests pass** under
> `QT_QPA_PLATFORM=offscreen pytest -q` in ~3 s; the post-test segfault
> previously tracked is no longer reproducible.

---

## TODO — open items

### Phase 6 — Tests (the only open milestone)
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
- [ ] [tooling] Pin `simplejson` (currently imported by `file_io.py`
      and `tree_view.py` without an entry in `requirements.txt`).
- [ ] [tooling] Add `coverage`/`pytest-cov` and commit a short
      summary to `ai-memory/coverage.md`.
- [ ] [tests] Smoke-cover Phase 4+ actions in `test_smoke_mainwindow.py`
      end-to-end (open → edit → Save → reopen → verify dirty marker
      cleared, recent-files menu populated).

### Stretch UX items (optional, deferred from Phase 5)
- [ ] [ux] Match-highlight delegate (`ValueDelegate.paint` override
      drawing a yellow background span over substring matches when
      a filter is active). — `delegate.py:ValueDelegate.paint`
- [ ] [ux] Type icons in column 1: register `:/icons/<type>.svg` and
      return them from `JsonTreeModel.data(..., DecorationRole)`.
      — `tree_model.py`, `delegate.py`

### Code hygiene (low priority)
- [ ] [hygiene] Drop the legacy `_demo_data()` seed and its
      `base64` / `gzip` / `zlib` / `gmpy2` imports from `json_tab.py`
      once the remaining bare-`JsonTab(...)` tests migrate to explicit
      `data=` constructors.
- [ ] [hygiene] Delete `tree_view._commit_on_tab` — dead code; the
      `commit_mutation` API it looks for no longer exists on `JsonTab`
      (superseded by typed `push_*` helpers).
- [ ] [hygiene] Decide whether to keep `header_view_editor.py`. The
      mixin is currently unused (commented out at the call site).
- [ ] [hygiene] Either tighten `MainWindow.update_actions` to enable
      `Save` only when `tab.is_dirty`, or document that the current
      "always-on" behaviour is intentional.

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

The following bugs were fixed during Phases 0–5; they're listed once
here so future audits don't reopen them.

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
