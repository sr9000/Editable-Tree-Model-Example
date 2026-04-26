# Editable-Tree-Model-Example — repo map

_Last scanned: 2026-04-26 (Phases 0–3 complete; 343 tests pass.)_

## 1) What this repo is

A PySide6 desktop app that started life as Qt's **Editable Tree Model**
example and has been rewritten into a real **structured-data editor**.
Compared with the original example, the in-tree code now provides:

- a tabbed multi-document shell (`ui.py` + `json_tab.py`)
- a JSON-centric tree model/view stack with type-aware editing
  (`tree_model.py`, `tree_item.py`, `delegate.py`, `enums.py`)
- typed `QUndoCommand`-based undo/redo (no whole-document snapshots)
- a clipboard / cut / copy / paste / duplicate / move / sort tree
  action layer (`tree_view.py`)
- several reusable custom editor widgets (`qhexedit`,
  `qmultiline_editor`, `datetime_editor`, `qbigint_spinbox`,
  `qmpq_spinbox`) and helper packages (`mpq2py`, `jsontream`,
  `coalesce`, `binary`, `qt2py`, `units`)

File I/O (open / save / dirty-state / recent-files) is the next
milestone — see `ai-memory/phases/phase-4-file-io.md`. The runtime
still seeds new tabs with a hardcoded demo dict instead of loading
`data.json` / `data.yaml` from disk.

## 2) Current app entry flow

### Runtime entrypoint
- `main.py`
  - creates `QApplication`
  - instantiates `ui.MainWindow`
  - passes a filename argument (defaulting to `data.yaml`) — currently
    a no-op until Phase 4 lands.
  - resizes window using `settings.WINDOW_DEFAULT_SIZE`

### Main window layer
- `ui.py` (~230 lines, slimmed down in Phase 0)
  - subclasses generated `mainwindow.Ui_MainWindow`
  - `create_new_file()` opens an empty `JsonTab` in `tabWidget`
  - `close_tab(index)` removes a tab and `deleteLater()`s it (no
    dirty-confirm yet — added in Phase 4)
  - `_current_tab()` / `_current_view()` resolve the active tab
  - `setup_model()` and `update_actions()` are deliberate stubs until
    Phase 4
  - all original C++ reference docstrings have been deleted

### Per-tab editor
- `json_tab.py` (~760 lines)
  - hosts a `QTreeView` plus `JsonTreeModel`, with column delegates
    (col 1 → `JsonTypeDelegate`, col 2 → `ValueDelegate`)
  - owns a `QUndoStack` (Phase 3) — every tree action goes through it
  - exposes the **typed-command push API**: `push_move_row`,
    `push_rename`, `push_edit_value`, `push_change_type`,
    `push_insert_rows`, `push_remove_rows`, `push_sort_keys`
  - `commit_set_data(index, value, role)` dispatches by column and is
    the single delegate-side mutation entry point
  - declares `_MoveRowCmd`, `_RenameCmd`, `_EditValueCmd`,
    `_ChangeTypeCmd`, `_InsertRowsCmd`, `_RemoveRowsCmd`,
    `_SortKeysCmd` — each stores only the affected subset (parent
    path + ints, or path + old/new subtree)
  - `_diff_apply()` family (`_diff_object`, `_diff_array`,
    `_convert_container`, `_convert_to_leaf`) replays undo/redo with
    surgical Qt model signals — no `beginResetModel`, view expansion
    and selection survive
  - still seeds the model with hardcoded demo data (Phase 4 will
    replace this with a `data` ctor argument)

## 3) Core JSON/tree architecture

### `tree_model.py` — `JsonTreeModel`
Tree model on top of `QAbstractItemModel`.

Responsibilities:
- holds `root_item: JsonTreeItem`
- exposes 3 fixed columns: `Name`, `Type`, `Value`
- column-insert/remove API was deleted in Phase 1 (was always-False
  dead code)
- `flags()` is data-aware: editing is disabled for `null`, arrays,
  objects, and oversize (>10 KB) blobs; the underlying `editable` flag
  is cached on `JsonTreeItem` and recomputed only on construction or
  `_apply_typed_value`, so `flags()` stays cheap
- `setData` routes through `JsonTreeItem.set_data`, which is total
  across all three columns (rename / type / value)
- emits typed signals: `dataChanged`, `rowsInserted`, `rowsRemoved`,
  `rowsMoved`, plus a custom `typeChanged(index)` for delegate
  reactions
- exposes mutation helpers used by typed commands: `move_row`,
  `change_type`, `sort_keys`, `_unique_child_name`

### `tree_item.py` — `JsonTreeItem`
Represents one JSON node.

Behavior:
- `json_type` resolved via `enums.parse_json_type`; user override is
  preserved through `explicit_type`
- stores `name`, `value`, `parent_item`, `child_items`, plus cached
  `editable` and a lazy cached `row()` index
- recursively expands `dict` → `OBJECT`, `list` → `ARRAY`
- `set_data(column, value)` is total across columns 0/1/2 with a
  coercion table (`_coerce_value_for_type`) for cross-type edits and
  validates names under OBJECT parents
- `to_json()` rebuilds Python primitives; raises `ValueError` for any
  remaining unnamed OBJECT child

### `enums.py` — `JsonType` + type detection
- `JsonType`: integer, float, string, boolean, object, array, null,
  percent, multiline, date, time, datetime, datetime-with-timezone,
  bytes, zlib, gzip
- `parse_json_type()` is **total** (returns STRING with a logger
  warning for unknown values) and uses narrowed heuristics:
  - datetime checked before bytes
  - `_looks_like_base64` requires length ≥ 16, valid regex, and
    < 0.85 printable-byte ratio
  - PERCENT auto-detection was removed — only reachable via explicit
    type pinning

## 4) Editing/delegate layer — `delegate.py`

### `ValueDelegate`
Editor by `JsonType`:
- INTEGER → `QBigIntSpinBox`
- FLOAT → `QMpqSpinBox`
- PERCENT → `QMpqSpinBox` configured 0..100 %
- BOOLEAN → `QComboBox`
- STRING → `QLineEdit`
- DATE / TIME / DATETIME / DATETIME_TZ → `BetterDateTimeEditor`
- MULTILINE → modal `QMultilineDialog`
- BYTES / ZLIB / GZIP → modal `QHexDialog`

Helpers `decode_bytes()` / `encode_bytes()` round-trip the binary
payload variants.

Open issues (Phase 5 carry-over from Phase 3):
- modal-dialog branches still capture raw `QModelIndex` and call
  `model.setData` directly; should switch to `QPersistentModelIndex`
  and route through `JsonTab.commit_set_data` so dialog edits land on
  the typed undo stack
- malformed `ZLIB` / `GZIP` payloads can raise from inside
  `createEditor` before the dialog is shown

### `JsonTypeDelegate`
- combo box of `JsonType` entries; populates in `createEditor`
- `setEditorData` preselects the current type via `findData`
- `setModelData` commits via `model.setData(index, json_type)`
- type change is fully wired into the undo stack via
  `JsonTab.push_change_type` (Phase 3); auto-reopen of the value
  editor after a user-driven type change is deferred to Phase 5

## 5) Tree view actions / context menu — `tree_view.py`

`show_context_menu(tree_view, position)` builds an action set that now
mirrors a real outliner:

- Cut (Ctrl+X), Copy (Ctrl+C), Paste (Ctrl+V), Delete (Del)
- Duplicate (Ctrl+D)
- Move Up (Alt+↑) / Move Down (Alt+↓)
- Insert Sibling Before / After
- Insert Child
- Sort Keys (Ctrl+Alt+S, recursive option in submenu)

Each action calls a typed `JsonTab.push_*` helper when the view's
parent is a `JsonTab`, falling back to a direct model mutation
otherwise.

Other helpers:
- `to_json(item)` uses `jsontream.StreamingJSONEncoderWrapper`
- `application/x-json-tree` MIME is used for the clipboard so
  copy-paste round-trips full type information
- name-collision avoidance under OBJECT parents during paste /
  duplicate generates `_copy`, `_copy_2`, … suffixes

`model_actions.py` still exists and provides
`action_insert_row` / `action_insert_child` for the toolbar /
menu-bar paths that haven't been migrated to typed helpers yet.
`action_insert_column` was removed in Phase 1.

## 6) Main UI / generated files

### `mainwindow.ui`
Qt Designer XML. Currently declares (among others):
`fileOpenAction`, `fileSaveAction`, `fileSaveAsAction`,
`fileCreateNewAction`, `appExitAction`, `rowInsertAction`,
`rowInsertAfterAction`, `rowRemoveAction`, plus an `actionsMenu`.
Phase 4 wires the file-related ones; Phases 5+ may add a `View` menu
for zoom / collapse-all.

### `mainwindow.py`
Auto-generated from `mainwindow.ui` — never hand-edit.

### `ui.py`
Hand-written integration layer. Post Phase 0 cleanup:
- C++ docstring blocks removed
- unused imports (`yaml`, `functools`, `HeaderViewEditorMixin`, …)
  removed
- `copy_action` placeholder superseded by per-tab clipboard handling
- toolbar action handlers route through `_current_tab()` /
  `_current_view()` helpers

## 7) Custom widgets and support packages

### `datetime_editor/`
Permissive but structured date/time text editing. The actively used
implementation is `better_dt_editor.BetterDateTimeEditor` (segment
stepping, full regex/partial-input support, timezone editing). Older
`DateTimeEditor` wrapper remains in `__init__.py`.

### `qhexedit/`
The largest custom widget package: `QHexEdit` over `QIODevice` chunks,
selection / overwrite / insert modes, ASCII zone, clipboard, undo,
modified-byte highlighting, theming via `ColorManager`.

### `dialogs/`
- `qhexedit_dlg.py` — `QHexDialog` with `QSettings` persistence
- `qmultiline_dlg.py` — `QMultilineDialog` with word-wrap / line
  numbers / monospaced toggles persisted via `QSettings`

### `qmultiline_editor.py`
`QPlainTextEdit` derivative with line-number gutter and toggles.

### Numeric editors
- `qbigint_spinbox/` — exact integer spin box (Python `int`)
- `qmpq_spinbox/` — exact rational spin box (`gmpy2.mpq`), uses
  `mpq2py.mpq_serialization` for stable display

### Helpers
- `mpq2py/` — `mpq_serialization`, `mpq_json_default`, YAML
  loader/dumper for `mpq`
- `jsontream/` — streaming JSON encoder wrapper supporting iterables
- `coalesce/`, `binary/`, `qt2py/`, `units/` — small utility packages

## 8) Tests and what they cover

`pytest -q` baseline (2026-04-26): **343 tests pass in ~1 s** under
`QT_QPA_PLATFORM=offscreen`.

JSON-editor specific suites delivered in Phases 0–3:

- `tests/test_smoke_model.py` — model construction smoke
- `tests/test_smoke_mainwindow.py` — `MainWindow` lifecycle, status
  bar, multi-tab open/close, type-change regressions
- `tests/test_tree_correctness.py` — insertion semantics, naming,
  `to_json` strictness, narrower `parse_json_type`, malformed binary
  `flags()` safety, dead column API, `action_insert_child`
- `tests/test_type_editing.py` — name editing under OBJECT/ARRAY,
  type-change coercion, type pinning, `JsonTypeDelegate` preselection
- `tests/test_tree_actions_clipboard.py` — copy / cut / paste round
  trips with collision-suffix naming
- `tests/test_tree_actions_structure.py` — duplicate, move up/down,
  insert sibling/child, sort keys
- `tests/test_undo_redo.py` — per-action undo/redo + label format
- `tests/test_undo_redo_scenario.py` — 16-step end-to-end scenario
  covering every JsonType + every mutating action with branched
  undo/redo
- `tests/test_typed_undo_commands.py` — every routine action pushes
  the correct typed `QUndoCommand` subclass
- `tests/test_typed_undo_perf.py` — wall-clock + per-command state
  size bounds
- `tests/test_perf_smoke.py` — 3000-row fan-out perf bound

Pre-existing widget-stack suites continue to cover `datetime_editor`,
`qhexedit`, `mpq2py`, `jsontream`, dialog `QSettings`, units, regex /
partial input.

## 9) Status of the unfinished surface (post Phase 3)

The "transitional" list from earlier scans has shrunk substantially.
Remaining gaps map to Phases 4–6:

1. **File I/O** — `MainWindow.setup_model()`, open/save/save-as,
   dirty-state, recent files, close-confirm dialog. (Phase 4.)
2. **`JsonTab` data ingest** — replace the hardcoded demo dict with a
   `data` ctor argument and remove the `base64` / `gzip` / `zlib` /
   `gmpy2` import-only-for-demo lines. (Phase 4.)
3. **`displayText` / status bar / persisted view state /
   search-filter** — none of the cosmetic UX layer exists yet.
   (Phase 5.)
4. **Auto-reopen value editor after user-driven `typeChanged`,
   `mergeWith` for consecutive same-cell edits, dialog-delegate
   `QPersistentModelIndex` + `commit_set_data` routing** — Phase 3
   carry-overs collected in Phase 5.
5. **Coverage gaps** — model invariants (`removeRows` persistent
   indices, `parent`/`index` round-trip), full delegate matrix tests,
   round-trip tests against `data.json` / `data.yaml`. (Phase 6.)

## 10) Data/sample files

- `data.yaml`
- `data.json`

These are currently inert at runtime (not yet loaded by any code path)
but are kept around as Phase 4 fixtures and for round-trip tests.

## 11) Dependencies / tooling

### Python dependencies (`requirements.txt`)
- `PySide6==6.11.0`
- `PyYAML==6.0.3`
- `python-dateutil==2.9.0.post0`
- `gmpy2==2.3.0`
- `pytest==9.0.3`
- `tzdata==2026.2`

`pytest-qt` is *not yet* in `requirements.txt`; some Phase 6 tests
already use a hand-rolled `qapp` fixture but adding the dependency is
listed in `phase-6-tests.md`.

### Formatting / linting (`Makefile`)
- `autoflake .`
- `isort . --extend-skip mainwindow.py`
- `black . --line-length 120 --extend-exclude mainwindow.py`

A `make test` target running `QT_QPA_PLATFORM=offscreen pytest -q` is
listed under Phase 6 tooling work.

### Pytest config
- `pytest.ini` sets `pythonpath = .`

## 12) Suggested reading order for future work

1. `main.py`
2. `ui.py`
3. `json_tab.py` — typed commands + push API + `_diff_apply`
4. `tree_model.py` — `setData` / `move_row` / `change_type` /
   `sort_keys` / `_unique_child_name`
5. `tree_item.py` — `set_data` total table + `_coerce_value_for_type`
6. `enums.py` — `parse_json_type` heuristics
7. `delegate.py` — `ValueDelegate` + `JsonTypeDelegate`
8. `tree_view.py` — context menu, clipboard, action wiring
9. `model_actions.py` — toolbar/menu insert helpers
10. `datetime_editor/better_dt_editor.py`
11. `qhexedit/__init__.py`

## 13) Practical mental model

- **Shell / UI layer**: `main.py` → `ui.py` / `mainwindow.ui`
- **Tab layer**: `json_tab.py` (owns the `QUndoStack` and the typed
  push API)
- **Tree data layer**: `tree_model.py` + `tree_item.py` + `enums.py`
- **Editing layer**: `delegate.py`
- **Actions layer**: `tree_view.py` + `model_actions.py`
- **Advanced editor widgets**:
  - datetime → `datetime_editor/`
  - binary → `qhexedit/` + `dialogs/qhexedit_dlg.py`
  - multiline text → `qmultiline_editor.py` +
    `dialogs/qmultiline_dlg.py`
  - exact numerics → `qbigint_spinbox/`, `qmpq_spinbox/`,
    `mpq2py/`
- **Utilities / tests**: `jsontream/`, `units/`, `qt2py/`, …

Today the tree-editor *itself* is functionally complete for in-memory
editing and undo/redo. The remaining surface area is wiring it up to
the file system (Phase 4) and polishing it for daily use (Phase 5),
with the model/delegate test matrix filled out alongside (Phase 6).
