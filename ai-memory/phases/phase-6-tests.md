# Phase 6 — Tests

> **Status (2026-04-26): ⚠️ partial.** 401 tests pass under
> `QT_QPA_PLATFORM=offscreen pytest -q` (no post-run segfault). Phase-5
> sub-phases each shipped focused suites:
> `test_phase_5_1_carryover.py`, `test_phase_5_2_display_formatting.py`,
> `test_phase_5_3_status_bar_breadcrumb.py`,
> `test_phase_5_4_persisted_view_state.py`,
> `test_phase_5_5_search_filter.py`, `test_phase_5_6_misc_polish.py`,
> plus `test_file_io_phase4.py`. Still missing: full
> `ValueDelegate` editor matrix (`tests/test_value_delegate.py`),
> JSON/YAML round-trip property tests against `data.json`/`data.yaml`
> with mpq + datetimes, model invariants (`removeRows` persistent
> indices, 3-level `parent`/`index` round-trip), `pytest-qt` in
> `requirements.txt`, `make test` target, and a coverage snapshot.

## Goal

Bring test coverage of the **GUI / model layer** up to the level of the
existing widget packages. The widget stack (datetime, hex, mpq,
jsontream) is well covered; the JSON tree editor itself is not.

## Already shipped (Phases 0–3)

A substantial slice of Phase 6 was delivered alongside Phases 0–3:

- ✅ `tests/test_smoke_model.py` — model construction smoke test.
- ✅ `tests/test_smoke_mainwindow.py` — full `MainWindow` lifecycle:
  construct, status-bar usability, `create_new_file`, multi-tab open
  + close, type-change regressions for both modal-editor types
  (NULL/ARRAY/OBJECT/MULTILINE/BYTES) and inline-editor types
  (INTEGER/FLOAT/STRING/BOOLEAN/PERCENT/DATE).
- ✅ `tests/test_tree_correctness.py` — insertion semantics, naming,
  `to_json` round-trip strictness, narrowed `parse_json_type` heuristics,
  malformed binary `flags()` safety, dead column API, `action_insert_child`.
- ✅ `tests/test_type_editing.py` — name editing under OBJECT/ARRAY,
  type-change coercion, type pinning vs. base64-like values, delegate
  preselection and commit.
- ✅ `tests/test_tree_actions_clipboard.py` — copy / cut / paste round
  trips through the `application/x-json-tree` MIME, name-collision
  avoidance under OBJECT parents.
- ✅ `tests/test_tree_actions_structure.py` — duplicate, move up/down,
  insert-sibling-before/after, insert-child, sort-keys structural
  invariants.
- ✅ `tests/test_undo_redo.py` — per-action undo/redo + label format
  (`[HH:MM:SS] {action} @ {qname}`).
- ✅ `tests/test_undo_redo_scenario.py` — 16-step end-to-end scenario
  covering every JsonType + every mutating action with branched
  undo/redo + redo-stack truncation.
- ✅ `tests/test_typed_undo_commands.py` — every routine action pushes
  the correct typed `QUndoCommand` subclass (no `_SnapshotCommand`).
- ✅ `tests/test_typed_undo_perf.py` — wall-clock + transitive command
  state size bounds proving undo entries store O(affected subset),
  never the full document.
- ✅ `tests/test_perf_smoke.py` — generic perf bounds (3000-row
  fan-out).
- ✅ Baseline: **343 tests pass** as of 2026-04-26 (Phases 0–3
  shipped).

The remaining Phase 6 scope below covers what's still missing.

## Entry criteria

- Phases 0–5 complete. Behaviour is stable enough to write
  regression tests against.

## Exit criteria

- `pytest -q` covers the model, item, delegates, file I/O, and at
  least one end-to-end GUI smoke flow.
- CI-equivalent target in `Makefile` (`make test`) runs the suite
  headlessly with `QT_QPA_PLATFORM=offscreen`.
- A coverage report (text-only is fine) is generated and committed to
  `ai-memory/coverage.md` (or similar).

## Work items

### Model / item unit tests
- [x] `tests/test_tree_correctness.py` (delivered)
      - `test_insert_row_under_object_creates_unique_named_null_children`
      - `test_insert_row_under_array_keeps_name_none`
      - `test_set_data_recomputes_json_type`
      - `test_to_json_raises_for_unnamed_object_child`
      - `test_parse_json_type_is_total_and_has_narrower_heuristics`
      - `test_flags_are_safe_for_malformed_binary_payloads`
      - `test_column_api_returns_false_without_changing_model`
      - `test_action_insert_child_main_path`
- [x] `tests/test_type_editing.py` (delivered)
      - `test_name_editing_object_and_duplicate_rejection`
      - `test_array_name_column_shows_index_and_is_read_only`
      - `test_type_change_sets_explicit_type_and_coerces_value`
      - `test_type_pinning_keeps_string_for_base64_like_value`
      - `test_json_type_delegate_preselects_and_commits`
- [ ] [tests] **still missing** model invariants:
      - `setData` emits `dataChanged` for the full row (cols 0..2)
      - `removeRows` updates persistent indices correctly
      - `parent()` / `index()` round-trip on a 3-level tree
      - `change_type` lossy=True only when there were children
      - `_unique_child_name` collision avoidance with reserved-name set

### Delegate tests
- [x] `tests/test_type_editing.py::test_json_type_delegate_preselects_and_commits`
- [ ] [tests] `tests/test_value_delegate.py` (uses `pytest-qt`)
      - editor type matches `JsonType` for all inline-editor types
      - `setEditorData` / `setModelData` round-trip integers, mpq,
        booleans, datetimes
      - dispatch by **editor widget class** survives stale editors
        (the code-level fix shipped in Phase 2 should be locked in by a
        focused regression test, complementing the existing
        `test_cycling_inline_types_does_not_log_edit_failed`)
      - dialog-based delegates (multiline / hex) commit through
        `QPersistentModelIndex` and route through
        `JsonTab.commit_set_data` (depends on the Phase 5 carry-over
        fix from `phase-5-ux-polish.md`).

### File I/O tests
- [ ] [tests] `tests/test_io_roundtrip.py`
      - JSON: load `data.json`, mutate, save, reload — equal
      - YAML: same with `data.yaml`
      - mpq values survive both formats
      - datetimes survive both formats with TZ intact
- [ ] [tests] `tests/test_dirty_state.py`
      - dirty flips on edit, clears on save, clears on undo-to-clean

### GUI smoke (`pytest-qt`)
- [x] `tests/test_smoke_mainwindow.py` (delivered)
      - launches `MainWindow(yaml_filename="")`
      - `test_mainwindow_constructs`
      - `test_mainwindow_status_bar_is_usable` (regression for the
        Designer-generated `statusBar` shadowing `statusBar()`)
      - `test_create_new_file_action_opens_tab`
      - `test_create_multiple_new_file_tabs` (also exercises `close_tab`)
      - parametrized `test_type_change_does_not_log_edit_failed`
      - `test_cycling_inline_types_does_not_log_edit_failed`
- [x] Phase 3 tree-action coverage (delivered) — see
      `test_tree_actions_clipboard.py`, `test_tree_actions_structure.py`,
      `test_undo_redo.py`, `test_undo_redo_scenario.py`,
      `test_typed_undo_commands.py`, `test_typed_undo_perf.py`.
- [ ] [tests] Extend smoke to cover Phase 4+ actions once they land
      (file open/save round-trip, dirty marker, recent-files menu).

### Tooling
- [ ] [tooling] Add `pytest-qt` to `requirements.txt`.
- [ ] [tooling] Add a `make test` target running
      `QT_QPA_PLATFORM=offscreen pytest -q`.
- [ ] [tooling] Add `coverage`/`pytest-cov` and produce a short
      summary committed to `ai-memory/coverage.md`.

## Tips & Deep Dives

### Headless Qt setup

`pytest-qt` provides a session-scoped `qapp` fixture. To make it cooperate
with this repo:

`tests/conftest.py`:

```python
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# pytest-qt creates QApplication itself; do NOT import main.py top-level.

import pytest
from PySide6.QtCore import QSettings

@pytest.fixture(autouse=True)
def _isolated_qsettings(tmp_path, monkeypatch):
    # Keep persisted state out of the user's real registry / config files
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path))
    yield
```

This pins both QPA and QSettings to ephemeral storage — required for
deterministic tests of recent-files / view-state.

### Asserting model invariants

Reusable helpers in `tests/_model_helpers.py`:

```python
def walk(model, parent=QModelIndex()):
    for r in range(model.rowCount(parent)):
        idx = model.index(r, 0, parent)
        yield idx
        yield from walk(model, idx)

def all_paths(model):
    return [
        " > ".join(_name_chain(idx)) for idx in walk(model)
    ]

def _name_chain(idx):
    parts = []
    while idx.isValid():
        item = idx.internalPointer()
        parts.append(item.name if item.name is not None else f"[{item.row()}]")
        idx = idx.parent()
    return list(reversed(parts))
```

These let assertions read like `assert "a > b > 0" in all_paths(model)`,
which makes failure messages legible.

### Round-trip property test

```python
@pytest.mark.parametrize("payload", [
    {"a": 1, "b": [True, None, "hi"]},
    {"q": Decimal("0.25"), "ts": "2024-06-01T12:34:56+00:00"},
    [],
    {},
])
def test_to_json_roundtrip(payload):
    item = JsonTreeItem(value=payload)
    assert item.to_json() == payload
```

Add `hypothesis` later for deeper coverage; the parametrized list is
enough for Phase 6 baseline.

### `qtbot` patterns

```python
def test_value_delegate_int(qtbot, qapp):
    model = JsonTreeModel({"x": 42})
    view = QTreeView(); view.setModel(model)
    view.setItemDelegateForColumn(2, ValueDelegate())
    qtbot.addWidget(view)

    idx = model.index(0, 2)
    view.edit(idx)
    editor = view.indexWidget(idx) or view.findChild(QBigIntSpinBox)
    qtbot.keyClicks(editor, "100")
    qtbot.keyClick(editor, Qt.Key_Return)

    assert model.data(idx, Qt.EditRole) == 100
```

For dialog-based delegates, monkey-patch `QHexDialog.open` /
`QMultilineDialog.open` to invoke the callback synchronously.

### Coverage harness

```bash
pip install coverage pytest-cov
QT_QPA_PLATFORM=offscreen pytest --cov=. --cov-report=term-missing -q
```

Add to `Makefile`:

```make
test:
	QT_QPA_PLATFORM=offscreen pytest -q

cov:
	QT_QPA_PLATFORM=offscreen pytest --cov=. --cov-report=term --cov-report=html -q
```

Drop `htmlcov/` into `.gitignore`. Commit a short text snapshot to
`ai-memory/coverage.md` so trends are visible across PRs.

### Skip decorators

Some boxes do not have `gmpy2` wheels for every Python version on CI;
add a skip marker to keep the suite portable:

```python
gmpy2 = pytest.importorskip("gmpy2")
```

### Avoiding clipboard flakiness

`QApplication.clipboard()` is a no-op on `offscreen` for some Qt
versions. For copy/paste tests, monkey-patch:

```python
@pytest.fixture
def fake_clipboard(monkeypatch):
    store = {"mime": None, "text": ""}
    monkeypatch.setattr("PySide6.QtWidgets.QApplication.clipboard",
                        lambda: _FakeClipboard(store))
    return store
```

…where `_FakeClipboard` mimics `setMimeData` / `mimeData` / `setText`.
Tests then assert against `store["mime"]` directly.

### CI smoke discipline

Keep the GUI smoke test minimal — *show, don't drive*:

```python
def test_smoke_open_close(qtbot, tmp_path):
    f = tmp_path / "x.json"; f.write_text('{"a": 1}')
    win = MainWindow(str(f))
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    assert win.tabWidget.count() == 1
```

Anything more elaborate (clicks on menu items, keyboard shortcuts) tends
to be flaky cross-platform; cover that behaviour with model/delegate-level
tests instead.

## Risks / notes

- `pytest-qt` brings in a `qtbot` fixture that conflicts with bare
  `QApplication` constructed in `main.py`. Tests should always use
  `qtbot.app` rather than instantiating a second `QApplication`.
- Headless `offscreen` mode hides clipboard access — tests for
  copy/paste should mock `QApplication.clipboard()` or use
  `QGuiApplication.clipboard().setText`.
- File I/O round-trip tests should write to `tmp_path`, never to the
  repo's `data.json` / `data.yaml`.
