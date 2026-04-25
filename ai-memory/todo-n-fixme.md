# TODO & FIXME

_Last updated: 2026-04-25_

Tracks **missing/incomplete features** (TODO) and **bugs/issues** (FIXME)
discovered while auditing the JSON editor codebase. Cross-reference with
`pros-n-cons.md` for the rationale behind each item.

Format: `- [ ] [scope] description — file:symbol`

---

## TODO — missing or incomplete features

### Application shell (`ui.py`, `main.py`)
- [ ] [shell] Implement `MainWindow.setup_model(yaml_filename)` to actually
      load the file passed via CLI into a tab.
      — `ui.py:MainWindow.setup_model`
- [ ] [shell] Implement `MainWindow.update_actions()` to drive enabled-state
      of insert/remove/save/copy actions from current selection and tab.
      — `ui.py:MainWindow.update_actions`
- [ ] [shell] Implement `MainWindow.close_tab(index)` connected to
      `tabCloseRequested`, with dirty-check confirm dialog.
      — `ui.py:MainWindow.close_tab`
- [ ] [shell] Finish `MainWindow.copy_action()` (currently truncated).
      Should copy the active tab's selected subtree as JSON.
      — `ui.py:MainWindow.copy_action`
- [ ] [shell] Add **File → Open** action: detect format (`.json` / `.yaml`)
      and feed parsed data into a new `JsonTab`.
- [ ] [shell] Add **File → Save / Save As** actions, JSON & YAML, using
      `mpq_json_default` / mpq YAML dumper.
- [ ] [shell] Wire dirty/modified state per tab; reflect in tab title
      (`*` suffix) and confirm-on-close.
- [ ] [shell] Add **recent files** submenu (persisted via `QSettings`).
- [ ] [shell] Make `MainWindow.insert_row` / `insert_child` / `remove_row`
      operate on the **currently active tab's** view, not the
      non-existent `self.view`.
      — `ui.py:MainWindow.insert_row`
- [ ] [shell] Distinguish `rowInsertAction` (before) from
      `rowInsertAfterAction` (after); currently both call the same slot.
      — `ui.py:setup_connections`

### Tab / data flow (`json_tab.py`)
- [ ] [tab] Replace hardcoded demo dict with a `data` ctor argument.
      — `json_tab.py:JsonTab.__init__`
- [ ] [tab] Track and expose `JsonTab.file_path` (already declared, never set).
- [ ] [tab] Track dirty state; emit signal on `model.dataChanged` /
      `rowsInserted` / `rowsRemoved`.
- [ ] [tab] Provide `JsonTab.to_json()` / `JsonTab.to_yaml()` save helpers
      using `tree_item.JsonTreeItem.to_json()` + the proper encoders.

### Type editing (`delegate.py`, `tree_item.py`, `tree_model.py`)
- [ ] [type] Implement `JsonTypeDelegate.setModelData()` so changing the
      `Type` cell actually mutates the node's `json_type` and coerces /
      resets `value` accordingly.
      — `delegate.py:JsonTypeDelegate.setModelData`
- [ ] [type] Make `JsonTypeDelegate.setEditorData()` preselect the **current**
      `JsonType` instead of always the first enum entry. Populate items in
      `createEditor`, not `setEditorData`.
      — `delegate.py:JsonTypeDelegate`
- [ ] [type] Extend `JsonTreeItem.set_data()` to accept column 0 (rename)
      and column 1 (type change). Currently only column 2 (value) is
      handled.
      — `tree_item.py:JsonTreeItem.set_data`
- [ ] [type] Implement value coercion table when `JsonType` changes
      (e.g. INTEGER → STRING, OBJECT ↔ ARRAY, BYTES ↔ ZLIB ↔ GZIP).
- [ ] [type] Allow user override to pin a string node as `STRING` instead
      of auto-classifying as `BYTES` / `MULTILINE` / `DATETIME` / etc.
      — `enums.py:parse_json_type`

### Tree mutation / context menu (`tree_view.py`, `model_actions.py`)
- [ ] [tree] Wire `Cut` and `Delete` context-menu actions in
      `tree_view.show_context_menu` (currently created but disconnected).
      — `tree_view.py:show_context_menu`
- [ ] [tree] Implement **Paste** from clipboard JSON (parse + insert as
      child or sibling).
- [ ] [tree] Add context-menu entries: *Insert Sibling Before*,
      *Insert Sibling After*, *Duplicate*, *Move Up/Down*,
      *Sort Keys*, *Collapse/Expand All*, *Change Type*.
- [ ] [tree] Either remove or properly implement *Insert Column* — the
      current entry is a no-op since `JsonTreeItem.insert_columns` returns
      `False`.
      — `tree_item.py:JsonTreeItem.insert_columns`
- [ ] [tree] Make `model.insertRow`/`insertRows` create properly initialized
      `JsonTreeItem`s (e.g. `value=None` → `JsonType.NULL`) instead of
      `value=[None, None, None]` which becomes an ARRAY of NULLs.
      — `tree_item.py:JsonTreeItem.insert_children`
- [ ] [tree] When inserting under an `OBJECT` parent, prompt for / generate
      a unique name; do not leave `name=None`.
- [ ] [tree] Add undo/redo via `QUndoStack` covering set/insert/remove on
      the model.

### I/O & serialization
- [ ] [io] Provide YAML round-trip through `mpq2py` YAML loader/dumper.
- [ ] [io] Provide JSON round-trip through `mpq_json_default` and a
      streaming reader for large files (paired with `jsontream`).
- [ ] [io] Validate datetime / bytes strings on save (raise readable
      errors).

### UX & polish
- [ ] [ux] Implement `displayText()` on `ValueDelegate` for nicer display
      of `PERCENT` (`50%`), `mpq` floats, datetimes, and elided long
      strings.
- [ ] [ux] Add a status bar message describing current selection
      (the C++ original did `Position: (row, column)`).
- [ ] [ux] Resize columns to contents on tab switch / model reset.
- [ ] [ux] Persist column widths and tree expansion state per file path.
- [ ] [ux] Add search / filter bar per tab.

### Tests
- [ ] [tests] Add unit tests for `JsonTreeModel`
      (insert/remove/setData/flags edge cases).
- [ ] [tests] Add unit tests for `JsonTreeItem.to_json()` round-trips
      including `mpq`, bytes, datetimes.
- [ ] [tests] Add unit tests for `parse_json_type` priority rules and
      ambiguous strings (`"abcd"` → BYTES vs STRING).
- [ ] [tests] Add a smoke test that `QApplication` + `JsonTab` constructs
      successfully (using `pytest-qt` if introduced).

### Code hygiene
- [ ] [hygiene] Strip the embedded C++ reference docstrings from
      `tree_model.py`, `tree_item.py`, `ui.py` once the port is settled.
- [ ] [hygiene] Remove unused imports in `ui.py` (`yaml`,
      `HeaderViewEditorMixin`, `JsonTypeDelegate`, `JsonTreeModel`,
      `show_context_menu`, `functools`).
- [ ] [hygiene] Remove demo-data imports from `json_tab.py` once real
      loading is wired (`base64`, `gzip`, `zlib`, `gmpy2`).
- [ ] [hygiene] Clean up commented-out C++/Python scaffolding inside
      `ui.py:setup_model` / `update_actions`.

---

## FIXME — bugs & known issues

### Confirmed bugs
- [ ] [BUG] `tests/test_mpq2py.py::test_mpq_with_json` **fails** —
      `json.dumps(..., default=mpq_json_default, indent=2)` raises through
      `simplejson`. Investigate which encoder is actually picked up and
      whether the project must avoid `simplejson` shadowing.
      — `mpq2py/__init__.py:mpq_json_default`,
        `tests/test_mpq2py.py::test_mpq_with_json`
- [ ] [BUG] `ui.py::MainWindow.copy_action` ends with no body after
      `model = self.view.model()` — function is syntactically incomplete
      and `self.view` does not exist on the tabbed `MainWindow`.
      — `ui.py:MainWindow.copy_action`
- [ ] [BUG] `MainWindow.insert_row` / `insert_child` / `insert_column` /
      `remove_row` / `remove_column` all reference `self.view`, which does
      not exist on the tabbed `MainWindow`; toolbar actions
      (`rowInsertAction`, `rowInsertAfterAction`, `rowRemoveAction`) will
      raise `AttributeError` at runtime.
      — `ui.py:MainWindow`
- [ ] [BUG] `JsonTypeDelegate.setModelData()` is `pass` — committing a
      type change silently does nothing.
      — `delegate.py:JsonTypeDelegate.setModelData`
- [ ] [BUG] `JsonTreeItem.set_data()` ignores columns 0 and 1, so the
      Name and Type columns appear editable (per `flags()`) but writes are
      silently dropped.
      — `tree_item.py:JsonTreeItem.set_data`
- [ ] [BUG] `JsonTreeItem.insert_children()` seeds new rows with
      `value=[None]*columns` (== `[None, None, None]`); `parse_json_type`
      then classifies them as `ARRAY` of three `NULL`s instead of a single
      blank node.
      — `tree_item.py:JsonTreeItem.insert_children`
- [ ] [BUG] Inserted children under an `OBJECT` parent have `name=None`;
      `JsonTreeItem.to_json()` then produces `{None: ...}` which is **not
      valid JSON** and will crash standard encoders.
      — `tree_item.py:JsonTreeItem.to_json`
- [ ] [BUG] `JsonTreeItem.insert_columns()` and `remove_columns()` always
      return `False`, but `JsonTreeModel.insertColumns`/`removeColumns`
      still call `beginInsertColumns`/`endInsertColumns` around the call.
      Views are notified of column changes that never happened.
      — `tree_model.py:JsonTreeModel.insertColumns`
- [ ] [BUG] `parse_json_type` raises a generic `Exception` on any
      unrecognized value type (tuples, custom classes, bytes, ...).
      `JsonTreeItem.__init__` propagates this and crashes the tree build.
      — `enums.py:parse_json_type`
- [ ] [BUG] `parse_json_type` for strings classifies any base64-decodable
      string (e.g. `"abcd"`, `"YWJjZA=="`) as `BYTES`; lossy and surprising
      for textual data.
      — `enums.py:parse_json_type`
- [ ] [BUG] `parse_json_type` reclassifies any `float`/`mpq` in `[0, 1]`
      as `PERCENT`; users who store probabilities like `0.5` see them
      auto-promoted and edited as `50%`.
      — `enums.py:parse_json_type`
- [ ] [BUG] `ValueDelegate.createEditor` for `MULTILINE` / `BYTES` /
      `ZLIB` / `GZIP` opens a `QDialog` and returns `None`. The dialog is
      created with `parent=parent` (the *editor* parent, not the main
      window), and is not stored, so its lifetime relies on Qt parenting
      alone. Reentrant edit triggers can stack dialogs.
      — `delegate.py:ValueDelegate.createEditor`
- [ ] [BUG] The same dialog callbacks capture `index` by closure; if the
      model is mutated while the dialog is open the index becomes stale
      and `setData` may write to the wrong row.
      — `delegate.py:ValueDelegate.createEditor`
- [ ] [BUG] `QHexDialog` is constructed eagerly with
      `decode_bytes(item.value, item.json_type)` inside `createEditor`. A
      malformed `ZLIB`/`GZIP` payload raises before the dialog is shown,
      breaking the edit flow with no user-visible recovery.
      — `delegate.py:ValueDelegate.createEditor`,
        `delegate.py:decode_bytes`
- [ ] [BUG] `JsonTypeDelegate.setEditorData` re-adds *all* `JsonType`
      values to the combo on every invocation, ignores the current node's
      type, and selects `next(iter(JsonType))`.
      — `delegate.py:JsonTypeDelegate.setEditorData`
- [ ] [BUG] Context-menu `Cut` and `Delete` actions are created but never
      `.triggered.connect(...)`'d — they appear enabled but do nothing.
      — `tree_view.py:show_context_menu`
- [ ] [BUG] Context-menu *Insert Column* triggers a no-op; should be
      removed or wired to a real action.
      — `tree_view.py:show_context_menu`
- [ ] [BUG] `MainWindow.close_tab` is connected to
      `tabCloseRequested(int)` but its signature takes no `index`
      argument and its body is `pass`; tabs cannot be closed.
      — `ui.py:MainWindow.close_tab`
- [ ] [BUG] `ui.py` still imports `functools` and `yaml` at module level
      but neither is used in the live code path.
      — `ui.py` imports
- [ ] [BUG] `JsonTreeModel.flags()` calls `base64.b64decode(..., validate=True)`
      and `zlib/gzip.decompress(...)` on every `flags()` query for
      `BYTES`/`ZLIB`/`GZIP` cells — `flags()` is hot-called by views; this
      is both slow and will raise if the stored value is malformed,
      breaking the whole row.
      — `tree_model.py:JsonTreeModel.flags`

### Suspected issues / smells
- [ ] [SMELL] `JsonTreeModel.data()` returns `None` implicitly for
      non-Display/Edit roles; consider an explicit `return None` and
      handle `Qt.ItemDataRole.ToolTipRole` for long values.
- [ ] [SMELL] `JsonTreeItem.row()` returns `0` for the root (no parent)
      instead of `-1`; tolerable but a footgun for future code.
- [ ] [SMELL] `ValueDelegate.setEditorData` for BOOLEAN uses
      `(not item.value) * 1`; replace with explicit
      `editor.setCurrentIndex(0 if item.value else 1)`.
- [ ] [SMELL] `ValueDelegate` raises `ValueError` when `json_type` is
      unsupported (`OBJECT`, `ARRAY`, `NULL`); these branches *should* be
      unreachable thanks to `flags()`, but a defensive `return None` would
      fail more gracefully.
- [ ] [SMELL] `JsonTreeModel.cleanup_columns_removal` calls `removeRows`
      which itself calls `beginRemoveRows`/`endRemoveRows` from inside a
      column-removal end signal — risk of nested model-change signals.
- [ ] [SMELL] `enums.parse_json_type` uses bare `except:` clauses three
      times, swallowing `KeyboardInterrupt`/`SystemExit` as well.
