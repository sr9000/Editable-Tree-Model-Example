# Phase 0 — Stabilize

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
- [ ] [BUG] Investigate `tests/test_mpq2py.py::test_mpq_with_json` — likely
      a `simplejson` shadowing of stdlib `json`. Force stdlib `json` in
      `mpq2py` (or add `import json as _stdjson`) and confirm `pytest -q`
      is green.
      — `mpq2py/__init__.py`, `tests/test_mpq2py.py`

### Fix runtime crashes in MainWindow
- [ ] [BUG] Replace every `self.view` reference inside `MainWindow` with a
      helper `self._current_view()` that returns
      `self.tabWidget.currentWidget().view` or `None`. Bail out cleanly
      when no tab is open.
      — `ui.py:MainWindow.insert_row`, `insert_child`, `insert_column`,
        `remove_row`, `remove_column`, `copy_action`
- [ ] [BUG] Finish or delete `MainWindow.copy_action` (currently truncated).
      For Phase 0, deleting it and unbinding any caller is acceptable;
      a real implementation lands in Phase 3.
      — `ui.py:MainWindow.copy_action`
- [ ] [BUG] Implement minimal `MainWindow.close_tab(index: int)`:
      `self.tabWidget.removeTab(index)`. Dirty-check is added in Phase 4.
      — `ui.py:MainWindow.close_tab`

### Hygiene
- [ ] [hygiene] Remove the C++ docstring blocks at the top of
      `tree_model.py`, `tree_item.py`, `ui.py`. Keep a one-line link to the
      original example URL if useful.
- [ ] [hygiene] Remove unused imports in `ui.py` (`yaml`,
      `HeaderViewEditorMixin`, `JsonTypeDelegate`, `JsonTreeModel`,
      `show_context_menu`, `functools`).
- [ ] [hygiene] Remove the commented-out scaffolding inside
      `MainWindow.setup_model` and `MainWindow.update_actions`. The empty
      `pass` body is fine until Phase 4 picks it up.
- [ ] [hygiene] Replace bare `except:` clauses in `enums.parse_json_type`
      with `except Exception:` so `KeyboardInterrupt` propagates.

### Smoke check
- [ ] Add a tiny `pytest-qt`-free smoke test that constructs
      `JsonTreeModel({"a": 1})` and walks rows/columns. (Full GUI smoke
      test lands in Phase 6.)

## Risks / notes

- Touching `mpq2py` may surface latent issues in dependent tests
  (`test_pretty_jsontream` etc.). Run the full suite, not just the failing
  case.
- Removing C++ docstrings is a large mechanical diff. Land it as a
  separate commit so it does not pollute the bug-fix diff.
- Do **not** refactor `JsonTreeItem` insertion logic here — that is
  Phase 1.
