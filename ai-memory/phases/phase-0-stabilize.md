# Phase 0 — Stabilize  ✅ DONE (2026-04-25)

## Goal

Bring the repository to a **green, runnable baseline**: every existing
toolbar action must not crash, the test suite must pass, dead
scaffolding must be removed. No new features.

## Entry criteria

- Repo as scanned on 2026-04-25.
- `pytest -q` shows one failure (`test_mpq_with_json`).
- `MainWindow` toolbar row actions raise `AttributeError`.

## Exit criteria

- `pytest -q` is fully green.
- Launching the app and clicking every menu/toolbar entry does not raise.
  Unimplemented entries either are disabled or show a "not yet
  implemented" status-bar message — never a traceback.
- `tree_model.py`, `tree_item.py`, `ui.py` no longer carry the embedded
  C++ reference blocks.
- `ui.py` and `json_tab.py` have no unused imports.

## Work items

### Fix failing test
- [x] [BUG] Investigate `tests/test_mpq2py.py::test_mpq_with_json` — likely
      a `simplejson` shadowing of stdlib `json`. Force stdlib `json` in
      `mpq2py` (or add `import json as _stdjson`) and confirm `pytest -q`
      is green.
      — `mpq2py/__init__.py`, `tests/test_mpq2py.py`
      → **Resolved**: actual root cause was `mpq_json_default` returning the
        full `(Decimal, mpq)` tuple from `mpq_serialization`, causing
        infinite recursion in `simplejson`. Fix: return `mpq_serialization(obj)[0]`.

### Fix runtime crashes in MainWindow
- [x] [BUG] Replace every `self.view` reference inside `MainWindow` with a
      helper `self._current_view()` that returns
      `self.tabWidget.currentWidget().view` or `None`. Bail out cleanly
      when no tab is open.
      — `ui.py:MainWindow.insert_row`, `insert_child`, `insert_column`,
        `remove_row`, `remove_column`, `copy_action`
- [x] [BUG] Finish or delete `MainWindow.copy_action` (currently truncated).
      For Phase 0, deleting it and unbinding any caller is acceptable;
      a real implementation lands in Phase 3.
      — `ui.py:MainWindow.copy_action`
      → Kept as a stub that flashes a status-bar "not yet implemented".
- [x] [BUG] Implement minimal `MainWindow.close_tab(index: int)`:
      `self.tabWidget.removeTab(index)`. Dirty-check is added in Phase 4.
      — `ui.py:MainWindow.close_tab`
      → Includes `widget.deleteLater()` cleanup and `update_actions()` call.

### Hygiene
- [x] [hygiene] Remove the C++ docstring blocks at the top of
      `tree_model.py`, `tree_item.py`, `ui.py`. Keep a one-line link to the
      original example URL if useful.
- [x] [hygiene] Remove unused imports in `ui.py` (`yaml`,
      `HeaderViewEditorMixin`, `JsonTypeDelegate`, `JsonTreeModel`,
      `show_context_menu`, `functools`).
- [x] [hygiene] Remove the commented-out scaffolding inside
      `MainWindow.setup_model` and `MainWindow.update_actions`. The empty
      `pass` body is fine until Phase 4 picks it up.
- [x] [hygiene] Replace bare `except:` clauses in `enums.parse_json_type`
      with `except Exception:` so `KeyboardInterrupt` propagates.

### Smoke check
- [x] Add a tiny `pytest-qt`-free smoke test that constructs
      `JsonTreeModel({"a": 1})` and walks rows/columns. (Full GUI smoke
      test lands in Phase 6.)
      → `tests/test_smoke_model.py`. A larger `tests/test_smoke_mainwindow.py`
        was also delivered ahead of schedule with `pytest-qt`-style fixtures.

## Implementation notes

- `tests/test_smoke_mainwindow.py` discovered a related regression — Qt
  Designer generated `Ui_MainWindow.statusBar = QStatusBar(...)`, which
  shadows `QMainWindow.statusBar()`. All call sites now use the attribute
  form `self.statusBar.showMessage(...)`.
- `JsonTab` now accepts a `status_message_callback` so phase-2 type
  changes can surface lossy-coercion messages without coupling to
  `MainWindow`.

## Final test status

```
308 passed in 0.47s
```

## Tips & Deep Dives

### Diagnosing `test_mpq_with_json`

The actual root cause is **not** `simplejson` shadowing stdlib `json` — the
test itself does `import simplejson as json` deliberately, and the YAML
twin test passes. The defect is in `mpq_json_default`:

```python
def mpq_json_default(obj):
    if isinstance(obj, mpq):
        return mpq_serialization(obj)   # returns a tuple (Decimal, mpq)
    raise TypeError(...)
```

`mpq_serialization(q)` returns `(value, denominator)` where the second
slot is itself an `mpq`. `simplejson` receives the tuple, serializes the
`Decimal` fine, then encounters the `mpq` again and recurses — leading
to infinite recursion or a `TypeError`.

**Fix candidates** (decide in this phase, document in `mpq2py`):

1. Return only the value: `return mpq_serialization(obj)[0]`.
2. Or return `float(obj)` / `str(obj)` — but that defeats the point of
   exact serialization.

Verify with:

```bash
python -c "import simplejson as j; from gmpy2 import mpq; \
  from mpq2py import mpq_json_default; \
  print(j.dumps({'q': mpq('1/3')}, default=mpq_json_default, indent=2))"
```

Then confirm `pytest -q tests/test_mpq2py.py` is green.

### `MainWindow._current_view()` helper pattern

```python
def _current_tab(self) -> "JsonTab | None":
    return self.tabWidget.currentWidget()  # may be None

def _current_view(self):
    tab = self._current_tab()
    return tab.view if tab is not None else None
```

Then guard every action:

```python
def insert_row(self):
    view = self._current_view()
    if view is None:
        return
    ...
```

This avoids the `AttributeError: 'MainWindow' object has no attribute 'view'`
crash without changing semantics.

### Closing tabs safely

The `tabCloseRequested` signal sends an `int` index. Update the slot
signature accordingly:

```python
def close_tab(self, index: int) -> None:
    widget = self.tabWidget.widget(index)
    self.tabWidget.removeTab(index)
    if widget is not None:
        widget.deleteLater()
```

`deleteLater()` matters: without it, the `JsonTab` keeps the model and
`QTreeView` alive until the `MainWindow` is destroyed, which leaks during
long sessions.

### Stripping the C++ docstrings

The C++ blocks are top-of-file `"""..."""` strings — Python treats them
as expression statements, so deleting them changes no semantics. Land
them as **one mechanical commit** with a message like
`chore: drop ported C++ reference blocks`, so subsequent bug-fix commits
have small, reviewable diffs. Replace with a one-liner:

```python
# Ported from: https://code.qt.io/cgit/qt/qtbase.git/tree/examples/widgets/itemviews/editabletreemodel
```

### Bare `except:` cleanup

```python
# before
try:
    raw = base64.b64decode(s, validate=True)
    ...
except:
    pass

# after
except Exception:
    pass
```

`KeyboardInterrupt` and `SystemExit` are both `BaseException` — not
`Exception` — so they propagate correctly with the narrower clause.

### Smoke test scaffold

Place in `tests/test_smoke_model.py`:

```python
from tree_model import JsonTreeModel

def test_construct_simple_model():
    m = JsonTreeModel({"a": 1, "b": [2, 3]})
    assert m.columnCount() == 3
    assert m.rowCount() == 2  # "a" and "b"
    b = m.index(1, 0)
    assert m.rowCount(b) == 2  # 2 array elements
```

No `QApplication` needed — `QAbstractItemModel` works without an event
loop as long as it has no parent widget.

## Risks / notes

- Touching `mpq2py` may surface latent issues in dependent tests
  (`test_pretty_jsontream` etc.). Run the full suite, not just the failing
  case.
- Removing C++ docstrings is a large mechanical diff. Land it as a
  separate commit so it does not pollute the bug-fix diff.
- Do **not** refactor `JsonTreeItem` insertion logic here — that is
  Phase 1.
