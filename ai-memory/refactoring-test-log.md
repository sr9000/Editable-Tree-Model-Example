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
