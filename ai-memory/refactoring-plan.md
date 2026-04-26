# Refactoring plan — isolate independent logical blocks

_Created: 2026-04-26._

Goal: split the current large source files into smaller, cohesive modules
without changing user-visible behaviour. The project is already well layered;
the main opportunity is to turn several “god modules” into packages grouped by
responsibility while keeping compatibility imports during the transition.

Execution tracker: use `ai-memory/refactoring-phases.md` as the authoritative
one-commit-per-phase checklist. Every phase must update
`ai-memory/refactoring-test-log.md` with focused-test and full-suite state
before commit.

Current largest top-level files:

| File | Lines | Primary responsibilities |
| --- | ---: | --- |
| `json_tab.py` | 1046 | Per-document widget, undo commands, diff replay, save/load glue, view state helpers, action wrappers |
| `tree_view.py` | 630 | Context menu, selection helpers, clipboard MIME handling, paste/duplicate/move/sort actions |
| `delegate.py` | 433 | Value/name/type delegates, editor creation, display formatting, bytes encode/decode |
| `ui.py` | 421 | Main window shell, menus/actions, tab lifecycle, recent files, close-confirm, history dialog |
| `tree_item.py` | 339 | Tree node storage, type coercion, name validation, JSON conversion |
| `tree_model.py` | 280 | Qt model API, model mutation helpers, display/edit roles |

The safest strategy is package extraction with compatibility shims:

- keep old import paths such as `from json_tab import JsonTab` working at first;
- move independent helpers/classes into packages;
- re-export public names from the old files;
- run the full suite after every small extraction;
- only remove shims once all imports/tests are migrated.

---

## 1) Target package layout

Recommended target structure:

```text
app/
  __init__.py
  main_window.py              # MainWindow implementation, later replaces ui.py
  main_window_actions.py      # QAction/menu wiring and enable/disable state
  recent_files.py             # QSettings-backed recent-file list
  close_confirm.py            # Save / Discard / Cancel flow helpers
  history.py                  # Undo/redo menu + QUndoView dialog glue

documents/
  __init__.py
  tab.py                      # JsonTab public widget shell
  tab_setup.py                # layout/delegate/search/shortcut setup helpers
  tab_paths.py                # proxy/source mapping, index paths, qualified names
  tab_status.py               # breadcrumb + transient/permanent status formatting
  tab_io.py                   # save/save_as wrappers around file_io
  tab_view_state.py           # expanded-path collection and restore adapter if desired

undo/
  __init__.py
  commands.py                 # _MoveRowCmd, _RenameCmd, _EditValueCmd, etc.
  diff.py                     # _diff_apply, object/array diff replay helpers
  merge.py                    # shared merge-window/id constants if needed

tree/
  __init__.py
  item.py                     # JsonTreeItem, possibly still one class
  item_coercion.py            # value/type coercion table extracted from JsonTreeItem
  item_names.py               # unique-name and object-key validation helpers
  model.py                    # JsonTreeModel public model shell
  model_roles.py              # JSON_TYPE_ROLE and role/display helpers
  model_mutations.py          # move_row, sort_keys, change_type helpers if extractable
  types.py                    # JsonType + parse/infer helpers, later replaces enums.py
  filter_proxy.py             # TreeFilterProxy

delegates/
  __init__.py
  base.py                     # _CapsLockSafeLineEdit, _TextEditorDelegateBase
  value.py                    # ValueDelegate public class
  value_formatting.py         # displayText/initStyleOption formatting helpers
  value_editors.py            # createEditor/setEditorData/setModelData dispatch helpers
  type_delegate.py            # JsonTypeDelegate
  name_delegate.py            # NameDelegate
  bytes_codec.py              # decode_bytes / encode_bytes

tree_actions/
  __init__.py
  context_menu.py             # show_context_menu only
  selection.py                # selected/top-level rows, index path, ancestor checks
  clipboard.py                # MIME format, copy/cut payloads, JSON text fallback
  paste.py                    # paste_from_clipboard and name-collision logic
  structure.py                # insert/delete/duplicate/move/sort/expand/collapse actions
  fallback_model_actions.py   # current model_actions.py direct-mutation fallback helpers

io_formats/
  __init__.py
  detect.py                   # detect_format constants + extension mapping
  load.py                     # JSON/JSONL/YAML/YAML-multi load paths
  dump.py                     # dump_text and mpq-safe serialization
  atomic.py                   # atomic_write/save_file

state/
  __init__.py
  view_state.py               # current view_state.py
  qsettings_coercion.py       # _coerce_int/_coerce_path helpers
```

This layout separates application shell, document widget, undo/diff logic,
tree model/data, delegates, tree actions, file formats, and persisted state.

---

## 2) Refactoring principles

1. **Extract pure helpers first.** Move code that does not depend on `self`,
   Qt object ownership, or signals before moving QObject subclasses.
2. **Preserve public imports.** Initial shims should keep these stable:
   - `from json_tab import JsonTab`
   - `from tree_model import JsonTreeModel, JSON_TYPE_ROLE`
   - `from tree_item import JsonTreeItem`
   - `from delegate import ValueDelegate, JsonTypeDelegate, NameDelegate`
   - `from tree_view import copy_selection, paste_from_clipboard, show_context_menu, ...`
   - `from ui import MainWindow`
3. **Avoid circular imports by direction.** Suggested dependency direction:

   ```text
   app -> documents -> delegates/tree_actions/tree/io_formats/state
   documents -> undo -> tree
   delegates -> tree/types + editor widgets
   tree_actions -> tree + optional document-tab protocol
   tree -> tree/types
   io_formats -> mpq2py only
   state -> settings only
   ```

4. **Use narrow protocols instead of importing `JsonTab` everywhere.**
   For tree actions and delegates, depend on methods such as
   `commit_set_data`, `push_insert_rows`, `push_remove_rows`, `push_move_row`,
   `push_sort_keys`, `status_message_callback`, not on the concrete class.
5. **Do not combine behaviour changes with moves.** First extraction commits
   should be byte-for-byte behavioural moves plus import updates.
6. **One logical extraction per PR/commit.** This keeps regressions easy to
   bisect.

---

## 3) Phase-by-phase plan

### Phase A — create compatibility skeletons

Objective: prepare package directories and re-export paths without moving
complex logic yet.

Steps:

1. Add package directories: `app/`, `documents/`, `undo/`, `tree/`,
   `delegates/`, `tree_actions/`, `io_formats/`, `state/`.
2. Add `__init__.py` files that expose planned public symbols only after each
   migration.
3. Add a short `docs`/memory note that old top-level modules remain temporary
   compatibility shims.
4. Run full tests.

Validation:

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

Risk: none, as this phase should only add empty packages.

---

### Phase B — split `file_io.py` first

Why first: `file_io.py` is small, mostly pure, and imported only by
`json_tab.py` and `ui.py`. It is a low-risk rehearsal for the extraction style.

Target:

- `io_formats/detect.py`
- `io_formats/load.py`
- `io_formats/dump.py`
- `io_formats/atomic.py`
- `io_formats/__init__.py`
- `file_io.py` becomes a re-export shim.

Public names to preserve:

- `SAVE_FORMAT_JSON`
- `SAVE_FORMAT_JSONL`
- `SAVE_FORMAT_YAML`
- `SAVE_FORMAT_YAML_MULTI`
- `detect_format`
- `load_file`
- `load_file_with_format`
- `dump_text`
- `atomic_write`
- `save_file`

Validation:

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_file_io_phase4.py
QT_QPA_PLATFORM=offscreen pytest -q
```

---

### Phase C — split `view_state.py`

Why: also mostly pure helper logic plus narrow `QSettings` calls.

Target:

- `state/qsettings_coercion.py`: `_coerce_int`, `_coerce_int_list`,
  `_coerce_path`, `_coerce_paths`.
- `state/view_state.py`: `state_key`, `save`, `restore`, `discard`.
- Top-level `view_state.py` re-exports from `state.view_state`.

Validation:

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_phase_5_4_persisted_view_state.py
QT_QPA_PLATFORM=offscreen pytest -q
```

---

### Phase D — split `enums.py` into `tree/types.py`

Why: `JsonType` and type inference are foundational. Move them before moving
tree model/item/delegate modules.

Target:

- `tree/types.py`: `JsonType`, `TEXT_FAMILY`, `parse_json_type`,
  `infer_text_json_type`, `text_pseudotype_for`, and private type-detection
  helpers.
- Top-level `enums.py` re-exports from `tree.types`.

Important: this package name can shadow or confuse `tree_model.py` imports only
if done carelessly. Keep explicit absolute imports and avoid naming a module
`types.py` at top level; `tree/types.py` is acceptable.

Validation:

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_type_editing.py tests/test_smoke_model.py
QT_QPA_PLATFORM=offscreen pytest -q
```

---

### Phase E — split `tree_item.py`

Why: `JsonTreeItem` is a cohesive class but contains separable policy helpers:
name validation, type coercion, editability detection.

Target:

- `tree/item.py`: `JsonTreeItem` class.
- `tree/item_coercion.py`: pure coercion functions, e.g.
  `coerce_value_for_type(value, json_type)`, `normalize_value_for_type(...)`,
  `compute_editable(...)`.
- `tree/item_names.py`: `validate_object_child_name(...)`,
  `unique_child_name(...)`.
- Top-level `tree_item.py` re-exports `JsonTreeItem`.

Recommended intermediate step:

1. Extract private methods to module-level helpers but keep `JsonTreeItem`
   in `tree_item.py`.
2. Run tests.
3. Move `JsonTreeItem` to `tree/item.py` and make the old file a shim.

Watch points:

- Preserve `explicit_type` semantics.
- Preserve `_row_cache` invalidation behaviour.
- Preserve duplicate/empty name errors exactly.
- Preserve malformed binary payloads degrading to non-editable.

Validation:

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_smoke_model.py tests/test_type_editing.py tests/test_tree_correctness.py
QT_QPA_PLATFORM=offscreen pytest -q
```

---

### Phase F — split `tree_model.py`

Why: the Qt model is modest, but display role formatting and mutation helpers
can be isolated.

Target:

- `tree/model.py`: `JsonTreeModel` class and core Qt model overrides.
- `tree/model_roles.py`: `JSON_TYPE_ROLE`, value display text, tooltip text,
  font-role helper.
- `tree/model_mutations.py`: candidate helpers for `move_row`, `sort_keys`,
  `_sort_object_item`, and possibly `change_type` support logic.
- Top-level `tree_model.py` re-exports `JsonTreeModel`, `JSON_TYPE_ROLE`.

Be conservative: if extracting mutation helpers makes signal ownership unclear,
leave them on `JsonTreeModel`. Qt begin/end calls often read better when kept
inside the model class.

Validation:

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_smoke_model.py tests/test_tree_correctness.py tests/test_type_editing.py
QT_QPA_PLATFORM=offscreen pytest -q
```

---

### Phase G — split `delegate.py`

Why: delegate code naturally separates into base editor safety, display
formatting, value editing, type editing, name editing, and bytes codecs.

Target:

- `delegates/base.py`: `_CapsLockSafeLineEdit`, `_TextEditorDelegateBase`.
- `delegates/value_formatting.py`: `_format_default`, `_format_with_type`,
  long-string elision, percent/mpq/bytes display helpers.
- `delegates/bytes_codec.py`: `decode_bytes`, `encode_bytes`.
- `delegates/value.py`: `ValueDelegate`.
- `delegates/type_delegate.py`: `JsonTypeDelegate`.
- `delegates/name_delegate.py`: `NameDelegate`.
- Top-level `delegate.py` re-exports all public delegate classes/functions.

Recommended extraction order:

1. Move bytes codec functions.
2. Move formatting helpers.
3. Move base classes.
4. Move `NameDelegate` and `JsonTypeDelegate`.
5. Move `ValueDelegate` last.

Watch points:

- `ValueDelegate._find_tab` and `JsonTypeDelegate._find_tab` duplicate logic;
  extract a shared `find_parent_with_method(widget, method_name)` helper.
- Avoid importing `JsonTab` directly from delegates.
- Dialog commits must keep using `QPersistentModelIndex`.
- Percent editing must preserve 0..100 UI / 0..1 stored value.
- `EditRole` must remain raw while `DisplayRole` remains presentation-oriented.

Validation:

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_phase_5_1_carryover.py tests/test_phase_5_2_display_formatting.py
QT_QPA_PLATFORM=offscreen pytest -q tests/test_type_editing.py
QT_QPA_PLATFORM=offscreen pytest -q
```

---

### Phase H — split `tree_view.py` into `tree_actions/`

Why: `tree_view.py` currently mixes context menu construction, selection,
clipboard serialization, and structural actions.

Target:

- `tree_actions/selection.py`:
  - `_resolve_model`
  - `_to_source_index`
  - `_to_view_index`
  - `_index_path`
  - `_is_ancestor`
  - `_selected_rows`
  - `_top_level_selected_rows`
  - `_row0`
  - `_is_root_index`
- `tree_actions/clipboard.py`:
  - MIME constants
  - `_build_copy_entries`
  - `_entries_text_payload`
  - `copy_selection`
  - `cut_selection` can either live here or in `structure.py`
  - `_clipboard_entries`
- `tree_actions/paste.py`:
  - `paste_from_clipboard`
  - name-collision helpers related to paste
- `tree_actions/structure.py`:
  - `insert_sibling_before`
  - `insert_sibling_after`
  - `insert_child_current`
  - `delete_selection`
  - `duplicate_selection`
  - `move_selection_up`
  - `move_selection_down`
  - `sort_selection_keys`
  - `expand_all`
  - `collapse_all`
- `tree_actions/context_menu.py`:
  - `show_context_menu`
- `tree_actions/fallback_model_actions.py` or keep top-level
  `model_actions.py` as direct-mutation fallback.
- Top-level `tree_view.py` re-exports the public action functions.

Also delete or avoid carrying forward `_commit_on_tab`, which is documented as
dead code because the old `commit_mutation` API no longer exists.

Watch points:

- Proxy/source mapping must remain central and shared.
- Cut must copy before delete.
- Multi-selection duplicate/delete must operate top-level rows only.
- Paste into object must preserve/correct names via collision avoidance.
- Actions should keep preferring `JsonTab.push_*` typed commands when a tab host
  exists, with direct `model_actions.py` fallback for headless tests.

Validation:

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_tree_actions_clipboard.py tests/test_tree_actions_structure.py
QT_QPA_PLATFORM=offscreen pytest -q tests/test_undo_redo.py tests/test_typed_undo_commands.py
QT_QPA_PLATFORM=offscreen pytest -q
```

---

### Phase I — split `json_tab.py`

Why: this is the largest module and should be tackled only after dependencies
are cleaner. It contains several independent blocks.

Target:

- `documents/tab.py`: public `JsonTab` class, constructor, top-level widget
  ownership, high-level method names.
- `documents/tab_paths.py`: `_proxy_to_source`, `_source_to_view`,
  `_index_path`, `_index_from_path`, `_qualified_name`.
- `documents/tab_status.py`: `_size_hint_for_item`, `_on_current_changed`,
  status message helpers.
- `documents/tab_io.py`: `save`, `save_as`, `_snapshot`.
- `documents/tab_view.py` or `documents/tab_setup.py`: layout creation,
  delegate setup, shortcuts, search/filter wiring, font zoom.
- `undo/commands.py`: `_MoveRowCmd`, `_RenameCmd`, `_EditValueCmd`,
  `_ChangeTypeCmd`, `_InsertRowsCmd`, `_RemoveRowsCmd`, `_SortKeysCmd`.
- `undo/diff.py`: `_diff_apply`, `_emit_row_changed`, `_clear_children`,
  `_convert_container`, `_convert_to_leaf`, `_insert_typed_item`,
  `_diff_object`, `_diff_array`.
- Top-level `json_tab.py` re-exports `JsonTab`.

Recommended extraction order:

1. Move undo command classes to `undo/commands.py` while passing the tab object
   as currently done. This should be mostly mechanical.
2. Move diff helpers to `undo/diff.py`. Prefer a small `DiffApplier` class
   wrapping the `JsonTab` instance rather than many free functions with long
   parameter lists:

   ```python
   class DiffApplier:
       def __init__(self, tab: JsonTabProtocol): ...
       def apply(self, parent_path, old, new): ...
   ```

3. Move path helpers to `documents/tab_paths.py`. These can be pure-ish helper
   functions receiving `model`, `proxy`, or `tab`.
4. Move save/save-as logic to `documents/tab_io.py`. Keep dialog ownership
   with the tab by passing `parent`/`tab`.
5. Move breadcrumb/status formatting to `documents/tab_status.py`.
6. Move UI setup helpers last; Qt object ownership and signal connections are
   easiest to break.

Watch points:

- `QUndoCommand.mergeWith` must preserve timing and same-path behaviour.
- `dataChanged` emissions must still cover columns 0..2 where expected.
- Type-change auto-reopen must keep using `QTimer.singleShot(0, ...)`.
- Dirty state must still be tied to `undo_stack.cleanChanged`.
- Search proxy mapping must not leak source indices into view APIs.
- View-state restore/save must still use proxy-visible paths correctly.
- Synthetic root behaviour (`show_root=True` in app, `False` in many tests)
  must remain unchanged.

Validation:

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_undo_redo.py tests/test_undo_redo_scenario.py tests/test_typed_undo_commands.py tests/test_typed_undo_perf.py
QT_QPA_PLATFORM=offscreen pytest -q tests/test_phase_5_1_carryover.py tests/test_phase_5_3_status_bar_breadcrumb.py tests/test_phase_5_5_search_filter.py
QT_QPA_PLATFORM=offscreen pytest -q
```

---

### Phase J — split `ui.py`

Why: once `JsonTab` is smaller, the application shell can be decomposed into
menu/action/lifecycle services.

Target:

- `app/main_window.py`: `MainWindow` class.
- `app/history.py`: history menu setup, undo/redo dispatch, history dialog.
- `app/recent_files.py`: recent-file list read/write/pruning.
- `app/close_confirm.py`: close-confirm dialog helper.
- `app/main_window_actions.py`: action connection setup and `update_actions`.
- Top-level `ui.py` re-exports `MainWindow` initially.

Recommended extraction order:

1. Move recent-files helpers.
2. Move close-confirm helper.
3. Move history-menu helper.
4. Move action enable/disable helper.
5. Move the class to `app/main_window.py` and shim `ui.py`.

Watch points:

- `mainwindow.py` is generated; do not hand-edit it.
- Preserve current Save behaviour unless intentionally changing it later.
- Close-event must save view state per tab and respect Cancel.
- Recent-file missing-path pruning must remain.

Validation:

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_smoke_mainwindow.py tests/test_file_io_phase4.py
QT_QPA_PLATFORM=offscreen pytest -q
```

---

## 4) Compatibility shim pattern

Use this pattern while migrating imports:

```python
"""Compatibility imports for the pre-package module path."""

from documents.tab import JsonTab

__all__ = ["JsonTab"]
```

For larger old modules such as `tree_view.py`, re-export only the public
functions currently used by tests and other modules. Avoid re-exporting private
helpers unless tests currently import them; if tests do import private helpers,
migrate tests in the same commit.

---

## 5) Suggested dependency contracts

To reduce circular imports, introduce small protocols in a neutral module such
as `documents/protocols.py` or `tree_actions/protocols.py`:

```python
from typing import Protocol, Any
from PySide6.QtCore import QModelIndex

class CommitHost(Protocol):
    def commit_set_data(self, index: QModelIndex, value: Any, role: int) -> bool: ...

class TreeMutationHost(Protocol):
    def push_insert_rows(self, parent, position: int, rows: int = 1) -> bool: ...
    def push_remove_rows(self, parent, position: int, rows: int = 1) -> bool: ...
    def push_move_row(self, parent, source_row: int, dest_row: int) -> bool: ...
    def push_sort_keys(self, parent_path, recursive: bool = False) -> bool: ...
```

These protocols let delegates and tree actions work with any host implementing
the right methods, without importing `JsonTab`.

---

## 6) Test and verification strategy

After every extraction:

1. Run the focused tests listed in the relevant phase.
2. Run the full suite:

   ```bash
   QT_QPA_PLATFORM=offscreen pytest -q
   ```

3. Run a lightweight import smoke check:

   ```bash
   python - <<'PY'
   from json_tab import JsonTab
   from tree_model import JsonTreeModel, JSON_TYPE_ROLE
   from tree_item import JsonTreeItem
   from delegate import ValueDelegate, JsonTypeDelegate, NameDelegate
   from tree_view import copy_selection, paste_from_clipboard, show_context_menu
   from ui import MainWindow
   print('imports ok')
   PY
   ```

4. For `json_tab.py`, `delegate.py`, and `tree_view.py` extractions, also run
   an offscreen application smoke where a `JsonTab` is created, a cell is
   edited through `commit_set_data`, undo/redo is invoked, and the result is
   saved to a temporary file.

---

## 7) Recommended commit sequence

1. Add package skeletons and this plan.
2. Extract `file_io.py` → `io_formats/`.
3. Extract `view_state.py` → `state/`.
4. Extract `enums.py` → `tree/types.py`.
5. Extract `tree_item.py` helpers, then move `JsonTreeItem`.
6. Extract `tree_model.py` role helpers, optionally mutation helpers.
7. Extract `delegate.py` bytes/format/base/type/name/value modules.
8. Extract `tree_view.py` selection/clipboard/paste/structure/context-menu
   modules and remove `_commit_on_tab`.
9. Extract `json_tab.py` undo commands, diff applier, paths, IO, status, setup.
10. Extract `ui.py` recent-files, close-confirm, history, action-state helpers.
11. Migrate all internal imports from compatibility shims to package paths.
12. Remove top-level shims only if desired; otherwise keep them as stable public
    API aliases.

---

## 8) Priority recommendation

The highest-value split is:

1. `json_tab.py` undo commands + diff replay into `undo/`.
2. `tree_view.py` into `tree_actions/`.
3. `delegate.py` into `delegates/`.

These three changes isolate the most independent logical blocks and make future
work easier:

- undo/diff logic becomes testable without scanning widget setup code;
- tree actions become reusable command helpers instead of a context-menu file;
- delegate formatting/editor dispatch becomes easier to cover with the planned
  Phase 6 delegate matrix.

Do smaller `file_io.py`, `view_state.py`, and `enums.py` migrations first only
because they are safer rehearsals for the package/shim pattern.

---

## 9) Things not to refactor yet

- Do not rewrite the undo system while moving it. Keep typed commands as-is.
- Do not replace the model/item architecture with a generic JSON library.
- Do not hand-edit `mainwindow.py`; it is generated from `mainwindow.ui`.
- Do not remove `show_root` compatibility until tests and app paths agree.
- Do not delete legacy top-level imports until downstream scripts/tests are
  migrated or compatibility is explicitly no longer required.

---

## 10) Definition of done

The refactor is complete when:

- no source file except generated `mainwindow.py` is over roughly 500 lines;
- top-level modules are either removed or documented compatibility shims;
- `JsonTab`, delegates, tree actions, model/item, file IO, and app shell each
  live in their own package area;
- there are no new circular imports;
- all existing tests pass under offscreen Qt;
- the planned Phase 6 delegate/model/IO tests can target smaller modules
  directly.
