# Editable-Tree-Model-Example — repo map

_Last scanned: 2026-04-26. Phases 0–5 are shipped (all sub-phases of
Phase 5 included). Phase 6 testing is partial. **401 tests pass** under
`QT_QPA_PLATFORM=offscreen pytest -q` in ~3 s; no teardown segfault._

## 1) What this repo is

A PySide6 desktop app that started life as Qt's **Editable Tree Model**
example and has been rewritten into a real **structured-data editor**.
After Phases 0–5 it provides:

- a tabbed multi-document shell with file open / save / save-as / recent
  files / close-confirm / persisted view state
  (`ui.py`, `json_tab.py`, `view_state.py`, `file_io.py`, `settings.py`)
- a JSON-centric tree model/view stack with type-aware editing
  (`tree_model.py`, `tree_item.py`, `delegate.py`, `enums.py`)
- typed `QUndoCommand`-based undo/redo with `mergeWith` on consecutive
  same-path edits, plus a `QUndoView` history dialog
- a clipboard / cut / copy / paste / duplicate / move / sort tree
  action layer routed through the typed undo stack (`tree_view.py`)
- a debounced recursive name+value filter proxy
  (`tree_filter_proxy.py`) with Ctrl+F focus binding
- font zoom (Ctrl+= / Ctrl+- / Ctrl+0) persisted per file
- a permanent status-bar breadcrumb (`$.foo.bar[2].baz (string, 24 chars)`)
  plus transient action messages
- presentational `ValueDelegate.displayText` / `initStyleOption` for
  PERCENT / mpq / bytes-typed cells, with `ToolTipRole` carrying full
  text for long values
- reusable custom editor widgets (`qhexedit`, `qmultiline_editor`,
  `datetime_editor`, `qbigint_spinbox`, `qmpq_spinbox`) and helper
  packages (`mpq2py`, `jsontream`, `coalesce`, `binary`, `qt2py`,
  `units`)

## 2) Runtime entrypoint and main window

### `main.py`
- Creates a `QApplication`.
- Instantiates `ui.MainWindow` with the optional CLI filename
  (defaulting to `data.yaml`).
- Resizes the window to `settings.WINDOW_DEFAULT_SIZE`.

### `ui.py` (~420 lines)
- `MainWindow(QMainWindow, Ui_MainWindow)`.
- `setup_model(filename)` opens the file via `_open_path`; no-op on
  empty string (so test fixtures can pass `""`).
- `_setup_history_menu` adds a `History` menu with Undo / Redo /
  `Show History…` (a `QUndoView` dialog bound to the active tab's
  `QUndoStack`).
- `_bind_undo_signals(tab)` wires `canUndoChanged` / `canRedoChanged`
  for the current tab and the history dialog.
- `_add_tab(data, file_path)` creates a `JsonTab` with `show_root=True`,
  expands all, calls `view_state.restore`, sets focus to the synthetic
  root row.
- File menu: `New`, `Open` (`open_file_dialog`), `Save` (`save_file`),
  `Save As` (`save_file_as`), `Recent` submenu (cap 8, persisted via
  `QSettings(APPLICATION_ID, "app")`), `Quit`.
- View menu: `Expand All`, `Collapse All`, `Zoom In`, `Zoom Out`,
  `Reset Zoom`.
- Actions menu: insert before / insert after / remove row.
- `close_tab(index)` and `closeEvent` route through `_confirm_close`
  (Save / Discard / Cancel) and call `view_state.save` per tab.
- `update_actions()` enables Save / SaveAs / View actions when a tab
  exists; insert/remove require a valid current index.
- `copy_action()` is a real action delegating to
  `tree_view.copy_selection`.

### `mainwindow.ui` / `mainwindow.py`
- Designer XML / generated. Declares `fileOpenAction`, `fileSaveAction`,
  `fileSaveAsAction`, `fileCreateNewAction`, `appExitAction`,
  `rowInsertAction`, `rowInsertAfterAction`, `rowRemoveAction`,
  `viewExpandAllAction`, `viewCollapseAllAction`, `viewZoomInAction`,
  `viewZoomOutAction`, `viewResetZoomAction`, `actionsMenu`, `fileMenu`,
  `viewMenu`. Never hand-edit `mainwindow.py`.

### `settings.py`
- `APPLICATION_ID` (UUID-namespaced for `QSettings`).
- `WINDOW_DEFAULT_SIZE`, `MODAL_WINDOW_SIZE`.
- `IntegerInfo / FloatInfo / MultiLineInfo / SingleLineInfo` `StrEnum`s.

## 3) Per-tab editor — `json_tab.py` (~1050 lines)

`class JsonTab(QWidget)`. Single source of truth for one document.

Key responsibilities:
- Holds the source `JsonTreeModel`, a `TreeFilterProxy`, three column
  delegates (`NameDelegate` col 0, `JsonTypeDelegate` col 1,
  `ValueDelegate` col 2), and a `QUndoStack`.
- Constructor: `data` / `file_path` / `show_root` /
  `update_actions_callback` / `status_message_callback` /
  `permanent_message_callback`. When `data is _DEFAULT_DATA`, falls
  back to a built-in demo dictionary (legacy compatibility for tests
  that call bare `JsonTab(...)`); explicit `data={}` gives an empty
  document.
- Owns the `search_edit` `QLineEdit` (debounced 150 ms via `QTimer`),
  bound shortcuts: `Ctrl+F`, `Ctrl+C/X/V`, `Del`, `Ctrl+D`, `Alt+↑/↓`,
  `Ctrl+Alt+S`, `Ctrl+= / Ctrl+- / Ctrl+0`.
- Typed-command push API: `push_move_row`, `push_rename`,
  `push_edit_value`, `push_change_type`, `push_insert_rows`,
  `push_remove_rows`, `push_sort_keys`. `commit_set_data(index, value,
  role)` is the single delegate-side mutation entry point and dispatches
  by column.
- Typed `QUndoCommand` subclasses (one per mutation kind):
  `_MoveRowCmd`, `_RenameCmd`, `_EditValueCmd`, `_ChangeTypeCmd`,
  `_InsertRowsCmd`, `_RemoveRowsCmd`, `_SortKeysCmd`. `_RenameCmd` and
  `_EditValueCmd` implement `id()` (signed-int32-safe constants) plus
  `mergeWith` that collapses consecutive same-path edits within a
  500 ms window.
- `_diff_apply` family (`_diff_object`, `_diff_array`,
  `_convert_container`, `_convert_to_leaf`) replays undo/redo with
  surgical Qt model signals; expansion + selection survive.
- Proxy-aware path helpers: `_proxy_to_source`, `_source_to_view`,
  `_index_path`, `_index_from_path`, `_qualified_name` (returns
  JSON-style `$.foo.bar[2]` paths).
- Dirty state: tied to `undo_stack.cleanChanged`. `dirtyChanged(bool)`
  signal updates `MainWindow` tab title (`*` suffix). `is_dirty`
  property; `display_name()` formats the title.
- File I/O helpers: `save()` (uses stored `save_format` if set, else
  detects from extension); `save_as(path=None)` opens
  `QFileDialog.getSaveFileName` with four format filters.
- Status callbacks: `_status_message_callback` for transient action
  messages; `_permanent_message_callback` for the breadcrumb that
  follows `currentChanged`.
- `_size_hint_for_item` computes a size hint per JsonType
  (text/object/array/bytes-family).
- Font zoom: `_font_pt` clamped 6..48; `zoom_in / zoom_out / zoom_reset`.
- `_collect_expanded_paths()` enumerates currently-expanded rows for
  `view_state.save`.
- `_on_type_changed`: closes any persistent value editor; if the
  underlying combo commit was interactive (per `JsonTypeDelegate.
  _interactive`) defers `view.edit(value_index)` via
  `QTimer.singleShot(0, ...)`.

## 4) Tree data layer

### `tree_model.py` — `JsonTreeModel`
- `QAbstractItemModel` over a single `root_item: JsonTreeItem`.
- Three fixed columns: `Name`, `Type`, `Value`.
- `show_root: bool` exposes the synthetic root row in the view
  (used by `MainWindow` so the user can edit the root container).
- `flags()` is data-aware (column 0 editable only under OBJECT parents;
  column 1 always editable; column 2 keyed off cached
  `JsonTreeItem.editable`).
- `data(index, role)`:
  - `EditRole` returns the raw value (`mpq`, `int`, `bool`, `None`,
    bytes-as-base64-str, …) for round-trip with editors.
  - `DisplayRole` keeps a stringified path for non-delegate clients
    (lowercase `true/false`, `null`, `mpq_serialization` for mpq).
  - `JSON_TYPE_ROLE = UserRole + 1` returns `item.json_type` for col 2;
    consumed by `ValueDelegate.initStyleOption` to format
    PERCENT / BYTES / ZLIB / GZIP cells without re-parsing.
  - `ToolTipRole` for col 2 returns the full value capped at 4 KB +
    ellipsis when the raw text exceeds 80 chars.
  - `FontRole` italicizes col 0 names that contain non-ASCII.
- `setData` routes through `JsonTreeItem.set_data` (col 0/2) or
  `change_type` (col 1, with `typeChanged(QModelIndex, lossy:bool)`
  signal).
- Mutation helpers used by typed commands: `move_row`, `change_type`,
  `sort_keys` (recursive option), `insertRows` / `removeRows`
  (context-managed `beginInsert*` / `beginRemove*`).
- Column insert/remove API was deleted in Phase 1.

### `tree_item.py` — `JsonTreeItem` (~340 lines)
- One JSON node. Stores `name`, `value`, `parent_item`, `child_items`,
  cached `editable`, lazy cached `row()` index, and `explicit_type`
  flag for user-pinned types.
- Recursively expands `dict` → OBJECT, `list` → ARRAY.
- `set_data(column, value)` is total across columns 0/1/2, with a
  coercion table (`_coerce_value_for_type`) for cross-type edits.
- Validates names under OBJECT parents (no duplicates / no empty).
- `_unique_child_name(base="new_key", used_names=None)` generates
  `new_key`, `new_key_2`, … suffixes.
- `to_json()` rebuilds Python primitives; raises `ValueError` for any
  remaining unnamed OBJECT child.
- `mark_children_dirty` / `_normalize_value_for_type` /
  `_apply_typed_value` / `_compute_editable` are the surgical
  mutators called by `_diff_apply`.

### `enums.py` — `JsonType` + type detection (~180 lines)
- `JsonType`: integer, float, percent, boolean, string, unicode,
  multiline, text, date, time, datetime, datetime-with-timezone,
  bytes, zlib, gzip, object, array, null.
- `parse_json_type(value)` is **total**: returns `STRING` with a logger
  warning for unknown types (no exception).
- Heuristics: floats / mpq in `[0,1]` → PERCENT; other floats / mpq →
  FLOAT.
- `_looks_like_base64` requires syntactic validity; datetime is
  checked before bytes.
- Text-axis helpers: `infer_text_json_type`, `text_pseudotype_for`,
  `TEXT_FAMILY` (single-line vs multiline x ascii-only vs unicode).

## 5) Editing/delegate layer — `delegate.py` (~430 lines)

### `ValueDelegate(_TextEditorDelegateBase)`
Editors per JsonType:
- INTEGER → `QBigIntSpinBox`
- FLOAT / PERCENT → `QMpqSpinBox` (PERCENT gets `0..100 %` UI but
  stores `0..1` mpq)
- BOOLEAN → `QComboBox`
- STRING / UNICODE → `_CapsLockSafeLineEdit`
  (`_TextEditorDelegateBase` swallows lock-key `KeyPress` and
  layout-switch `FocusOut` events to keep the editor open)
- DATE / TIME / DATETIME / DATETIMEZONE → `BetterDateTimeEditor`
- MULTILINE / TEXT → modal `QMultilineDialog`, commit via
  `QPersistentModelIndex` + `_commit` → `JsonTab.commit_set_data`
- BYTES / ZLIB / GZIP → modal `QHexDialog`; decode wrapped in
  `try/except (ValueError, OSError, zlib.error, binascii.Error)`,
  failures surface via `_notify_status` (status-bar callback)

`initStyleOption` reads `EditRole` + `JSON_TYPE_ROLE` and sets
`option.text` to a type-aware formatted string (PERCENT → `"50%"`,
BYTES-family → `"<24 byte>"`, mpq → decimal form, long strings
elide to 80 chars).

### `JsonTypeDelegate(QStyledItemDelegate)`
- Combo box of all `JsonType` entries; preselects the current type via
  `findData`.
- `_interactive` flag set during `setModelData`; commit routes through
  `JsonTab.commit_set_data` if a tab ancestor exists.

### `NameDelegate(_TextEditorDelegateBase)`
- `_CapsLockSafeLineEdit` for col 0 rename. Commit routes through
  `ValueDelegate._commit` so renames land on the typed undo stack.

### Helpers
- `decode_bytes(b64string, json_type)` / `encode_bytes(data, json_type)`
  round-trip BYTES/ZLIB/GZIP payloads.

## 6) Tree view actions / clipboard — `tree_view.py` (~630 lines)

`show_context_menu(tree_view, position)` builds an outliner-style menu:

- Copy (Ctrl+C), Cut (Ctrl+X), Paste (Ctrl+V), Delete (Del)
- Duplicate (Ctrl+D)
- Move Up (Alt+↑) / Move Down (Alt+↓)
- Sort Keys / Sort Keys (Recursive)
- Insert Sibling Before / After
- Insert Child (only when current row is OBJECT/ARRAY)
- Expand All / Collapse All

Each action is proxy-aware via `_resolve_model` / `_to_source_index` /
`_to_view_index`, then either:
- routes through `JsonTab.push_*` typed helpers (when the view's parent
  is a `JsonTab`), or
- falls back to `model_actions.py` direct helpers for non-tab hosts.

Clipboard MIME format is `application/x-json-tree`; the JSON-tree
metadata payload preserves names so paste keeps full type info.
Name-collision avoidance under OBJECT parents during paste/duplicate
uses `_copy_name` / `_unique_child_name`, generating `_copy`,
`_copy_2`, … suffixes.

`expand_all(view)` / `collapse_all(view)` are thin wrappers used by the
context menu and the View menu.

## 7) Filter proxy — `tree_filter_proxy.py`

`TreeFilterProxy(QSortFilterProxyModel)`:
- `setRecursiveFilteringEnabled(True)` keeps ancestors of matches
  visible.
- `set_filter_text(text)` normalizes (strip + casefold) and calls
  `invalidate()`.
- `filterAcceptsRow` matches the needle against `name` for every row;
  for leaves, also against the value text. Container nodes pass when
  any descendant passes.

## 8) View state — `view_state.py`

- `state_key(path)` → `"view_state/<sha1[:16]>"` keyed off the resolved
  absolute path.
- `save(tab)` persists column widths, expanded paths,
  current-selection path, and `_font_pt` under `QSettings(APPLICATION_ID,
  "view_state")`.
- `restore(tab)` returns `True` when any state was found and applied;
  callers fall back to defaults (`expandAll` + `resizeColumnToContents`)
  on `False`.
- `discard(path)` removes the group on `Save As` to a new path.
- Hard cap `MAX_EXPANDED_PATHS = 5000`. Coercion helpers handle
  `QSettings`'s platform-dependent shapes (list of ints, string with
  `/` or `,` separators).

## 9) File I/O — `file_io.py`

- Format constants: `SAVE_FORMAT_JSON / JSONL / YAML / YAML_MULTI`.
- `detect_format(path)` dispatches by extension (`.json`, `.jsonl`,
  `.ndjson`, `.yaml`, `.yml`).
- `load_file_with_format(path)`:
  - JSON / JSONL → `simplejson.load(parse_float=mpq)` /
    line-by-line `loads`.
  - YAML → `yaml.load_all(MpqSafeLoader)`; returns a list with the
    `YAML_MULTI` marker when there is more than one document.
- `dump_text(path, data, save_format)`:
  - JSON → `simplejson.dumps(default=mpq_json_default, indent=2,
    use_decimal=True)`.
  - JSONL → one `dumps` per row.
  - YAML / YAML_MULTI → `yaml.dump` / `yaml.dump_all` with
    `MpqSafeDumper`.
- `atomic_write(path, text)` uses `os.replace` for cross-platform
  atomic rename.

## 10) Toolbar / menu insert helpers — `model_actions.py`

Direct-mutation helpers used as fallbacks when the view has no
`JsonTab` parent:
- `_copy_name(base, used)` for paste/duplicate name suffixes.
- `action_insert_row_before / _after`, `action_insert_child`,
  `action_duplicate`, `action_move_up / _down`, `action_sort_keys`.
- The toolbar/menu paths in `MainWindow` go through `JsonTab` typed
  commands; `model_actions.py` is mostly dormant in app flow but kept
  as a stable API for headless tests.

## 11) Custom widgets and support packages

### `datetime_editor/`
- `BetterDateTimeEditor` (segment stepping, partial regex / partial
  input support, timezone editing). `regex.py` / `validator.py` /
  `enums.py` back the parser.

### `qhexedit/`
- `QHexEdit` over `QIODevice` chunks; selection / overwrite / insert
  modes; ASCII zone; clipboard; undo; modified-byte highlighting;
  theming via `ColorManager`.

### `dialogs/`
- `qhexedit_dlg.QHexDialog` — modal hex editor with `QSettings`
  persistence.
- `qmultiline_dlg.QMultilineDialog` — modal multiline editor with
  word-wrap / line-numbers / monospaced toggles.

### `qmultiline_editor.py`
- `QPlainTextEdit` derivative used by the multiline dialog.

### Numeric editors
- `qbigint_spinbox.QBigIntSpinBox` — arbitrary-precision integer.
- `qmpq_spinbox.QMpqSpinBox` — exact rational using `gmpy2.mpq` and
  `mpq2py.mpq_serialization` for stable display.

### Helpers
- `mpq2py/` — `mpq_serialization`, `mpq_json_default`,
  `MpqSafeLoader`, `MpqSafeDumper`.
- `jsontream/` — streaming JSON encoder wrapper supporting iterables.
- `units/` — `bits` / `format_bytes` size formatting.
- `coalesce/`, `binary/`, `qt2py/` — small utility packages.

### `header_view_editor.py`
- `HeaderViewEditorMixin` — currently unused by `JsonTab` (commented
  out). Kept for future column header editing.

## 12) Tests (401 passing as of 2026-04-26)

Editor / phase suites:
- `test_smoke_model.py`, `test_smoke_mainwindow.py`,
  `test_tree_correctness.py`, `test_type_editing.py`,
  `test_tree_actions_clipboard.py`, `test_tree_actions_structure.py`,
  `test_undo_redo.py`, `test_undo_redo_scenario.py`,
  `test_typed_undo_commands.py`, `test_typed_undo_perf.py`,
  `test_perf_smoke.py`, `test_file_io_phase4.py`,
  `test_phase_5_1_carryover.py`, `test_phase_5_2_display_formatting.py`,
  `test_phase_5_3_status_bar_breadcrumb.py`,
  `test_phase_5_4_persisted_view_state.py`,
  `test_phase_5_5_search_filter.py`,
  `test_phase_5_6_misc_polish.py`.

Pre-existing widget-stack suites: `test_better_datetime_buffer`,
`test_datetime_editor`, `test_dialog_settings`, `test_jsontream`,
`test_mpq2py`, `test_partial_float_re`, `test_partial_regex`,
`test_pretty_jsontream`, `test_qhexedit_highlighting`, `test_units`,
`test_validator`.

`pytest -q` baseline (2026-04-26): **401 tests pass in ~3 s** under
`QT_QPA_PLATFORM=offscreen`. No teardown segfault.

## 13) Sample data

- `data.yaml` / `data.json` / `data.jsonl` / `data-multidoc.yaml` /
  `john-doe.yaml` — multi-format fixtures for manual smoke + future
  Phase 6 round-trip tests.

## 14) Dependencies / tooling

### Python (`requirements.txt`)
- `PySide6==6.11.0`
- `PyYAML==6.0.3`
- `python-dateutil==2.9.0.post0`
- `gmpy2==2.3.0`
- `pytest==9.0.3`
- `tzdata==2026.2`

`simplejson` is imported by `file_io.py` and `tree_view.py` but is not
yet pinned in `requirements.txt`. `pytest-qt` is also not pinned;
smoke tests roll their own `QApplication` fixture.

### `Makefile`
- `autoflake .`
- `isort . --extend-skip mainwindow.py`
- `black . --line-length 120 --extend-exclude mainwindow.py`
- A `make test` target running
  `QT_QPA_PLATFORM=offscreen pytest -q` is still queued for Phase 6.

### `pytest.ini`
- `pythonpath = .`

## 15) Suggested reading order for future work

1. `main.py`
2. `ui.py`
3. `json_tab.py` — typed commands, push API, `_diff_apply`, dirty
   state, breadcrumb, font zoom.
4. `tree_model.py` — `data` / `setData` / `change_type` / `move_row` /
   `sort_keys` / `JSON_TYPE_ROLE`.
5. `tree_item.py` — `set_data`, `_coerce_value_for_type`,
   `_unique_child_name`.
6. `enums.py` — `parse_json_type`, text family heuristics.
7. `delegate.py` — editors per type, `initStyleOption` formatting,
   `_commit` routing, dialog-edit `QPersistentModelIndex` flow.
8. `tree_view.py` — context menu, clipboard, action wiring, proxy
   mapping helpers.
9. `tree_filter_proxy.py` — recursive filter.
10. `view_state.py` — persisted column widths / expansion / current /
    font zoom.
11. `file_io.py` — JSON / JSONL / YAML / YAML-multi load + save +
    atomic write.
12. `model_actions.py` — fallback direct mutations for headless tests.
13. `datetime_editor/better_dt_editor.py`
14. `qhexedit/__init__.py`

## 16) Practical mental model

- **Shell layer** — `main.py` → `ui.py` / `mainwindow.ui` /
  `view_state.py` / `file_io.py` / `settings.py`
- **Tab layer** — `json_tab.py` (owns `QUndoStack`, typed-command
  push API, search proxy hookup, breadcrumb plumbing)
- **Tree data** — `tree_model.py` + `tree_item.py` + `enums.py`
- **Filter** — `tree_filter_proxy.py`
- **Editing** — `delegate.py` (+ `dialogs/`, `qmultiline_editor.py`)
- **Actions / clipboard** — `tree_view.py` + `model_actions.py`
- **Advanced editor widgets**:
  - datetime → `datetime_editor/`
  - binary → `qhexedit/` + `dialogs/qhexedit_dlg.py`
  - multiline text → `qmultiline_editor.py` +
    `dialogs/qmultiline_dlg.py`
  - exact numerics → `qbigint_spinbox/`, `qmpq_spinbox/`,
    `mpq2py/`
- **Utilities / tests** — `jsontream/`, `units/`, `qt2py/`,
  `coalesce/`, `binary/`, `tests/`

After Phase 5 the editor is functionally complete for daily use:
multi-document file I/O, undo/redo with merge, persistent layout,
search, and pretty rendering. The remaining surface area is the
Phase 6 test matrix and a small set of stretch UX items (type icons,
match highlight).
