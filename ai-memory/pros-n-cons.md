# JSON Editor — Pros & Cons

_Last analysis: 2026-04-26 (Phase 4 core in progress; 346 tests pass, but post-pytest segfault remains.)_

This document evaluates the **current** state of the JSON tree editor
implementation (`tree_model.py`, `tree_item.py`, `delegate.py`,
`enums.py`, `json_tab.py`, `tree_view.py`, `ui.py`,
`model_actions.py`).

## ✅ Pros

### Architecture & design
- **Clean separation of concerns** between data layer (`JsonTreeItem`),
  model layer (`JsonTreeModel`), view + action layer (`JsonTab` /
  `tree_view.py` / `QTreeView`), editing layer
  (`ValueDelegate` / `JsonTypeDelegate`), and shell layer (`ui.py`).
- **Tabbed multi-document architecture** via `QTabWidget` + `JsonTab` —
  each tab encapsulates its own model, view, delegates *and* its own
  `QUndoStack`.
- **Three-column schema** (`Name | Type | Value`) is well chosen for
  JSON: it surfaces the inferred type as a first-class, editable
  concept rather than hiding it behind value text.
- **Streaming JSON serialization** (`jsontream`) is used for
  copy-to-clipboard, avoiding loading the whole subtree into a single
  string up front.
- **Rich type system** (`JsonType` enum) goes well beyond plain JSON:
  percent, multiline, date/time/datetime/tz, bytes, zlib, gzip — the
  editor is positioned as a *structured-data* editor, not just JSON.
- **Auto-detection of types** in `parse_json_type()` is now total and
  conservative: short ambiguous strings stay as `STRING`, datetime is
  checked before bytes, PERCENT is no longer auto-promoted, and
  unknown values fall back to `STRING` with a logger warning instead
  of raising.
- **Type pinning** (`JsonTreeItem.explicit_type`) lets the user
  override auto-classification — pasted base64-like or
  newline-containing strings can be kept as plain `STRING`.
- **Exact numeric arithmetic** via `gmpy2.mpq` and
  `QMpqSpinBox` / `QBigIntSpinBox` avoids float precision loss.
- **Dedicated specialist editors** are wired through delegates:
  `BetterDateTimeEditor` for temporal values, `QHexDialog` for binary,
  `QMultilineDialog` for text blobs. Each persists settings via
  `QSettings`.
- **Begin/End model signals** are wrapped in context managers
  (`rows_insertion`, …), which makes Qt model bookkeeping
  exception-safe.
- **Row-level editability is data-aware**: `flags()` disables editing
  for `null`, array/object containers, and oversize blobs (>10 KB),
  but the underlying check is cached on `JsonTreeItem.editable` so
  `flags()` stays O(1) — malformed binary payloads no longer raise
  on every paint.
- **Typed-command undo/redo**: every tree mutation (rename, type
  change, value edit, insert, remove, move, sort, paste, duplicate,
  cut) pushes an O(affected-subset) typed `QUndoCommand`. No
  whole-document snapshots; undo/redo replays via surgical Qt model
  signals, preserving expansion and selection.
- **Path-based addressing** in undo commands (`(int, …)` paths
  resolved by `JsonTab._index_from_path()`) sidesteps
  `QModelIndex` invalidation across mutations.
- **Substantial test coverage**: 346 tests, including end-to-end
  scenario coverage of every JsonType crossed with every mutating
  action, plus wall-clock + memory bounds locking the typed-command
  contract in place.
- **Phase 4 core shell plumbing is now present**: `MainWindow.setup_model`
  loads CLI files, File menu open/save/save-as are wired, recent-files
  menu is persisted via `QSettings`, and dirty-state/tab-title flow is
  wired through `QUndoStack.cleanChanged`.
- **Reusable widget stack**: `qhexedit`, `qmultiline_editor`,
  `datetime_editor`, `qbigint_spinbox`, `qmpq_spinbox` are
  independently useful packages.

### Code quality
- Modern Python (3.12+ `match`/`case`, `StrEnum`, type hints across
  most modules).
- `Makefile` enforces formatting (`black`, `isort`, `autoflake`).
- Pytest config (`pytest.ini`) sets `pythonpath = .` for consistent
  runs.
- Phase 0 stripped the embedded C++ docstrings and unused imports
  from `ui.py` / `tree_model.py` / `tree_item.py`.

---

## ❌ Cons

### App shell remaining work (Phase 4)
- Core file I/O is implemented, but `JsonTab` still keeps legacy demo
  seed behavior for bare `JsonTab(...)` construction to preserve older
  tests; full constructor migration is still pending.
- `MainWindow.update_actions()` currently enables Save whenever a tab
  exists; optional refinement is to enable Save only when dirty.
- Round-trip tests are only partially covered (JSON load/save smoke and
  dirty-state tests exist; dedicated YAML round-trip tests are pending).
- A new issue appeared during Phase 4 runs: full `pytest` reports all
  tests passing, then the interpreter segfaults on teardown.

### Delegate / editor remaining issues (Phase 5)
- `ValueDelegate.createEditor` for `MULTILINE` / `BYTES` / `ZLIB` /
  `GZIP` opens a dialog and returns `None`. The dialog callbacks
  capture raw `QModelIndex` by closure and call `model.setData`
  directly; this bypasses the typed undo stack and breaks if rows
  are inserted/removed while the dialog is open. Fix: convert to
  `QPersistentModelIndex` and route through
  `JsonTab.commit_set_data`.
- `QHexDialog` decodes/decompresses the entire payload eagerly inside
  `createEditor`. A malformed `ZLIB` / `GZIP` value raises from
  `createEditor` before the dialog is shown — should be wrapped in
  try/except with a status-bar message.
- After a user-driven type change, the value editor does **not**
  auto-reopen with the new delegate; the user has to double-click
  the value cell again. The hook point is `JsonTab._on_type_changed`
  / `JsonTypeDelegate.setModelData`. Programmatic `setData` paths
  must keep their current behaviour (no auto-edit) so existing tests
  stay green.
- Consecutive value/name edits to the **same** path push separate
  undo entries; `mergeWith` on `_EditValueCmd` and `_RenameCmd`
  would collapse them into single user-visible undo steps.

### UX / display polish (Phase 5)
- No `displayText()` on `ValueDelegate`: PERCENT shows as `0.5`
  rather than `50%`, mpq fractions show as raw repr, long strings
  are not elided with tooltip fallback, datetimes-with-tz lack a
  human-friendly format.
- No status-bar breadcrumb (`Path: a > b > 3 (string, 24 chars)`);
  selection changes are silent.
- No persisted column widths or expansion state per file (depends
  on Phase 4 file paths landing first).
- No search / filter bar; finding values in a large document
  requires manual expansion.
- No collapse-all / expand-all / font zoom actions.

### Tree/model semantic smells (low priority)
- `JsonTreeItem.row()` returns `0` for the root rather than
  signalling "no parent"; works but is a footgun. (Phase 6 invariant
  test suggested.)
- `JsonTreeModel.data()` returns `None` implicitly for non-Display /
  Edit roles; an explicit `return None` plus a real
  `Qt.ToolTipRole` branch is wanted (Phase 5).
- `ValueDelegate` raises `ValueError` when `json_type` is
  unsupported (`OBJECT`, `ARRAY`, `NULL`); these branches *should*
  be unreachable thanks to `flags()`, but a defensive `return None`
  would degrade more gracefully.

### Persistence / I/O remaining risks (Phase 4)
- JSON load path cannot use `simplejson.load(..., use_decimal=True)`
  together with `parse_float=mpq` on the pinned version; compatibility
  path is now `parse_float=mpq` only.
- YAML and JSON format validation before save (datetime/bytes strictness)
  is still not surfaced as dedicated user-facing diagnostics.
- App-level teardown stability needs investigation due to the post-test
  segfault noted above.

### Test gaps (Phase 6)
- No model-invariant suite covering `setData` row-wide
  `dataChanged` emission, `removeRows` persistent-index correctness,
  `parent()` / `index()` round-trips on a 3-level tree.
- No full delegate matrix test: editor type, `setEditorData` /
  `setModelData` round-trip per JsonType, dispatch by editor widget
  class.
- No JSON / YAML round-trip tests against `data.json` / `data.yaml`
  — those wait on Phase 4.
- `pytest-qt` is not yet in `requirements.txt`; smoke tests
  hand-roll a `QApplication` fixture.

---

## TL;DR

The **editor primitives** (delegates, custom widgets, datetime / hex /
multiline editors, exact numerics, type detection) are in good shape
and well tested. The **tree editing & undo/redo** layer is now
production-quality after Phase 3: typed commands, surgical
undo/redo replay, comprehensive scenario tests. The **application
shell** (file open/save, dirty state, recent files, close-confirm)
is still scaffolded — Phase 4 is the next blocking milestone. UX
polish and the remaining test matrix are queued for Phases 5 and 6.
