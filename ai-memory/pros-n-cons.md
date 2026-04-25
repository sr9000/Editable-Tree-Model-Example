# JSON Editor — Pros & Cons

_Last analysis: 2026-04-25_

This document evaluates the **current** state of the JSON tree editor implementation
(`tree_model.py`, `tree_item.py`, `delegate.py`, `enums.py`, `json_tab.py`,
`tree_view.py`, `ui.py`, `model_actions.py`).

## ✅ Pros

### Architecture & design
- **Clean separation of concerns** between data layer (`JsonTreeItem`),
  model layer (`JsonTreeModel`), view layer (`JsonTab`/`QTreeView`), and
  editing layer (`ValueDelegate`/`JsonTypeDelegate`).
- **Tabbed multi-document architecture** via `QTabWidget` + `JsonTab` is in
  place — each tab encapsulates its own model, view and delegates.
- **Three-column schema** (`Name | Type | Value`) is well chosen for JSON: it
  surfaces the inferred type as a first-class, editable concept rather than
  hiding it behind value text.
- **Streaming JSON serialization** (`jsontream`) is used for copy-to-clipboard,
  avoiding loading the whole subtree into a single string up front.
- **Rich type system** (`JsonType` enum) goes well beyond plain JSON:
  percent, multiline, date/time/datetime/tz, bytes, zlib, gzip — the editor
  is positioned as a *structured-data* editor, not just JSON.
- **Auto-detection of types** in `parse_json_type()` makes pasted/loaded data
  immediately useful: base64+gzip blobs, ISO datetimes, etc. are recognized
  out of the box.
- **Exact numeric arithmetic** via `gmpy2.mpq` and `QMpqSpinBox` /
  `QBigIntSpinBox` avoids float precision loss — important for a serious data
  editor.
- **Dedicated specialist editors** are wired through delegates:
  `BetterDateTimeEditor` for temporal values, `QHexDialog` for binary,
  `QMultilineDialog` for text blobs. Each has persisted `QSettings`.
- **Begin/End model signals** are wrapped in context managers
  (`columns_insertion`, `rows_insertion`, ...), which makes Qt model
  bookkeeping exception-safe and harder to misuse.
- **Row-level editability is data-aware**: `flags()` disables editing for
  null / array / object / oversize blobs (>10 KB) — protecting against
  accidental destructive edits and UI freezes.
- **Substantial test coverage** for the *supporting* widgets (datetime
  parsing/validation, hex highlighting, mpq round-trip, jsontream,
  units/binary helpers).
- **Reusable widget stack**: `qhexedit`, `qmultiline_editor`, `datetime_editor`,
  `qbigint_spinbox`, `qmpq_spinbox` are independently useful packages.

### Code quality
- Modern Python (3.12+ `match`/`case`, `StrEnum`, type hints in most
  modules).
- `Makefile` enforces formatting (`black`, `isort`, `autoflake`).
- Pytest config (`pytest.ini`) sets `pythonpath = .` for consistent runs.

---

## ❌ Cons

### App shell is incomplete
- `main.py` accepts a filename but `MainWindow.setup_model()` is a **no-op
  stub** — the file is never loaded.
- `MainWindow.update_actions()` is a **stub**; menu/toolbar enabled-state is
  not driven by selection or model state.
- `MainWindow.close_tab()` is a **stub**; the close button on tabs does not
  actually close them.
- `MainWindow.copy_action()` is **truncated mid-function** in `ui.py` (ends
  after `model = self.view.model()` with no body, and `self.view` does not
  exist on the tabbed `MainWindow`).
- `JsonTab` is seeded with **hard-coded demo data**; there is no file-open,
  file-save, or recent-files workflow.
- No file-format negotiation between YAML (`data.yaml`) and JSON
  (`data.json`); the runtime defaults to YAML but the model only knows JSON
  semantics.

### Type & schema editing
- `JsonTypeDelegate.setModelData()` is `pass` — the type combo box does
  **nothing**; users cannot change a node's type.
- `JsonTreeItem.set_data()` only handles **column 2 (Value)**; renaming
  (column 0) and changing type (column 1) are not implemented in the data
  layer either.
- There is no validation that a user-typed string (e.g. for `DATE`) actually
  parses cleanly before being stored — `set_data` writes the raw editor
  text. The model trusts the delegate.
- Type inference is **eager and lossy**: a plain string that happens to be
  valid base64 (e.g. `"abcd"`) will be classified as `BYTES`, and any string
  containing `\n` becomes `MULTILINE` permanently. There is no way to
  override the inferred type and pin a node as `STRING`.
- `PERCENT` is auto-inferred from any float / `mpq` in `[0, 1]`, which
  silently reinterprets values like `0.5` as 50%.

### Tree/model semantics
- `JsonTreeModel` exposes `insertColumns` / `removeColumns` /
  `setHeaderData`, but `JsonTreeItem.insert_columns()` /
  `remove_columns()` always return `False`. The column API is dead code that
  imitates the original Qt example, while headers are actually fixed
  (`Name`, `Type`, `Value`).
- `model_actions.action_insert_column()` and the **Insert Column** context
  menu / toolbar action thus appear to do nothing — silent no-op UX.
- `action_insert_row` and `action_insert_child` rely on
  `model.insertRow(...)` which produces a child seeded with
  `value=[None, None, None]` — that is then parsed by `parse_json_type` as
  `ARRAY` of three `NULL`s. New rows are not blank `null` items as
  intended; they become 3-element arrays of nulls.
- `JsonTreeItem` does **not assign names** to inserted children, so new
  rows under an `OBJECT` parent have `name=None`, displayed as
  `<no name>`, and `to_json()` produces `{None: ...}` which is not valid
  JSON (and will crash standard json encoders).
- `parse_json_type` raises on unknown values (e.g. `tuple`, custom classes)
  — but `JsonTreeItem.__init__` calls it unconditionally, so any
  unsupported value type crashes tree construction without a clean error
  path.
- `JsonTreeItem.row()` returns `0` for the root rather than something
  signalling "no parent"; works in practice but is a footgun.
- `data()` for non-Display/Edit roles returns `None` implicitly; intent is
  unclear without an explicit return.

### Delegate / editor issues
- `ValueDelegate.createEditor` for `MULTILINE` / `BYTES` / `ZLIB` / `GZIP`
  opens a dialog *and then returns `None`*. Qt expects an editor widget; the
  view treats `None` as "no editor", but the dialog is opened during
  `createEditor` which is invoked on every edit-trigger — including
  programmatic ones. There is no guarantee the dialog is parented to a
  visible window, and reentrancy / focus issues are likely.
- The dialog callbacks capture `index` by closure — if the model is
  mutated (rows inserted/removed) while the dialog is open, the index
  becomes stale and `setData` may write to the wrong row.
- `setEditorData` for `BOOLEAN` uses `(not item.value) * 1` to compute the
  combo index, which works but is unidiomatic; if `item.value` is ever
  truthy-but-not-bool the result is misleading.
- `QHexDialog` decodes/decompresses the entire payload eagerly inside
  `createEditor`. A malformed `ZLIB`/`GZIP` value will raise from
  `createEditor` and probably break the edit flow.
- `JsonTypeDelegate.setEditorData` re-populates the combo every time it is
  called and always selects the first enum value — it does **not preselect
  the current type** of the node.
- No `displayText()` override: large strings, percent fractions,
  datetimes-with-tz are shown via `str(...)` in the model rather than a
  human-friendly formatted string.

### Context menu / actions
- `Cut` and `Delete` actions are created but never connected (`tree_view.py`).
- `Copy` only copies the value subtree as JSON; pasting back is not
  implemented.
- `Insert Column` is exposed in the context menu but, as noted, is a no-op.
- The context menu has no "Add Sibling Before/After", "Duplicate",
  "Sort Keys", "Collapse/Expand All", or "Change Type" entries.
- `rowInsertAction` and `rowInsertAfterAction` in `ui.py` are both wired to
  the same `insert_row` slot — there is no "insert before" semantic.
- `MainWindow.insert_row` / `insert_child` / `remove_row` reference
  `self.view`, which doesn't exist on the tabbed `MainWindow`; triggering
  these toolbar actions will raise `AttributeError`.

### Persistence / I/O
- No save/load roundtrip path (YAML or JSON) in the actual UI flow.
- No undo/redo at the model level — `qhexedit` has its own undo stack but
  edits via the tree go through `dataChanged` only.
- No dirty-state tracking; closing a modified tab would lose data silently.
- No error feedback path for I/O failures beyond a single `QMessageBox` in
  `create_new_file`.

### Known/observed bugs
- `tests/test_mpq2py.py::test_mpq_with_json` is **failing** in baseline
  scan — `mpq` JSON serialization regression / `simplejson` interaction.
- `ui.py::copy_action` is syntactically truncated (function body missing).
- `ui.py` still imports `yaml`, `HeaderViewEditorMixin`, `JsonTypeDelegate`,
  `JsonTreeModel`, `show_context_menu` that are unused in the active path.

### Code hygiene
- `tree_model.py`, `tree_item.py`, and `ui.py` contain large embedded **C++
  reference blocks** as docstrings — useful while porting but now adding
  ~150–200 lines of noise per file.
- `ui.py` retains commented-out scaffolding for `setup_model` and
  `update_actions`, which obscures the intended Python design.
- `JsonTab` imports `base64`, `gzip`, `zlib`, `gmpy2` purely to construct
  the demo dictionary — these will be dead imports once real loading is
  implemented.

---

## TL;DR

The **editor primitives** (delegates, custom widgets, datetime/hex/multiline
editors, exact numerics, type detection) are in good shape and well tested.
The **application shell** (file open/save, type editing, name editing,
row insertion, action wiring, tab close) is largely scaffolded but **not
functional**. The repo is currently a strong widget toolkit with a
half-finished JSON editor on top.
