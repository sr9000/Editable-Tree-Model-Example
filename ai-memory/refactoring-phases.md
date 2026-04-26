# Refactoring phases — one commit per phase

_Created: 2026-04-26._

This is the executable version of `ai-memory/refactoring-plan.md`.

Rules:

1. **One phase = one git commit.**
2. **No phase may mix code movement with behaviour changes.**
3. **Every phase must update `ai-memory/refactoring-test-log.md`.**
4. **Every phase must have a green focused test run or explicitly document why
   no focused test applies.**
5. **Every phase must run the full suite before commit unless the phase only
   adds documentation.**
6. **If a phase exposes a regression, stop and fix it before starting the next
   phase. Do not stack refactors on top of a red suite.**

Baseline known from repo memory before this plan:

```text
QT_QPA_PLATFORM=offscreen pytest -q
401 passed in ~3 s
```

The baseline should be refreshed in Phase 00 before any source refactor.

---

## Mandatory per-commit workflow

For every refactoring commit:

1. Start from a clean git worktree.
2. Run and record baseline tests for the exact starting revision when practical.
3. Make only the changes listed in the phase.
4. Run the phase-focused tests.
5. Run the full suite.
6. Update `ai-memory/refactoring-test-log.md` with:
   - phase ID;
   - commit subject or planned subject;
   - files changed;
   - focused test command and result;
   - full-suite command and result;
   - known failures, if any;
   - decision: `PASS`, `BLOCKED`, or `DOCS_ONLY`.
7. Commit only if DoD is complete.

Recommended full-suite command:

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

Recommended import-smoke command after any compatibility-shim phase:

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

---

## Phase 00 — refresh baseline and add tracking files

**Commit size:** documentation / process only.

**Goal:** establish the current test state before source movement starts.

**Allowed changes:**

- Add or update `ai-memory/refactoring-phases.md`.
- Add or update `ai-memory/refactoring-test-log.md`.
- Optionally add a short link from `ai-memory/refactoring-plan.md`.

**Tests to run:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Full-suite baseline recorded in `ai-memory/refactoring-test-log.md`.
- [ ] No runtime source files changed.
- [ ] If the baseline is red, failures are recorded before any refactor begins.

---

## Phase 01 — add empty package skeletons

**Commit size:** package directories only.

**Goal:** create the future module homes without moving logic.

**Allowed changes:**

- Add empty/minimal package directories:
  - `app/`
  - `documents/`
  - `undo/`
  - `tree/`
  - `delegates/`
  - `tree_actions/`
  - `io_formats/`
  - `state/`
- Add `__init__.py` files.
- Do not change imports yet.

**Focused tests:**

```bash
python - <<'PY'
import app, documents, undo, tree, delegates, tree_actions, io_formats, state
print('package skeleton imports ok')
PY
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] All new packages import successfully.
- [ ] Full suite result recorded.
- [ ] `ai-memory/refactoring-test-log.md` updated.
- [ ] No existing module imports changed.

---

## Phase 02 — extract file-format constants and detection

**Commit size:** first `file_io.py` slice only.

**Goal:** move save-format constants and extension detection into
`io_formats/detect.py`.

**Allowed changes:**

- Create `io_formats/detect.py`.
- Move:
  - `SAVE_FORMAT_JSON`
  - `SAVE_FORMAT_JSONL`
  - `SAVE_FORMAT_YAML`
  - `SAVE_FORMAT_YAML_MULTI`
  - `detect_format`
- Re-export these names through `io_formats/__init__.py` and `file_io.py`.
- Do not move load/save implementations yet.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_file_io_phase4.py
python - <<'PY'
from file_io import detect_format, SAVE_FORMAT_JSON
from io_formats import detect_format as detect_format2, SAVE_FORMAT_JSON as JSON2
assert detect_format('x.json') == SAVE_FORMAT_JSON
assert detect_format2('x.json') == JSON2
print('file format detection imports ok')
PY
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Old imports from `file_io.py` still work.
- [ ] New imports from `io_formats` work.
- [ ] Focused tests pass and are recorded.
- [ ] Full suite passes and is recorded.

---

## Phase 03 — extract file loading

**Commit size:** second `file_io.py` slice only.

**Goal:** move load paths into `io_formats/load.py`.

**Allowed changes:**

- Create `io_formats/load.py`.
- Move:
  - `load_file`
  - `load_file_with_format`
- Keep `file_io.py` as compatibility re-export/import wrapper.
- Do not move dump/write implementations yet.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_file_io_phase4.py
python - <<'PY'
from file_io import load_file, load_file_with_format
from io_formats.load import load_file as load_file2
assert load_file is not None
assert load_file_with_format is not None
assert load_file2 is not None
print('file loading imports ok')
PY
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] JSON, JSONL, YAML, and YAML-multi load tests still pass.
- [ ] Old `file_io` load imports still work.
- [ ] Focused and full test states recorded.

---

## Phase 04 — extract file dumping and atomic write

**Commit size:** final `file_io.py` slice.

**Goal:** finish `io_formats/` extraction while preserving `file_io.py`.

**Allowed changes:**

- Create `io_formats/dump.py`.
- Create `io_formats/atomic.py`.
- Move:
  - `dump_text`
  - `atomic_write`
  - `save_file`
- Make `file_io.py` a small compatibility shim.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_file_io_phase4.py
python - <<'PY'
from file_io import dump_text, atomic_write, save_file
from io_formats import dump_text as dump_text2, save_file as save_file2
assert dump_text is dump_text2
assert save_file is save_file2
assert atomic_write is not None
print('file dumping imports ok')
PY
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] `file_io.py` is now only a compatibility wrapper.
- [ ] Save/load tests pass.
- [ ] Full suite passes.
- [ ] Test log updated.

---

## Phase 05 — extract `QSettings` coercion helpers

**Commit size:** first `view_state.py` slice.

**Goal:** move pure coercion helpers out of persisted view-state logic.

**Allowed changes:**

- Create `state/qsettings_coercion.py`.
- Move:
  - `_coerce_int`
  - `_coerce_int_list`
  - `_coerce_path`
  - `_coerce_paths`
- Keep `save`, `restore`, `discard`, and `state_key` in top-level
  `view_state.py` for now.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_phase_5_4_persisted_view_state.py
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Persisted view-state tests pass.
- [ ] No public view-state imports changed.
- [ ] Test log updated.

---

## Phase 06 — move persisted view-state module

**Commit size:** final `view_state.py` slice.

**Goal:** move public view-state functions into `state/view_state.py`.

**Allowed changes:**

- Create `state/view_state.py`.
- Move:
  - `MAX_EXPANDED_PATHS`
  - `state_key`
  - `save`
  - `restore`
  - `discard`
- Make top-level `view_state.py` a compatibility shim.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_phase_5_4_persisted_view_state.py
python - <<'PY'
from view_state import save, restore, discard, state_key
from state.view_state import save as save2, restore as restore2
assert save is save2
assert restore is restore2
assert discard is not None
assert state_key is not None
print('view_state compatibility imports ok')
PY
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Top-level `view_state.py` remains import-compatible.
- [ ] New `state.view_state` imports work.
- [ ] Focused and full test states recorded.

---

## Phase 07 — move JSON type definitions

**Commit size:** one foundational module move.

**Goal:** move `JsonType` and type-detection helpers into `tree/types.py`.

**Allowed changes:**

- Create `tree/types.py`.
- Move all logic from `enums.py`.
- Make top-level `enums.py` a compatibility shim.
- Do not update all internal imports yet unless needed to avoid circulars.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_type_editing.py tests/test_smoke_model.py tests/test_phase_5_2_display_formatting.py
python - <<'PY'
from enums import JsonType, parse_json_type
from tree.types import JsonType as JsonType2, parse_json_type as parse2
assert JsonType is JsonType2
assert parse_json_type is parse2
print('type compatibility imports ok')
PY
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] `enums.py` remains import-compatible.
- [ ] `tree.types` is the canonical implementation.
- [ ] Type-editing and display tests pass.
- [ ] Full suite result recorded.

---

## Phase 08 — extract tree-item name helpers

**Commit size:** first `tree_item.py` slice.

**Goal:** isolate object-key validation and unique-name generation.

**Allowed changes:**

- Create `tree/item_names.py`.
- Extract helper logic used by:
  - `_set_name`
  - `_unique_child_name`
- Keep `JsonTreeItem` in top-level `tree_item.py` for now.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_smoke_model.py tests/test_tree_actions_clipboard.py tests/test_tree_actions_structure.py
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Duplicate/empty object-key behaviour unchanged.
- [ ] Paste/duplicate collision tests pass.
- [ ] Full suite result recorded.

---

## Phase 09 — extract tree-item coercion helpers

**Commit size:** second `tree_item.py` slice.

**Goal:** isolate type coercion and editability policy.

**Allowed changes:**

- Create `tree/item_coercion.py`.
- Extract logic from:
  - `_normalize_value_for_type`
  - `_coerce_value_for_type`
  - `_compute_editable`
- Keep `JsonTreeItem` in top-level `tree_item.py`.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_type_editing.py tests/test_phase_5_1_carryover.py tests/test_phase_5_2_display_formatting.py
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Type coercion results unchanged.
- [ ] Malformed bytes-family payloads still degrade to non-editable.
- [ ] Focused and full test states recorded.

---

## Phase 10 — move `JsonTreeItem`

**Commit size:** final `tree_item.py` move.

**Goal:** move the item class into `tree/item.py`.

**Allowed changes:**

- Create `tree/item.py`.
- Move `JsonTreeItem`.
- Make top-level `tree_item.py` a compatibility shim.
- Update internal imports only where convenient and safe.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_smoke_model.py tests/test_tree_correctness.py tests/test_type_editing.py
python - <<'PY'
from tree_item import JsonTreeItem
from tree.item import JsonTreeItem as JsonTreeItem2
assert JsonTreeItem is JsonTreeItem2
print('tree item compatibility imports ok')
PY
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Old and new `JsonTreeItem` imports are identical.
- [ ] Model/type/tree tests pass.
- [ ] Full suite result recorded.

---

## Phase 11 — extract model role/display helpers

**Commit size:** first `tree_model.py` slice.

**Goal:** move model data-role formatting policy out of the Qt model shell.

**Allowed changes:**

- Create `tree/model_roles.py`.
- Move or wrap:
  - `JSON_TYPE_ROLE`
  - display-value formatting helper logic;
  - tooltip text helper logic;
  - font-role helper logic.
- Keep `JsonTreeModel` in top-level `tree_model.py`.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_smoke_model.py tests/test_phase_5_2_display_formatting.py
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] DisplayRole/EditRole/ToolTipRole behaviour unchanged.
- [ ] `JSON_TYPE_ROLE` old import remains valid.
- [ ] Focused and full test states recorded.

---

## Phase 12 — move `JsonTreeModel`

**Commit size:** final `tree_model.py` move.

**Goal:** move the model class into `tree/model.py`.

**Allowed changes:**

- Create `tree/model.py`.
- Move `JsonTreeModel`.
- Make top-level `tree_model.py` a compatibility shim.
- Avoid extracting model mutation helpers in this phase unless they are purely
  mechanical; Qt begin/end signal ownership should stay clear.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_smoke_model.py tests/test_tree_correctness.py tests/test_type_editing.py
python - <<'PY'
from tree_model import JsonTreeModel, JSON_TYPE_ROLE
from tree.model import JsonTreeModel as JsonTreeModel2
from tree.model_roles import JSON_TYPE_ROLE as ROLE2
assert JsonTreeModel is JsonTreeModel2
assert JSON_TYPE_ROLE == ROLE2
print('tree model compatibility imports ok')
PY
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Old and new model imports are compatible.
- [ ] Persistent index and model mutation tests remain green.
- [ ] Full suite result recorded.

---

## Phase 13 — extract delegate bytes codec

**Commit size:** first `delegate.py` slice.

**Goal:** isolate bytes/zlib/gzip encode/decode helpers.

**Allowed changes:**

- Create `delegates/bytes_codec.py`.
- Move:
  - `decode_bytes`
  - `encode_bytes`
- Re-export from top-level `delegate.py`.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_phase_5_1_carryover.py tests/test_qhexedit_highlighting.py
python - <<'PY'
from delegate import decode_bytes, encode_bytes
from delegates.bytes_codec import decode_bytes as decode2, encode_bytes as encode2
assert decode_bytes is decode2
assert encode_bytes is encode2
print('delegate bytes codec imports ok')
PY
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Bytes-family decode failures are still caught by delegate code.
- [ ] Old helper imports remain valid.
- [ ] Focused and full test states recorded.

---

## Phase 14 — extract delegate formatting helpers

**Commit size:** second `delegate.py` slice.

**Goal:** isolate type-aware display formatting.

**Allowed changes:**

- Create `delegates/value_formatting.py`.
- Move helper logic behind:
  - `_format_default`
  - `_format_with_type`
  - long-string elision;
  - percent/mpq/bytes-family display formatting.
- Keep `ValueDelegate` class in top-level `delegate.py` for now.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_phase_5_2_display_formatting.py
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Percent, mpq, bytes-family, and long-string display unchanged.
- [ ] Tooltips still carry full text where expected.
- [ ] Test log updated.

---

## Phase 15 — extract delegate base classes

**Commit size:** third `delegate.py` slice.

**Goal:** isolate CapsLock/layout-switch-safe text editing base classes.

**Allowed changes:**

- Create `delegates/base.py`.
- Move:
  - `_CapsLockSafeLineEdit`
  - `_TextEditorDelegateBase`
- Keep concrete delegates in top-level `delegate.py` for now.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_phase_5_6_misc_polish.py tests/test_type_editing.py
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Inline text/name editing still uses the CapsLock-safe line edit.
- [ ] Concrete delegates still import and instantiate.
- [ ] Focused and full test states recorded.

---

## Phase 16 — move name and type delegates

**Commit size:** fourth `delegate.py` slice.

**Goal:** move smaller concrete delegates before `ValueDelegate`.

**Allowed changes:**

- Create `delegates/name_delegate.py`.
- Create `delegates/type_delegate.py`.
- Move:
  - `NameDelegate`
  - `JsonTypeDelegate`
- Re-export from top-level `delegate.py`.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_type_editing.py tests/test_phase_5_1_carryover.py
python - <<'PY'
from delegate import NameDelegate, JsonTypeDelegate
from delegates.name_delegate import NameDelegate as NameDelegate2
from delegates.type_delegate import JsonTypeDelegate as JsonTypeDelegate2
assert NameDelegate is NameDelegate2
assert JsonTypeDelegate is JsonTypeDelegate2
print('name/type delegate compatibility imports ok')
PY
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Type combo commit still routes through `JsonTab.commit_set_data` when hosted by a tab.
- [ ] Rename commit still routes through typed undo when hosted by a tab.
- [ ] Focused and full test states recorded.

---

## Phase 17 — move `ValueDelegate`

**Commit size:** final `delegate.py` move.

**Goal:** move the largest delegate into `delegates/value.py`.

**Allowed changes:**

- Create `delegates/value.py`.
- Move `ValueDelegate`.
- Make top-level `delegate.py` a compatibility shim re-exporting all public
  delegate names and bytes helpers.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_type_editing.py tests/test_phase_5_1_carryover.py tests/test_phase_5_2_display_formatting.py
python - <<'PY'
from delegate import ValueDelegate
from delegates.value import ValueDelegate as ValueDelegate2
assert ValueDelegate is ValueDelegate2
print('value delegate compatibility imports ok')
PY
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] All editor creation and set/get data paths remain unchanged.
- [ ] Dialog editors still commit via persistent indexes.
- [ ] Display formatting remains unchanged.
- [ ] Full suite result recorded.

---

## Phase 18 — extract tree-action selection helpers

**Commit size:** first `tree_view.py` slice.

**Goal:** centralize proxy/source mapping and row-selection helpers.

**Allowed changes:**

- Create `tree_actions/selection.py`.
- Move:
  - `_resolve_model`
  - `_to_source_index`
  - `_to_view_index`
  - `_index_path`
  - `_is_ancestor`
  - `_selected_rows`
  - `_top_level_selected_rows`
  - `_row0`
  - `_is_root_index`
- Keep public actions in top-level `tree_view.py` for now.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_tree_actions_clipboard.py tests/test_tree_actions_structure.py tests/test_phase_5_5_search_filter.py
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Tree actions remain proxy-aware.
- [ ] Search/filter action tests still pass.
- [ ] Focused and full test states recorded.

---

## Phase 19 — extract tree-action clipboard helpers

**Commit size:** second `tree_view.py` slice.

**Goal:** isolate copy/cut clipboard payload logic.

**Allowed changes:**

- Create `tree_actions/clipboard.py`.
- Move:
  - `_build_copy_entries`
  - `_entries_text_payload`
  - `copy_selection`
  - `_clipboard_entries`
- `cut_selection` may remain in `tree_view.py` until delete action moves.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_tree_actions_clipboard.py
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Clipboard MIME format and plain-text fallback unchanged.
- [ ] Copy tests pass.
- [ ] Full suite result recorded.

---

## Phase 20 — extract paste action

**Commit size:** third `tree_view.py` slice.

**Goal:** isolate paste-from-clipboard and object-name collision behaviour.

**Allowed changes:**

- Create `tree_actions/paste.py`.
- Move:
  - `paste_from_clipboard`
  - paste-specific helpers.
- Re-export `paste_from_clipboard` from `tree_view.py`.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_tree_actions_clipboard.py tests/test_tree_actions_structure.py
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Paste preserves names and avoids collisions under objects.
- [ ] Paste still prefers tab typed commands when a `JsonTab` host exists.
- [ ] Focused and full test states recorded.

---

## Phase 21 — extract structural tree actions

**Commit size:** fourth `tree_view.py` slice.

**Goal:** move insert/delete/duplicate/move/sort/expand/collapse actions.

**Allowed changes:**

- Create `tree_actions/structure.py`.
- Move:
  - `insert_sibling_before`
  - `insert_sibling_after`
  - `insert_child_current`
  - `delete_selection`
  - `cut_selection`
  - `duplicate_selection`
  - `move_selection_up`
  - `move_selection_down`
  - `sort_selection_keys`
  - `expand_all`
  - `collapse_all`
- Re-export public functions from `tree_view.py`.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_tree_actions_structure.py tests/test_tree_actions_clipboard.py tests/test_undo_redo.py tests/test_typed_undo_commands.py
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Structural actions still use typed undo when hosted by a tab.
- [ ] Direct model-action fallback still works for headless tests.
- [ ] Multi-selection top-level-row behaviour unchanged.
- [ ] Full suite result recorded.

---

## Phase 22 — extract context menu and finish `tree_view.py`

**Commit size:** final `tree_view.py` move.

**Goal:** move context-menu construction and make `tree_view.py` a shim.

**Allowed changes:**

- Create `tree_actions/context_menu.py`.
- Move `show_context_menu`.
- Make top-level `tree_view.py` a compatibility shim.
- Remove dead `_commit_on_tab` instead of moving it.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_tree_actions_clipboard.py tests/test_tree_actions_structure.py tests/test_phase_5_6_misc_polish.py
python - <<'PY'
from tree_view import show_context_menu, copy_selection, paste_from_clipboard
from tree_actions.context_menu import show_context_menu as show_context_menu2
assert show_context_menu is show_context_menu2
assert copy_selection is not None
assert paste_from_clipboard is not None
print('tree_view compatibility imports ok')
PY
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Context menu still exposes all expected actions.
- [ ] `tree_view.py` public imports still work.
- [ ] Dead `_commit_on_tab` is removed.
- [ ] Focused and full test states recorded.

---

## Phase 23 — move undo command classes

**Commit size:** first `json_tab.py` slice.

**Goal:** move typed `QUndoCommand` classes into `undo/commands.py`.

**Allowed changes:**

- Create `undo/commands.py`.
- Move:
  - `_MoveRowCmd`
  - `_RenameCmd`
  - `_EditValueCmd`
  - `_ChangeTypeCmd`
  - `_InsertRowsCmd`
  - `_RemoveRowsCmd`
  - `_SortKeysCmd`
- Keep `JsonTab` in top-level `json_tab.py`.
- Keep command names private if practical, but import them explicitly where
  `JsonTab` constructs commands.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_undo_redo.py tests/test_undo_redo_scenario.py tests/test_typed_undo_commands.py tests/test_typed_undo_perf.py
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Undo/redo behaviour unchanged.
- [ ] Rename/value `mergeWith` behaviour unchanged.
- [ ] Typed-command performance tests still pass.
- [ ] Full suite result recorded.

---

## Phase 24 — extract diff replay helper

**Commit size:** second `json_tab.py` slice.

**Goal:** move surgical tree diff replay out of the widget class.

**Allowed changes:**

- Create `undo/diff.py`.
- Move logic behind:
  - `_diff_apply`
  - `_emit_row_changed`
  - `_clear_children`
  - `_convert_container`
  - `_convert_to_leaf`
  - `_insert_typed_item`
  - `_diff_object`
  - `_diff_array`
- Prefer a small helper class wrapping the tab/model instead of many long
  parameter lists.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_undo_redo.py tests/test_undo_redo_scenario.py tests/test_typed_undo_commands.py tests/test_typed_undo_perf.py tests/test_perf_smoke.py
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Undo/redo still preserves expansion and selection where tests expect it.
- [ ] Qt model signals remain correct.
- [ ] Performance smoke tests remain within limits.
- [ ] Test log updated.

---

## Phase 25 — extract `JsonTab` path helpers

**Commit size:** third `json_tab.py` slice.

**Goal:** move proxy/source mapping and item-path helpers.

**Allowed changes:**

- Create `documents/tab_paths.py`.
- Move logic behind:
  - `_proxy_to_source`
  - `_source_to_view`
  - `_index_path`
  - `_index_from_path`
  - `_qualified_name`

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_phase_5_3_status_bar_breadcrumb.py tests/test_phase_5_4_persisted_view_state.py tests/test_phase_5_5_search_filter.py
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Breadcrumb paths unchanged.
- [ ] View-state expanded/current paths restore unchanged.
- [ ] Search proxy index mapping remains correct.
- [ ] Full suite result recorded.

---

## Phase 26 — extract `JsonTab` status helpers

**Commit size:** fourth `json_tab.py` slice.

**Goal:** move breadcrumb and size-hint/status formatting.

**Allowed changes:**

- Create `documents/tab_status.py`.
- Move logic behind:
  - `_size_hint_for_item`
  - `_on_current_changed` formatting helpers.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_phase_5_3_status_bar_breadcrumb.py tests/test_phase_5_2_display_formatting.py
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Breadcrumb text remains byte-for-byte compatible with tests.
- [ ] Transient/permanent status callback behaviour unchanged.
- [ ] Test log updated.

---

## Phase 27 — extract `JsonTab` save/save-as helpers

**Commit size:** fifth `json_tab.py` slice.

**Goal:** move document save orchestration out of the widget class.

**Allowed changes:**

- Create `documents/tab_io.py`.
- Move logic behind:
  - `save`
  - `save_as`
  - `_snapshot`
- Keep public `JsonTab.save` and `JsonTab.save_as` methods as forwarding
  methods if needed.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_file_io_phase4.py tests/test_smoke_mainwindow.py
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Save/save-as behaviour unchanged.
- [ ] Dirty clean-state marker still updates after save.
- [ ] Save-format detection/persistence unchanged.
- [ ] Full suite result recorded.

---

## Phase 28 — extract `JsonTab` setup helpers

**Commit size:** sixth `json_tab.py` slice.

**Goal:** move constructor setup chunks without moving the class yet.

**Allowed changes:**

- Create `documents/tab_setup.py`.
- Extract helper functions for:
  - model/proxy/delegate setup;
  - search bar setup;
  - shortcut setup;
  - font zoom initialization;
  - tree-view context-menu wiring.
- Keep `JsonTab.__init__` as the owner of Qt objects and signal connections.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_smoke_mainwindow.py tests/test_phase_5_5_search_filter.py tests/test_phase_5_6_misc_polish.py
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Search debounce and Ctrl+F still work in tests.
- [ ] Zoom shortcuts/actions still work in tests.
- [ ] Context menu setup remains connected.
- [ ] Full suite result recorded.

---

## Phase 29 — move `JsonTab`

**Commit size:** final `json_tab.py` move.

**Goal:** move public tab widget to `documents/tab.py`.

**Allowed changes:**

- Create `documents/tab.py`.
- Move `JsonTab` class.
- Make top-level `json_tab.py` a compatibility shim.
- Keep `_demo_data` with the class for now unless a separate cleanup phase is
  explicitly planned.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_smoke_mainwindow.py tests/test_undo_redo.py tests/test_phase_5_1_carryover.py tests/test_phase_5_5_search_filter.py
python - <<'PY'
from json_tab import JsonTab
from documents.tab import JsonTab as JsonTab2
assert JsonTab is JsonTab2
print('JsonTab compatibility imports ok')
PY
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Old and new `JsonTab` imports are identical.
- [ ] Main-window smoke tests still pass.
- [ ] Full suite result recorded.

---

## Phase 30 — extract recent-files helper

**Commit size:** first `ui.py` slice.

**Goal:** isolate recent-file persistence from `MainWindow`.

**Allowed changes:**

- Create `app/recent_files.py`.
- Move logic behind:
  - `_recent_files`
  - `_push_recent`
  - `_refresh_recent_menu` helper logic where practical.
- Keep `MainWindow` in top-level `ui.py`.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_file_io_phase4.py tests/test_smoke_mainwindow.py
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Recent-files cap and missing-file pruning unchanged.
- [ ] Recent menu still populates after open/save paths in tests.
- [ ] Test log updated.

---

## Phase 31 — extract close-confirm helper

**Commit size:** second `ui.py` slice.

**Goal:** isolate Save/Discard/Cancel close flow.

**Allowed changes:**

- Create `app/close_confirm.py`.
- Move logic behind `_confirm_close` into a helper function/class.
- Keep `MainWindow.close_tab` and `closeEvent` public behaviour unchanged.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_smoke_mainwindow.py tests/test_file_io_phase4.py
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Save/Discard/Cancel behaviour unchanged.
- [ ] View state is still saved on accepted close paths.
- [ ] Full suite result recorded.

---

## Phase 32 — extract history menu/dialog helper

**Commit size:** third `ui.py` slice.

**Goal:** isolate undo/redo menu and history dialog setup.

**Allowed changes:**

- Create `app/history.py`.
- Move logic behind:
  - `_setup_history_menu`
  - `_bind_undo_signals`
  - `_do_undo`
  - `_do_redo`
  - `_show_history_dialog`

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_smoke_mainwindow.py tests/test_undo_redo.py
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Undo/redo actions still track active tab state.
- [ ] History dialog still binds to the active tab stack.
- [ ] Test log updated.

---

## Phase 33 — extract main-window action wiring/state

**Commit size:** fourth `ui.py` slice.

**Goal:** isolate action connection and enable/disable policy.

**Allowed changes:**

- Create `app/main_window_actions.py`.
- Move logic behind:
  - `setup_connections`
  - `update_actions`
  - simple wrappers for expand/collapse/zoom/copy if practical.
- Do not change Save enablement policy in this phase.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_smoke_mainwindow.py tests/test_phase_5_6_misc_polish.py
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Action enabled/disabled states unchanged.
- [ ] View menu actions still target active tab.
- [ ] Full suite result recorded.

---

## Phase 34 — move `MainWindow`

**Commit size:** final `ui.py` move.

**Goal:** move public main-window class to `app/main_window.py`.

**Allowed changes:**

- Create `app/main_window.py`.
- Move `MainWindow`.
- Make top-level `ui.py` a compatibility shim.
- Do not hand-edit generated `mainwindow.py`.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_smoke_mainwindow.py tests/test_file_io_phase4.py
python - <<'PY'
from ui import MainWindow
from app.main_window import MainWindow as MainWindow2
assert MainWindow is MainWindow2
print('MainWindow compatibility imports ok')
PY
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Old and new `MainWindow` imports are identical.
- [ ] Main-window smoke and file-flow tests pass.
- [ ] Full suite result recorded.

---

## Phase 35 — migrate internal imports to package paths

**Commit size:** import cleanup only.

**Goal:** stop relying on compatibility shims inside the application code.

**Allowed changes:**

- Update internal imports from old top-level modules to package modules where
  stable.
- Keep top-level compatibility shims for external callers/tests unless a later
  removal phase is planned.
- No behavioural changes.

**Focused tests:**

```bash
python - <<'PY'
from json_tab import JsonTab
from documents.tab import JsonTab as JsonTab2
from ui import MainWindow
from app.main_window import MainWindow as MainWindow2
from tree_model import JsonTreeModel
from tree.model import JsonTreeModel as JsonTreeModel2
assert JsonTab is JsonTab2
assert MainWindow is MainWindow2
assert JsonTreeModel is JsonTreeModel2
print('compatibility shims still ok')
PY
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Internal imports prefer package paths.
- [ ] Compatibility shims still work.
- [ ] Full suite result recorded.

---

## Phase 36 — optional cleanup: remove obsolete private/dead code only

**Commit size:** cleanup only.

**Goal:** remove dead code identified during extraction.

**Allowed changes:**

- Remove only code proven dead by previous phases/tests.
- Candidate: `tree_view._commit_on_tab` if not already removed in Phase 22.
- Do not remove public compatibility shims in this phase.

**Focused tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q tests/test_tree_actions_clipboard.py tests/test_tree_actions_structure.py tests/test_smoke_mainwindow.py
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Removed code has no remaining references.
- [ ] Focused and full test states recorded.
- [ ] No compatibility shim removed accidentally.

---

## Phase 37 — optional cleanup: remove compatibility shims

**Commit size:** public API decision only.

**Goal:** remove old top-level modules only if the project intentionally no
longer supports those import paths.

**Default recommendation:** skip this phase and keep shims. They are cheap and
useful for tests, scripts, and downstream users.

**Allowed changes if executed:**

- Remove top-level shim files only after all imports and tests are migrated.
- Update documentation and tests to use package paths.

**Focused tests:**

```bash
python - <<'PY'
from documents.tab import JsonTab
from app.main_window import MainWindow
from tree.model import JsonTreeModel
from tree.item import JsonTreeItem
from delegates.value import ValueDelegate
print('new public imports ok')
PY
```

**Full tests:**

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

**DoD:**

- [ ] Decision to remove shims is documented.
- [ ] No tests or internal modules import removed paths.
- [ ] Full suite result recorded.

---

## Phase progress table

Update this table as phases land.

| Phase | Commit subject | Status | Full suite result | Notes |
| --- | --- | --- | --- | --- |
| 00 | Add refactor phase/test tracking | PASS | 401 passed in 3.36s | Docs/process |
| 01 | Add package skeletons | PASS | 401 passed in 3.23s |  |
| 02 | Extract file-format detection | PASS | 401 passed in 3.23s |  |
| 03 | Extract file loading | PASS | 401 passed in 3.18s |  |
| 04 | Extract file dumping/write | PASS | 401 passed in 3.18s |  |
| 05 | Extract QSettings coercion | PASS | 401 passed in 3.25s |  |
| 06 | Move persisted view-state module | PASS | 401 passed in 3.20s |  |
| 07 | Move JSON type definitions | PASS | 401 passed in 3.20s |  |
| 08 | Extract tree-item name helpers | PASS | 401 passed in 3.15s | Focused command segfaults post-run |
| 09 | Extract tree-item coercion helpers | PASS | 401 passed in 3.18s |  |
| 10 | Move JsonTreeItem | PASS | 401 passed in 3.21s |  |
| 11 | Extract model role/display helpers | PASS | 401 passed in 3.19s |  |
| 12 | Move JsonTreeModel | PASS | 401 passed in 3.22s |  |
| 13 | Extract delegate bytes codec | PASS | 401 passed in 3.23s |  |
| 14 | Extract delegate formatting helpers | PASS | 401 passed in 3.17s |  |
| 15 | Extract delegate base classes | PASS | 401 passed in 3.19s |  |
| 16 | Move name/type delegates | PASS | 401 passed in 3.20s |  |
| 17 | Move ValueDelegate | PASS | 401 passed in 3.24s |  |
| 18 | Extract tree-action selection helpers | PASS | 401 passed in 3.17s | Focused command segfaults post-run |
| 19 | Extract tree-action clipboard helpers | PASS | 401 passed in 3.19s | Focused command segfaults post-run |
| 20 | Extract paste action | PASS | 401 passed in 3.22s | Focused command segfaults post-run |
| 21 | Extract structural tree actions | PASS | 401 passed in 3.16s |  |
| 22 | Extract context menu / finish tree_view | PASS | 401 passed in 3.15s | Focused command segfaults post-run |
| 23 | Move undo command classes | PASS | 401 passed in 3.23s | Restored `json_tab.time` monkeypatch compatibility |
| 24 | Extract diff replay helper | TODO | Not run |  |
| 25 | Extract JsonTab path helpers | PASS | 401 passed in 3.22s |  |
| 26 | Extract JsonTab status helpers | PASS | 401 passed in 3.17s |  |
| 27 | Extract JsonTab save/save-as helpers | TODO | Not run |  |
| 28 | Extract JsonTab setup helpers | TODO | Not run |  |
| 29 | Move JsonTab | TODO | Not run |  |
| 30 | Extract recent-files helper | TODO | Not run |  |
| 31 | Extract close-confirm helper | TODO | Not run |  |
| 32 | Extract history helper | TODO | Not run |  |
| 33 | Extract main-window action wiring/state | TODO | Not run |  |
| 34 | Move MainWindow | TODO | Not run |  |
| 35 | Migrate internal imports | TODO | Not run |  |
| 36 | Optional dead-code cleanup | TODO | Not run |  |
| 37 | Optional remove compatibility shims | SKIP recommended | Not run | Keep shims by default |
