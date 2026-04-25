# Phase 6 — Tests

## Goal

Bring test coverage of the **GUI / model layer** up to the level of the
existing widget packages. The widget stack (datetime, hex, mpq,
jsontream) is well covered; the JSON tree editor itself is not.

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
- [ ] [tests] `tests/test_tree_item.py`
      - construction from dict / list / scalar
      - `to_json` round-trip including `mpq`, datetimes, bytes
      - `set_data(0/1/2, ...)` for rename, type change, value change
      - `insert_children` produces a single NULL row
      - duplicate-name rejection under OBJECT
- [ ] [tests] `tests/test_tree_model.py`
      - `flags()` is O(1) and never raises on malformed bytes payloads
      - `rowCount` / `columnCount` / `parent` / `index` invariants
      - `setData` emits `dataChanged`
      - `removeRows` updates persistent indices correctly
      - `setData` on a malformed BYTES cell doesn't crash flags
- [ ] [tests] `tests/test_enums_parse.py`
      - boundary cases for `parse_json_type`: short strings, ambiguous
        base64, datetimes with/without TZ, nested types, unknown types
        (do not raise)
      - explicit-type pinning honoured

### Delegate tests
- [ ] [tests] `tests/test_value_delegate.py` (uses `pytest-qt`)
      - editor type matches `JsonType`
      - `setEditorData` / `setModelData` round-trip integers, mpq,
        booleans, datetimes
      - dialog-based delegates (multiline / hex) commit through
        `QPersistentModelIndex`
- [ ] [tests] `tests/test_type_delegate.py`
      - combo preselects current type
      - `setModelData` triggers a model-level type change

### File I/O tests
- [ ] [tests] `tests/test_io_roundtrip.py`
      - JSON: load `data.json`, mutate, save, reload — equal
      - YAML: same with `data.yaml`
      - mpq values survive both formats
      - datetimes survive both formats with TZ intact
- [ ] [tests] `tests/test_dirty_state.py`
      - dirty flips on edit, clears on save, clears on undo-to-clean

### GUI smoke (`pytest-qt`)
- [ ] [tests] `tests/test_smoke_app.py`
      - launch `MainWindow(filename)` with offscreen QPA
      - open a sample file, expand all, resize columns, no exception
      - trigger every menu/toolbar action that does not require user
        input; assert no exception and dirty/undo states remain
        consistent
      - close the app — confirm dialog suppressed in test mode

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
