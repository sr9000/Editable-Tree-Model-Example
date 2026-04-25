# Editable-Tree-Model-Example — repo map

_Last scanned: 2026-04-25_

## 1) What this repo is

A PySide6 desktop app that is evolving from Qt's **Editable Tree Model** example into a more ambitious **JSON/tree editor**.

The codebase mixes:
- a direct/generated Qt UI port (`mainwindow.py`, `mainwindow.ui`)
- a partially ported/adapted main window layer (`ui.py`)
- a newer JSON-centric tree model/view stack (`json_tab.py`, `tree_model.py`, `tree_item.py`, `delegate.py`)
- several custom editor widgets/utilities (`qhexedit`, `qmultiline_editor`, `datetime_editor`, `qbigint_spinbox`, `qmpq_spinbox`)

The repo is **not just a minimal example anymore**: it contains reusable widgets and helper packages, plus a fairly large test suite.

## 2) Current app entry flow

### Runtime entrypoint
- `main.py`
  - creates `QApplication`
  - instantiates `ui.MainWindow`
  - passes a filename argument, defaulting to `data.yaml`
  - resizes window using `settings.WINDOW_DEFAULT_SIZE`

### Main window layer
- `ui.py`
  - subclasses generated `mainwindow.Ui_MainWindow`
  - wires menu actions
  - supports `create_new_file()` by adding a `JsonTab` into `tabWidget`
  - **important:** several methods are still stubs:
	- `setup_model()`
	- `close_tab()`
	- `update_actions()`
  - also still contains commented C++ reference code from the original Qt example

### Per-tab editor
- `json_tab.py`
  - creates a `QTreeView`
  - attaches `JsonTreeModel`
  - assigns delegates:
	- column 1 → `JsonTypeDelegate`
	- column 2 → `ValueDelegate`
  - installs custom context menu via `tree_view.show_context_menu`
  - currently seeds the model with **hardcoded demo JSON-like data** instead of loading file contents

## 3) Core JSON/tree architecture

### `tree_model.py` — `JsonTreeModel`
Main tree model built on `QAbstractItemModel`.

Responsibilities:
- holds `root_item: JsonTreeItem`
- exposes 3 columns: `Name`, `Type`, `Value`
- uses `JsonTreeItem` for hierarchy/navigation
- stringifies values for display/edit roles
- normalizes display of:
  - booleans → `"true"` / `"false"`
  - `None` → `"null"`
  - `gmpy2.mpq` → serialized decimal form via `mpq2py.mpq_serialization`
- selectively disables editing for:
  - `null`
  - arrays/objects
  - overly large strings/binary payloads
- provides row/column insert/remove wrappers using context managers around Qt begin/end calls

Observations:
- the file begins with a long embedded C++ reference block from the Qt example
- the real Python implementation starts after that block
- column insertion/removal exists because it mirrors Qt model APIs, but the JSON model itself is effectively fixed-width (3 columns)

### `tree_item.py` — `JsonTreeItem`
Represents one JSON node.

Behavior:
- infers `json_type` using `enums.parse_json_type`
- stores:
  - `name`
  - `value`
  - `parent_item`
  - `child_items`
- recursively expands:
  - Python `list` → `JsonType.ARRAY`
  - Python `dict` → `JsonType.OBJECT`
- `to_json()` converts the in-memory tree back to Python primitives

Important limitation:
- `set_data()` only supports editing **column 2** (`Value`)
- renaming names and changing types are **not implemented here**

### `enums.py` — `JsonType` + type detection
Defines supported value kinds:
- basic JSON-ish: integer, float, string, boolean, object, array, null
- extras: percent, multiline, date, time, datetime, datetime-with-timezone, bytes, zlib, gzip

`parse_json_type()` detects types from Python values and strings by trying, in roughly this order:
- `None` / bool / int / float / `gmpy2.mpq`
- multiline strings
- base64 / zlib / gzip encoded strings
- datetime/date/time strings
- list / dict

That means a plain string can be auto-classified as encoded bytes or datetime if it matches.

## 4) Editing/delegate layer

### `delegate.py`
Two delegates exist:

#### `ValueDelegate`
Chooses editor by `JsonType`:
- integer → `QBigIntSpinBox`
- float → `QMpqSpinBox`
- percent → `QMpqSpinBox` configured as 0..100%
- boolean → `QComboBox`
- string → `QLineEdit`
- date/time/datetime/tz → `BetterDateTimeEditor`
- multiline → opens modal `QMultilineDialog`
- bytes/zlib/gzip → opens modal `QHexDialog`

Also contains byte encode/decode helpers:
- `decode_bytes()`
- `encode_bytes()`

#### `JsonTypeDelegate`
Currently incomplete:
- editor is a combo box listing `JsonType`
- `setModelData()` is `pass`
- type-changing workflow is therefore scaffolded, not finished

## 5) Tree view actions / context menu

### `tree_view.py`
Contains `show_context_menu(tree_view, position)`.

Current menu contents:
- submenu for current item label
- `Copy`
- placeholders created for `Cut` / `Delete` (not wired)
- `Insert Row`
- `Insert Child`
- `Insert Column`

Serialization helper:
- `to_json(item)` uses `jsontream.StreamingJSONEncoderWrapper`

### `model_actions.py`
Contains standalone action helpers used by the view/UI:
- `action_insert_row()`
- `action_insert_child()`
- `action_insert_column()`

These are generic-ish Qt model manipulations adapted from the original example.

## 6) Main UI / generated files

### `mainwindow.ui`
Qt Designer XML for the main window.
Key visible structure:
- central `QTabWidget` (`tabWidget`)
- menus/actions including:
  - `fileCreateNewAction`
  - `appExitAction`
  - row insert/remove actions
  - `actionsMenu`

### `mainwindow.py`
Auto-generated Python from `mainwindow.ui`.
Do not hand-edit unless regenerating is acceptable.

### `ui.py`
This is the hand-written integration layer around the generated UI.

Important state of this file:
- it still carries the original C++ reference block as a docstring
- much of the old single-view logic references `self.view`, but the newer app structure is tab-based via `JsonTab`
- this means the file is in a **transition state** between the original Qt example and the newer multi-tab JSON editor architecture

## 7) Custom widgets and support packages

### `datetime_editor/`
Purpose: permissive-but-structured date/time text editing.

Key pieces:
- `regex.py`
  - complete + partial regexes for dates/times/datetimes/timezones
  - `parse_datetime_text()` using `dateutil.isoparse` / stdlib parsers
- `validator.py`
  - `DateTimeValidator` for Qt line edit validation
- `better_dt_editor.py`
  - the most advanced datetime editor implementation
  - includes `BetterDateTimeBuffer` for segment-aware stepping/editing
  - supports arrow/page up/down editing of year/month/day/hour/etc.
  - timezone segments (`+HH:MM`, `Z`) are editable too
- `__init__.py`
  - older/simple `DateTimeEditor` wrapper still exists

Takeaway: `BetterDateTimeEditor` is the one actively used by delegates.

### `qhexedit/`
Largest custom widget package in repo.

Purpose:
- binary/hex editing inside dialogs
- selection, cursoring, overwrite/insert mode, clipboard, undo/redo, highlighting

Main files:
- `qhexedit/__init__.py`
  - `QHexEdit` widget implementation
- `qhexedit/chunks.py`
  - storage backend over `QIODevice`
  - lazy chunk loading, mutation bookkeeping, changed-byte tracking
- `qhexedit/commands.py`
  - `QUndoStack` wrappers for insert/remove/overwrite
- `qhexedit/color_manager.py`
  - theming, selection colors, changed-byte highlighting

Notable behavior implemented in `QHexEdit`:
- hex and ASCII edit zones
- insert vs overwrite modes
- special delete/backspace semantics
- clipboard copy/paste as hex text
- highlight modified bytes
- dynamic bytes-per-line on resize

### `dialogs/`
Modal wrappers around custom editors.

- `dialogs/qhexedit_dlg.py`
  - `QHexDialog`
  - persists settings using `QSettings`
  - toggles address area / ASCII area / highlighting / caps
- `dialogs/qmultiline_dlg.py`
  - `QMultilineDialog`
  - persists word wrap / line numbers / monospaced mode

### `qmultiline_editor.py`
`QPlainTextEdit` derivative with:
- line number gutter
- word-wrap toggle
- monospaced toggle

### `qbigint_spinbox/`
Exact integer spinbox built on Python's arbitrary-precision `int`.

### `qmpq_spinbox/`
Exact rational spinbox built on `gmpy2.mpq`.
Uses `mpq2py.mpq_serialization()` for stable display formatting.

### `mpq2py/`
Helpers for converting exact rationals to/from JSON/YAML-friendly forms.

Key contents:
- `mpq_serialization()`
- `mpq_json_default()`
- YAML loader/dumper subclasses for `mpq`

### `jsontream/`
Streaming JSON encoder wrapper.

Purpose:
- support iterables/generators during JSON encoding
- both compact and pretty-print modes

Key API:
- `StreamingJSONEncoderWrapper`
- `new_streaming_json_factory()`

### Small utility packages
- `coalesce/` → `nn[...]` null-coalescing helper
- `binary/` → formatted hex dump string helper
- `qt2py/` → timezone-aware `QDateTime` ↔ Python `datetime` conversion
- `units/` → human-readable byte/count formatting

## 8) Tests and what they cover

The repo has a substantial `tests/` suite covering more than the main GUI shell.

Major covered areas:
- `test_better_datetime_buffer.py`
  - segment stepping, timezone editing, revert behavior
- `test_datetime_editor.py`
  - parsing of dates/times/datetimes/tz values
- `test_validator.py`
  - validator accept/intermediate/invalid behavior
- `test_jsontream.py`, `test_pretty_jsontream.py`
  - streaming JSON encoding behavior
- `test_mpq2py.py`
  - JSON/YAML round-trip behavior for `mpq`
- `test_qhexedit_highlighting.py`
  - highlighting integration with `ColorManager`
- `test_dialog_settings.py`
  - persistence of `QSettings` for dialogs
- `test_units.py`
  - human-readable formatting helpers
- plus regex/partial-input tests

### Baseline when scanned
Ran:
```bash
pytest -q
```

Observed result:
- suite is **almost green**
- there is **one failing test**:
  - `tests/test_mpq2py.py::test_mpq_with_json`
- the failure occurs during `json.dumps(..., default=mpq_json_default, indent=2)`
- traceback goes through `simplejson` inside the virtualenv

So the repo is generally healthy, but JSON serialization of `mpq` currently has a regression or environment interaction.

## 9) Unfinished / transitional areas

These are the most obvious incomplete spots found during scan:

1. `ui.py::setup_model()` is a stub
   - startup filename loading (`data.yaml`) is not actually implemented there

2. `ui.py::close_tab()` is a stub

3. `ui.py::update_actions()` is a stub

4. `delegate.py::JsonTypeDelegate.setModelData()` is a stub
   - type changes are not wired into the model

5. `tree_item.py::JsonTreeItem.set_data()` only updates value column
   - renaming and type mutation are not supported in model core

6. `json_tab.py` currently uses hardcoded demo data
   - not file-backed yet

7. The codebase still contains large embedded C++ reference blocks in:
   - `tree_model.py`
   - `tree_item.py`
   - `ui.py`
   These are helpful as porting references but add noise.

8. The architecture is midway between:
   - original single-view Qt example logic
   - newer tabbed JSON editor logic

## 10) Data/sample files

- `data.yaml`
- `data.json`

These appear to be sample datasets inherited from/related to the original Qt example structure.
The current runtime path does **not** appear to load them into `JsonTab` yet.

## 11) Dependencies / tooling

### Python dependencies (`requirements.txt`)
- `PySide6==6.11.0`
- `PyYAML==6.0.3`
- `python-dateutil==2.9.0.post0`
- `gmpy2==2.3.0`
- `pytest==9.0.3`
- `tzdata==2026.2`

### Formatting/linting (`Makefile`)
- `autoflake .`
- `isort . --extend-skip mainwindow.py`
- `black . --line-length 120 --extend-exclude mainwindow.py`

### Pytest config
- `pytest.ini` sets `pythonpath = .`

## 12) Suggested reading order for future work

If returning to this repo later, the fastest orientation path is:
1. `main.py`
2. `ui.py`
3. `json_tab.py`
4. `tree_model.py`
5. `tree_item.py`
6. `delegate.py`
7. `tree_view.py`
8. `model_actions.py`
9. `datetime_editor/better_dt_editor.py`
10. `qhexedit/__init__.py`

## 13) Practical mental model

Use this simplified model when thinking about the repo:

- **Shell/UI layer**: `main.py` → `ui.py` / `mainwindow.ui`
- **Tab layer**: `json_tab.py`
- **Tree data layer**: `tree_model.py` + `tree_item.py` + `enums.py`
- **Editing layer**: `delegate.py`
- **Advanced editor widgets**:
  - datetime → `datetime_editor/`
  - binary → `qhexedit/` + `dialogs/qhexedit_dlg.py`
  - multiline text → `qmultiline_editor.py` + `dialogs/qmultiline_dlg.py`
  - exact numerics → `qbigint_spinbox/`, `qmpq_spinbox/`, `mpq2py/`
- **Utilities/tests**: `jsontream/`, `units/`, `qt2py/`, etc.

In short: **the real value of the repo is the custom editor/widget stack; the main window app integration is still partially under construction.**
