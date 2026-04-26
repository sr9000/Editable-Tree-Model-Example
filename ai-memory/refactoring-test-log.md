# Refactoring test log

_Created: 2026-04-26._

Purpose: every refactoring phase in `ai-memory/refactoring-phases.md` must
record its test state here before commit. This file is intentionally part of
the repo memory so regressions cannot be hidden between extraction commits.

Status values:

- `PASS` — focused tests and full suite passed.
- `BLOCKED` — tests failed or could not run; do not proceed to the next source
  refactor until resolved or explicitly accepted.
- `DOCS_ONLY` — documentation/process-only phase; full runtime tests optional
  but record whether they were run.

Known pre-plan baseline from repo memory:

```text
QT_QPA_PLATFORM=offscreen pytest -q
401 passed in ~3 s
```

Refresh this with an actual local run before Phase 01 source work.

---

## Entry template

Copy this template for each phase:

```markdown
## Phase NN — short title

- Date:
- Commit subject:
- Status: PASS | BLOCKED | DOCS_ONLY
- Files changed:
  - `path/to/file.py`
- Focused tests:
  ```bash
  command here
  ```
- Focused result:
  ```text
  result here
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  result here
  ```
- Import smoke, if applicable:
  ```bash
  command here
  ```
- Import-smoke result:
  ```text
  result here
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed | blocked | docs-only
```

---

## Phase 00 — add refactor phase/test tracking

- Date: 2026-04-26
- Commit subject: Add commit-sized refactoring phase tracker
- Status: DOCS_ONLY
- Files changed:
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
  - `ai-memory/refactoring-plan.md`
- Focused tests:
  ```bash
  test -s ai-memory/refactoring-phases.md
  test -s ai-memory/refactoring-test-log.md
  grep -n "Execution tracker" -A3 ai-memory/refactoring-plan.md
  ```
- Focused result:
  ```text
  passed; both files exist and ai-memory/refactoring-plan.md links to the phase tracker/test log
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.36s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 01 — add package skeletons

- Date: 2026-04-26
- Commit subject: Add package skeletons
- Status: PASS
- Files changed:
  - `app/__init__.py`
  - `documents/__init__.py`
  - `undo/__init__.py`
  - `tree/__init__.py`
  - `delegates/__init__.py`
  - `tree_actions/__init__.py`
  - `io_formats/__init__.py`
  - `state/__init__.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
  ```bash
  python - <<'PY'
  import app, documents, undo, tree, delegates, tree_actions, io_formats, state
  print('package skeleton imports ok')
  PY
  ```
- Focused result:
  ```text
  package skeleton imports ok
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.23s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 02 — extract file-format detection

- Date: 2026-04-26
- Commit subject: Extract file-format detection
- Status: PASS
- Files changed:
  - `io_formats/detect.py`
  - `io_formats/__init__.py`
  - `file_io.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
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
- Focused result:
  ```text
  tests/test_file_io_phase4.py: 12 passed in 0.15s
  file format detection imports ok
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.23s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 03 — extract file loading

- Date: 2026-04-26
- Commit subject: Extract file loading
- Status: PASS
- Files changed:
  - `io_formats/load.py`
  - `file_io.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
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
- Focused result:
  ```text
  tests/test_file_io_phase4.py: 12 passed in 0.15s
  file loading imports ok
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.18s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 04 — extract file dumping/write

- Date: 2026-04-26
- Commit subject: Extract file dumping and atomic write
- Status: PASS
- Files changed:
  - `io_formats/dump.py`
  - `io_formats/atomic.py`
  - `io_formats/__init__.py`
  - `file_io.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
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
- Focused result:
  ```text
  tests/test_file_io_phase4.py: 12 passed in 0.15s
  file dumping imports ok
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.18s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 05 — extract QSettings coercion

- Date: 2026-04-26
- Commit subject: Extract QSettings coercion helpers
- Status: PASS
- Files changed:
  - `state/qsettings_coercion.py`
  - `view_state.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q tests/test_phase_5_4_persisted_view_state.py
  ```
- Focused result:
  ```text
  tests/test_phase_5_4_persisted_view_state.py: 3 passed in 0.13s
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.25s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 06 — move persisted view-state module

- Date: 2026-04-26
- Commit subject: Move persisted view-state module
- Status: PASS
- Files changed:
  - `state/view_state.py`
  - `view_state.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
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
- Focused result:
  ```text
  tests/test_phase_5_4_persisted_view_state.py: 3 passed in 0.16s
  view_state compatibility imports ok
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.20s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 07 — move JSON type definitions

- Date: 2026-04-26
- Commit subject: Move JSON type definitions
- Status: PASS
- Files changed:
  - `tree/types.py`
  - `enums.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
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
- Focused result:
  ```text
  tests: 34 passed in 0.13s
  type compatibility imports ok
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.20s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 08 — extract tree-item name helpers

- Date: 2026-04-26
- Commit subject: Extract tree-item name helpers
- Status: PASS
- Files changed:
  - `tree/item_names.py`
  - `tree_item.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q tests/test_smoke_model.py tests/test_tree_actions_clipboard.py tests/test_tree_actions_structure.py
  ```
- Focused result:
  ```text
  11 passed in 0.09s
  process exited with post-test segmentation fault during interpreter shutdown
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.15s
  ```
- Known failures / skipped checks:
  - Focused command reports a teardown-time segfault after all tests pass; full suite remained green and was used as gate.
- Decision:
  - proceed

## Phase 09 — extract tree-item coercion helpers

- Date: 2026-04-26
- Commit subject: Extract tree-item coercion helpers
- Status: PASS
- Files changed:
  - `tree/item_coercion.py`
  - `tree_item.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q tests/test_type_editing.py tests/test_phase_5_1_carryover.py tests/test_phase_5_2_display_formatting.py
  ```
- Focused result:
  ```text
  39 passed in 0.14s
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.18s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 10 — move JsonTreeItem

- Date: 2026-04-26
- Commit subject: Move JsonTreeItem
- Status: PASS
- Files changed:
  - `tree/item.py`
  - `tree_item.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q tests/test_smoke_model.py tests/test_tree_correctness.py tests/test_type_editing.py
  python - <<'PY'
  from tree_item import JsonTreeItem
  from tree.item import JsonTreeItem as JsonTreeItem2
  assert JsonTreeItem is JsonTreeItem2
  print('tree item compatibility imports ok')
  PY
  ```
- Focused result:
  ```text
  tests: 37 passed in 0.13s
  tree item compatibility imports ok
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.21s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 11 — extract model role/display helpers

- Date: 2026-04-26
- Commit subject: Extract model role/display helpers
- Status: PASS
- Files changed:
  - `tree/model_roles.py`
  - `tree_model.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q tests/test_smoke_model.py tests/test_phase_5_2_display_formatting.py
  ```
- Focused result:
  ```text
  7 passed in 0.07s
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.19s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 12 — move JsonTreeModel

- Date: 2026-04-26
- Commit subject: Move JsonTreeModel
- Status: PASS
- Files changed:
  - `tree/model.py`
  - `tree_model.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
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
- Focused result:
  ```text
  tests: 37 passed in 0.14s
  tree model compatibility imports ok
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.22s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 13 — extract delegate bytes codec

- Date: 2026-04-26
- Commit subject: Extract delegate bytes codec
- Status: PASS
- Files changed:
  - `delegates/bytes_codec.py`
  - `delegate.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
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
- Focused result:
  ```text
  tests: 11 passed in 0.12s
  delegate bytes codec imports ok
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.23s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 14 — extract delegate formatting helpers

- Date: 2026-04-26
- Commit subject: Extract delegate formatting helpers
- Status: PASS
- Files changed:
  - `delegates/value_formatting.py`
  - `delegate.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q tests/test_phase_5_2_display_formatting.py
  ```
- Focused result:
  ```text
  6 passed in 0.07s
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.17s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 15 — extract delegate base classes

- Date: 2026-04-26
- Commit subject: Extract delegate base classes
- Status: PASS
- Files changed:
  - `delegates/base.py`
  - `delegate.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q tests/test_phase_5_6_misc_polish.py tests/test_type_editing.py
  ```
- Focused result:
  ```text
  30 passed in 0.14s
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.19s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 16 — move name/type delegates

- Date: 2026-04-26
- Commit subject: Move name/type delegates
- Status: PASS
- Files changed:
  - `delegates/name_delegate.py`
  - `delegates/type_delegate.py`
  - `delegate.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
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
- Focused result:
  ```text
  tests: 33 passed in 0.13s
  name/type delegate compatibility imports ok
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.20s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 17 — move ValueDelegate

- Date: 2026-04-26
- Commit subject: Move ValueDelegate
- Status: PASS
- Files changed:
  - `delegates/value.py`
  - `delegate.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q tests/test_type_editing.py tests/test_phase_5_1_carryover.py tests/test_phase_5_2_display_formatting.py
  python - <<'PY'
  from delegate import ValueDelegate
  from delegates.value import ValueDelegate as ValueDelegate2
  assert ValueDelegate is ValueDelegate2
  print('value delegate compatibility imports ok')
  PY
  ```
- Focused result:
  ```text
  tests: 39 passed in 0.14s
  value delegate compatibility imports ok
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.24s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 18 — extract tree-action selection helpers

- Date: 2026-04-26
- Commit subject: Extract tree-action selection helpers
- Status: PASS
- Files changed:
  - `tree_actions/selection.py`
  - `tree_view.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q tests/test_tree_actions_clipboard.py tests/test_tree_actions_structure.py tests/test_phase_5_5_search_filter.py
  ```
- Focused result:
  ```text
  13 passed in 0.55s
  process exited with post-test segmentation fault during interpreter shutdown
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.17s
  ```
- Known failures / skipped checks:
  - Focused command reports a teardown-time segfault after tests pass; full suite remained green and was used as gate.
- Decision:
  - proceed

## Phase 19 — extract tree-action clipboard helpers

- Date: 2026-04-26
- Commit subject: Extract tree-action clipboard helpers
- Status: PASS
- Files changed:
  - `tree_actions/clipboard.py`
  - `tree_view.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q tests/test_tree_actions_clipboard.py
  ```
- Focused result:
  ```text
  6 passed in 0.08s
  process exited with post-test segmentation fault during interpreter shutdown
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.19s
  ```
- Known failures / skipped checks:
  - Focused command reports a teardown-time segfault after tests pass; full suite remained green and was used as gate.
- Decision:
  - proceed

## Phase 20 — extract paste action

- Date: 2026-04-26
- Commit subject: Extract paste action
- Status: PASS
- Files changed:
  - `tree_actions/paste.py`
  - `tree_view.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q tests/test_tree_actions_clipboard.py tests/test_tree_actions_structure.py
  ```
- Focused result:
  ```text
  10 passed in 0.09s
  process exited with post-test segmentation fault during interpreter shutdown
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.22s
  ```
- Known failures / skipped checks:
  - Focused command reports a teardown-time segfault after tests pass; full suite remained green and was used as gate.
- Decision:
  - proceed

## Phase 21 — extract structural tree actions

- Date: 2026-04-26
- Commit subject: Extract structural tree actions
- Status: PASS
- Files changed:
  - `tree_actions/structure.py`
  - `tree_view.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q tests/test_tree_actions_structure.py tests/test_tree_actions_clipboard.py tests/test_undo_redo.py tests/test_typed_undo_commands.py
  ```
- Focused result:
  ```text
  22 passed in 0.25s
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.16s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 22 — extract context menu / finish tree_view

- Date: 2026-04-26
- Commit subject: Extract context menu and finish tree_view
- Status: PASS
- Files changed:
  - `tree_actions/context_menu.py`
  - `tree_view.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
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
- Focused result:
  ```text
  tests: 13 passed in 0.13s
  process exited with post-test segmentation fault during interpreter shutdown when running the combined command
  tree_view compatibility imports ok (verified in separate run)
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.15s
  ```
- Known failures / skipped checks:
  - Focused combined command reports a teardown-time segfault after tests pass; import smoke was run separately and full suite remained green.
- Decision:
  - proceed

## Phase 23 — move undo command classes

- Date: 2026-04-26
- Commit subject: Move undo command classes
- Status: PASS
- Files changed:
  - `undo/commands.py`
  - `json_tab.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q tests/test_undo_redo.py tests/test_undo_redo_scenario.py tests/test_typed_undo_commands.py tests/test_typed_undo_perf.py
  QT_QPA_PLATFORM=offscreen pytest -q tests/test_undo_redo.py tests/test_undo_redo_scenario.py tests/test_typed_undo_commands.py tests/test_typed_undo_perf.py tests/test_phase_5_1_carryover.py
  ```
- Focused result:
  ```text
  first run: 18 passed in 1.73s
  after restoring `json_tab.time` compatibility import used by monkeypatch tests: 24 passed in 1.88s
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  final rerun: 401 passed in 3.23s
  ```
- Known failures / skipped checks:
  - Initial full-suite attempt failed at `tests/test_phase_5_1_carryover.py::test_edits_outside_merge_window_do_not_merge` because `json_tab.time` import compatibility was removed; fixed in the same phase by restoring `import time` in `json_tab.py`.
- Decision:
  - proceed

## Phase 24 — extract diff replay helper

- Date: 2026-04-26
- Commit subject: Extract diff replay helper
- Status: PASS
- Files changed:
  - `undo/diff.py`
  - `documents/tab.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q tests/test_undo_redo.py tests/test_undo_redo_scenario.py tests/test_typed_undo_commands.py tests/test_typed_undo_perf.py tests/test_perf_smoke.py
  ```
- Focused result:
  ```text
  24 passed in 2.29s
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.33s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 25 — extract JsonTab path helpers

- Date: 2026-04-26
- Commit subject: Extract JsonTab path helpers
- Status: PASS
- Files changed:
  - `documents/tab_paths.py`
  - `json_tab.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q tests/test_phase_5_3_status_bar_breadcrumb.py tests/test_phase_5_4_persisted_view_state.py tests/test_phase_5_5_search_filter.py
  ```
- Focused result:
  ```text
  8 passed in 0.58s
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.22s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 26 — extract JsonTab status helpers

- Date: 2026-04-26
- Commit subject: Extract JsonTab status helpers
- Status: PASS
- Files changed:
  - `documents/tab_status.py`
  - `json_tab.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q tests/test_phase_5_3_status_bar_breadcrumb.py tests/test_phase_5_2_display_formatting.py
  ```
- Focused result:
  ```text
  8 passed in 0.11s
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.17s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 27 — extract JsonTab save/save-as helpers

- Date: 2026-04-26
- Commit subject: Extract JsonTab save/save-as helpers
- Status: PASS
- Files changed:
  - `documents/tab_io.py`
  - `json_tab.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q tests/test_file_io_phase4.py tests/test_smoke_mainwindow.py
  ```
- Focused result:
  ```text
  22 passed in 0.21s
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.12s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 28 — extract JsonTab setup helpers

- Date: 2026-04-26
- Commit subject: Extract JsonTab setup helpers
- Status: PASS
- Files changed:
  - `documents/tab_setup.py`
  - `json_tab.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q tests/test_smoke_mainwindow.py tests/test_phase_5_5_search_filter.py tests/test_phase_5_6_misc_polish.py
  ```
- Focused result:
  ```text
  16 passed in 0.61s
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.21s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 29 — move JsonTab

- Date: 2026-04-26
- Commit subject: Move JsonTab
- Status: PASS
- Files changed:
  - `documents/tab.py`
  - `json_tab.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q tests/test_smoke_mainwindow.py tests/test_undo_redo.py tests/test_phase_5_1_carryover.py tests/test_phase_5_5_search_filter.py
  python - <<'PY'
  from json_tab import JsonTab
  from documents.tab import JsonTab as JsonTab2
  assert JsonTab is JsonTab2
  print('JsonTab compatibility imports ok')
  PY
  ```
- Focused result:
  ```text
  tests: 25 passed in 0.63s
  JsonTab compatibility imports ok
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  final rerun: 401 passed in 3.14s
  ```
- Known failures / skipped checks:
  - Initial full-suite attempt failed because `json_tab.py` shim omitted private command exports used by `tests/test_typed_undo_commands.py`; fixed in this phase by re-exporting `_ChangeTypeCmd`, `_InsertRowsCmd`, `_RenameCmd`, and `_SortKeysCmd`.
- Decision:
  - proceed

## Phase 30 — extract recent-files helper

- Date: 2026-04-26
- Commit subject: Extract recent-files helper
- Status: PASS
- Files changed:
  - `app/recent_files.py`
  - `ui.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q tests/test_file_io_phase4.py tests/test_smoke_mainwindow.py
  ```
- Focused result:
  ```text
  22 passed in 0.20s
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.17s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 31 — extract close-confirm helper

- Date: 2026-04-26
- Commit subject: Extract close-confirm helper
- Status: PASS
- Files changed:
  - `app/close_confirm.py`
  - `ui.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q tests/test_smoke_mainwindow.py tests/test_dialog_settings.py
  ```
- Focused result:
  ```text
  12 passed in 0.21s
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.16s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 32 — extract history helper

- Date: 2026-04-26
- Commit subject: Extract history helper
- Status: PASS
- Files changed:
  - `app/history.py`
  - `ui.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q tests/test_smoke_mainwindow.py tests/test_undo_redo.py tests/test_typed_undo_commands.py
  ```
- Focused result:
  ```text
  22 passed in 0.30s
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.22s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 33 — extract main-window action wiring/state

- Date: 2026-04-26
- Commit subject: Extract main-window action wiring/state
- Status: PASS
- Files changed:
  - `app/main_window_actions.py`
  - `ui.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q tests/test_smoke_mainwindow.py tests/test_phase_5_6_misc_polish.py
  ```
- Focused result:
  ```text
  13 passed in 0.17s
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.22s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 34 — move MainWindow

- Date: 2026-04-26
- Commit subject: Move MainWindow
- Status: PASS
- Files changed:
  - `app/main_window.py`
  - `ui.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q tests/test_smoke_mainwindow.py tests/test_file_io_phase4.py tests/test_dialog_settings.py
  python - <<'PY'
  from ui import MainWindow
  from app.main_window import MainWindow as MainWindow2
  assert MainWindow is MainWindow2
  print('MainWindow compatibility imports ok')
  PY
  ```
- Focused result:
  ```text
  tests: 24 passed in 0.26s
  MainWindow compatibility imports ok
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.19s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 35 — migrate internal imports

- Date: 2026-04-26
- Commit subject: Migrate internal imports
- Status: PASS
- Files changed:
  - `app/main_window.py`
  - `documents/tab.py`
  - `documents/tab_setup.py`
  - `documents/tab_status.py`
  - `delegates/type_delegate.py`
  - `delegates/value.py`
  - `tree/model.py`
  - `tree_actions/selection.py`
  - `tree_actions/clipboard.py`
  - `tree_filter_proxy.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q tests/test_smoke_mainwindow.py tests/test_type_editing.py tests/test_tree_actions_clipboard.py tests/test_tree_actions_structure.py tests/test_undo_redo.py
  ```
- Focused result:
  ```text
  53 passed in 0.29s
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.22s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 36 — optional dead-code cleanup

- Date: 2026-04-26
- Commit subject: Optional dead-code cleanup
- Status: PASS
- Files changed:
  - `app/main_window.py`
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Focused tests:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q tests/test_smoke_mainwindow.py tests/test_dialog_settings.py tests/test_undo_redo.py
  ```
- Focused result:
  ```text
  18 passed in 0.22s
  ```
- Full suite:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest -q
  ```
- Full-suite result:
  ```text
  401 passed in 3.26s
  ```
- Known failures / skipped checks:
  - none
- Decision:
  - proceed

## Phase 37 — optional remove compatibility shims

- Date: 2026-04-26
- Commit subject: Optional remove compatibility shims
- Status: SKIP
- Files changed:
  - `ai-memory/refactoring-phases.md`
  - `ai-memory/refactoring-test-log.md`
- Rationale:
  - Skipped by design to keep compatibility shims (`json_tab.py`, `ui.py`, `tree_view.py`, and similar) for stable import paths and lower integration risk.
- Focused tests:
  - not run (no runtime code changes)
- Full suite:
  - not run (doc-only phase)
- Known failures / skipped checks:
  - tests intentionally not executed for this doc-only skip decision
- Decision:
  - skip accepted
