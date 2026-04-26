# TODO & FIXME

_Last updated: 2026-04-26_

Tracks **missing/incomplete features** (TODO) and **bugs/issues** (FIXME)
discovered while auditing the JSON editor codebase. Cross-reference with
`pros-n-cons.md` for the rationale behind each item.

Format: `- [ ] [scope] description — file:symbol`

> **Status (2026-04-26)** — Phases 0–3 of the roadmap are complete; their
> items below are checked off. The remaining open items map to Phases 4–6
> (see `phases/`).

---

## TODO — missing or incomplete features

### Application shell (`ui.py`, `main.py`)
- [ ] [shell] Implement `MainWindow.setup_model(yaml_filename)` to actually
      load the file passed via CLI into a tab.
      — `ui.py:MainWindow.setup_model` (Phase 4)
- [ ] [shell] Implement `MainWindow.update_actions()` to drive enabled-state
      of insert/remove/save/copy actions from current selection and tab.
      — `ui.py:MainWindow.update_actions` (Phase 4)
- [x] [shell] Implement `MainWindow.close_tab(index)` connected to
      `tabCloseRequested`. Dirty-check confirm dialog deferred to Phase 4.
      — `ui.py:MainWindow.close_tab` ✅ Phase 0
- [x] [shell] Finish `MainWindow.copy_action()`.
      ✅ Phase 0 (placeholder); Phase 3 superseded the placeholder by
      routing copy through `JsonTab._run_tree_action`.
      — `ui.py:MainWindow.copy_action`
- [ ] [shell] Add **File → Open** action: detect format (`.json` / `.yaml`)
      and feed parsed data into a new `JsonTab`. (Phase 4)
- [ ] [shell] Add **File → Save / Save As** actions, JSON & YAML, using
      `mpq_json_default` / mpq YAML dumper. (Phase 4)
- [ ] [shell] Wire dirty/modified state per tab; reflect in tab title
      (`*` suffix) and confirm-on-close. (Phase 4)
- [ ] [shell] Add **recent files** submenu (persisted via `QSettings`). (Phase 4)
- [x] [shell] Make `MainWindow.insert_row` / `insert_child` / `remove_row`
      operate on the **currently active tab's** view, not the
      non-existent `self.view`.
      — `ui.py:MainWindow._current_view` ✅ Phase 0
- [x] [shell] Distinguish `rowInsertAction` (before) from
      `rowInsertAfterAction` (after).
      — `tree_view.insert_sibling_before` /
        `tree_view.insert_sibling_after` ✅ Phase 3

### Tab / data flow (`json_tab.py`)
- [ ] [tab] Replace hardcoded demo dict with a `data` ctor argument.
      — `json_tab.py:JsonTab.__init__` (Phase 4)
- [ ] [tab] Track and expose `JsonTab.file_path` (declared, never set). (Phase 4)
- [ ] [tab] Track dirty state; emit signal on `model.dataChanged` /
      `rowsInserted` / `rowsRemoved`. (Phase 4)
- [ ] [tab] Provide `JsonTab.to_json()` / `JsonTab.to_yaml()` save helpers
      using `tree_item.JsonTreeItem.to_json()` + the proper encoders. (Phase 4)

### Type editing (`delegate.py`, `tree_item.py`, `tree_model.py`)
- [x] [type] Implement `JsonTypeDelegate.setModelData()` so changing the
      `Type` cell actually mutates the node's `json_type` and coerces /
      resets `value` accordingly.
      — `delegate.py:JsonTypeDelegate.setModelData` ✅ Phase 2
- [x] [type] Make `JsonTypeDelegate.setEditorData()` preselect the **current**
      `JsonType` instead of always the first enum entry. Populate items in
      `createEditor`, not `setEditorData`.
      — `delegate.py:JsonTypeDelegate` ✅ Phase 2
- [x] [type] Extend `JsonTreeItem.set_data()` to accept column 0 (rename)
      and column 1 (type change). Currently only column 2 (value) is
      handled.
      — `tree_item.py:JsonTreeItem.set_data` ✅ Phase 2
- [x] [type] Implement value coercion table when `JsonType` changes
      (e.g. INTEGER → STRING, OBJECT ↔ ARRAY, BYTES ↔ ZLIB ↔ GZIP).
      ✅ Phase 2 — see `_coerce_value_for_type`.
- [x] [type] Allow user override to pin a string node as `STRING` instead
      of auto-classifying as `BYTES` / `MULTILINE` / `DATETIME` / etc.
      — `enums.py:parse_json_type`, `JsonTreeItem.explicit_type` ✅ Phase 2

### Tree mutation / context menu (`tree_view.py`, `model_actions.py`)
- [x] [tree] Wire `Cut` and `Delete` context-menu actions in
      `tree_view.show_context_menu`.
      — `tree_view.cut_selection` / `tree_view.delete_selection` ✅ Phase 3
- [x] [tree] Implement **Paste** from clipboard JSON (parse + insert as
      child or sibling).
      — `tree_view.paste_from_clipboard` ✅ Phase 3
- [x] [tree] Add context-menu entries: *Insert Sibling Before*,
      *Insert Sibling After*, *Duplicate*, *Move Up/Down*,
      *Sort Keys*, *Change Type*. (Collapse/Expand All deferred to Phase 5.)
      ✅ Phase 3 — `tree_view.show_context_menu`.
- [x] [tree] Either remove or properly implement *Insert Column* — removed.
      ✅ Phase 1
- [x] [tree] Make `model.insertRow`/`insertRows` create properly initialized
      `JsonTreeItem`s (e.g. `value=None` → `JsonType.NULL`).
      — `tree_item.py:JsonTreeItem.insert_children` ✅ Phase 1
- [x] [tree] When inserting under an `OBJECT` parent, generate
      a unique name. — `_unique_child_name` ✅ Phase 1
- [x] [tree] Add undo/redo via `QUndoStack` covering set/insert/remove on
      the model.
      ✅ Phase 3 — typed action/compensation commands per mutation
      (`_MoveRowCmd`, `_RenameCmd`, `_EditValueCmd`, `_ChangeTypeCmd`,
      `_InsertRowsCmd`, `_RemoveRowsCmd`, `_SortKeysCmd`). No
      whole-document snapshots — see
      `phases/phase-3-compensating-undo-plan.md`.

### I/O & serialization (Phase 4)
- [ ] [io] Provide YAML round-trip through `mpq2py` YAML loader/dumper.
- [ ] [io] Provide JSON round-trip through `mpq_json_default` and a
      streaming reader for large files (paired with `jsontream`).
- [ ] [io] Validate datetime / bytes strings on save (raise readable
      errors).

### UX & polish (Phase 5)
- [ ] [ux] Implement `displayText()` on `ValueDelegate` for nicer display
      of `PERCENT` (`50%`), `mpq` floats, datetimes, and elided long
      strings.
- [ ] [ux] Add a status bar message describing current selection
      (the C++ original did `Position: (row, column)`).
- [ ] [ux] Resize columns to contents on tab switch / model reset.
- [ ] [ux] Persist column widths and tree expansion state per file path.
- [ ] [ux] Add search / filter bar per tab.

### Tests
- [x] [tests] Add unit tests for `JsonTreeModel` core mutations
      (insert/remove/setData/flags edge cases).
      ✅ Phase 1/2 — `tests/test_tree_correctness.py`, `test_type_editing.py`.
      Phase 6 will fill the remaining invariants.
- [x] [tests] Add unit tests for `JsonTreeItem.to_json()` strictness.
      ✅ Phase 1 — `test_to_json_raises_for_unnamed_object_child`.
      Round-trip with `mpq` / datetimes / bytes still pending (Phase 6).
- [x] [tests] Add unit tests for `parse_json_type` priority rules and
      ambiguous strings (`"abcd"` → STRING after stricter heuristic).
      ✅ Phase 1 — `test_parse_json_type_is_total_and_has_narrower_heuristics`.
- [x] [tests] Add a smoke test that `QApplication` + `JsonTab` constructs
      successfully (using `pytest-qt`).
      ✅ Phase 6 partial — `tests/test_smoke_mainwindow.py`.
- [x] [tests] Round-trip / typed-command coverage for tree actions and
      undo stack.
      ✅ Phase 3 — `tests/test_tree_actions_clipboard.py`,
      `test_tree_actions_structure.py`, `test_undo_redo.py`,
      `test_undo_redo_scenario.py`, `test_typed_undo_commands.py`,
      `test_typed_undo_perf.py`, `test_perf_smoke.py`.

### Code hygiene
- [x] [hygiene] Strip the embedded C++ reference docstrings from
      `tree_model.py`, `tree_item.py`, `ui.py` once the port is settled.
      ✅ Phase 0 — replaced with a single source-link comment.
- [x] [hygiene] Remove unused imports in `ui.py` (`yaml`,
      `HeaderViewEditorMixin`, `JsonTypeDelegate`, `JsonTreeModel`,
      `show_context_menu`, `functools`).
      ✅ Phase 0
- [ ] [hygiene] Remove demo-data imports from `json_tab.py` once real
      loading is wired (`base64`, `gzip`, `zlib`, `gmpy2`). (Phase 4)
- [x] [hygiene] Clean up commented-out C++/Python scaffolding inside
      `ui.py:setup_model` / `update_actions`.
      ✅ Phase 0

---

## FIXME — bugs & known issues

### Confirmed bugs (all resolved in Phases 0–2 ✅)
- [x] [BUG] `tests/test_mpq2py.py::test_mpq_with_json` failed — actual
      cause was `mpq_json_default` returning the full
      `(Decimal, mpq)` tuple from `mpq_serialization`, not a
      `simplejson` shadowing issue. Fix: return `mpq_serialization(obj)[0]`.
      ✅ Phase 0 — `mpq2py/__init__.py`
- [x] [BUG] `ui.py::MainWindow.copy_action` was syntactically incomplete.
      Replaced with a status-bar placeholder; real impl in Phase 3.
      ✅ Phase 0
- [x] [BUG] `MainWindow.insert_row` / `insert_child` / `remove_row` etc.
      referenced non-existent `self.view`. Replaced with
      `_current_view()` helper.
      ✅ Phase 0
- [x] [BUG] `JsonTypeDelegate.setModelData()` was a `pass`.
      ✅ Phase 2 — now commits via `model.setData(index, json_type)`.
- [x] [BUG] `JsonTreeItem.set_data()` ignored columns 0 and 1.
      ✅ Phase 2 — full table coercion + name validation.
- [x] [BUG] `JsonTreeItem.insert_children()` seeded `value=[None]*columns`.
      ✅ Phase 1 — now `value=None` (single NULL row).
- [x] [BUG] Inserted children under OBJECT had `name=None`.
      ✅ Phase 1 — `_unique_child_name` generates `new_key`, `new_key_2`, …
      `to_json()` raises `ValueError` for any remaining `None` name.
- [x] [BUG] `JsonTreeModel.insertColumns`/`removeColumns` emitted Qt
      column-change signals around always-False work.
      ✅ Phase 1 — model overrides removed entirely.
- [x] [BUG] `parse_json_type` raised on unknown value types.
      ✅ Phase 1 — total: returns STRING with logger warning.
- [x] [BUG] `parse_json_type` over-classified short strings as `BYTES`.
      ✅ Phase 1 — `_looks_like_base64` (length ≥ 16, regex, < 0.85
      printable-byte ratio); datetime checked first.
- [x] [BUG] `parse_json_type` auto-promoted `[0, 1]` floats to `PERCENT`.
      ✅ Phase 1 — PERCENT auto-detection removed; only reachable via
      explicit type pinning (Phase 2).
- [x] [BUG] `JsonTypeDelegate.setEditorData` ignored current type.
      ✅ Phase 2 — `findData(item.json_type)` preselects.
- [x] [BUG] `MainWindow.close_tab` had `pass` body and dropped its index
      argument.
      ✅ Phase 0 — `(self, index: int) -> None` with `removeTab` +
      `deleteLater`.
- [x] [BUG] `ui.py` imported `functools`, `yaml`, `HeaderViewEditorMixin`,
      `JsonTypeDelegate`, `JsonTreeModel`, `show_context_menu` for nothing.
      ✅ Phase 0 — all unused imports removed.
- [x] [BUG] `JsonTreeModel.flags()` decoded base64/zlib/gzip on every
      query.
      ✅ Phase 1 — moved to cached `JsonTreeItem.editable`, recomputed
      only on construction / `_apply_typed_value`. Malformed payloads
      cleanly become non-editable instead of raising.

### Confirmed bugs — still open (Phase 4+)
- [ ] [BUG] `ValueDelegate.createEditor` for `MULTILINE` / `BYTES` /
      `ZLIB` / `GZIP` opens a `QDialog` parented to the editor parent
      and returns `None`. Reentrant edit triggers can stack dialogs.
      — `delegate.py:ValueDelegate.createEditor` (Phase 5)
- [ ] [BUG] The dialog callbacks capture raw `QModelIndex` by closure;
      if the model is mutated while the dialog is open the index becomes
      stale and `setData` may write to the wrong row. Convert to
      `QPersistentModelIndex` and route the commit through
      `JsonTab.commit_set_data` so the edit lands on the typed-undo
      stack.
      — `delegate.py:ValueDelegate.createEditor` (Phase 5)
- [ ] [BUG] `QHexDialog` is constructed eagerly with
      `decode_bytes(item.value, item.json_type)` inside `createEditor`. A
      malformed `ZLIB`/`GZIP` payload raises before the dialog is shown.
      Wrap construction in try/except and surface via status bar.
      — `delegate.py:ValueDelegate.createEditor` (Phase 5)
- [x] [BUG] Context-menu `Cut` and `Delete` actions are created but
      never `.triggered.connect(...)`'d. ✅ Phase 3.
- [x] [BUG] `rowInsertAction` and `rowInsertAfterAction` both call
      `MainWindow.insert_row` — there is no "insert before" semantic.
      ✅ Phase 3 — separate `tree_view.insert_sibling_before` /
      `insert_sibling_after`.

### Suspected issues / smells
- [ ] [SMELL] `JsonTreeModel.data()` returns `None` implicitly for
      non-Display/Edit roles; consider an explicit `return None` and
      handle `Qt.ItemDataRole.ToolTipRole` for long values. (Phase 5)
- [ ] [SMELL] `JsonTreeItem.row()` returns `0` for the root (no parent)
      instead of `-1`; tolerable but a footgun for future code.
- [x] [SMELL] `ValueDelegate.setEditorData` for BOOLEAN used
      `(not item.value) * 1`. ✅ Phase 2 — replaced with explicit
      `setCurrentIndex(0 if bool(value) else 1)`.
- [ ] [SMELL] `ValueDelegate` raises `ValueError` when `json_type` is
      unsupported (`OBJECT`, `ARRAY`, `NULL`); these branches should be
      unreachable thanks to `flags()`, but a defensive `return None`
      would fail more gracefully. (Phase 3)
- [x] [SMELL] `JsonTreeModel.cleanup_columns_removal` was a nested
      `removeRows` call inside a column-removal end signal.
      ✅ Phase 1 — column API removed entirely; concern is moot.
- [x] [SMELL] `enums.parse_json_type` used bare `except:` clauses.
      ✅ Phase 0 — replaced with `except Exception:`.
