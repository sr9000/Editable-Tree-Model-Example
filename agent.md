# Agent Guide — Editable-Tree-Model-Example

_Orientation document for AI coding agents working on this repository._
**Last updated:** 2026-06-13

## 1) Project Overview

A PySide6 desktop **structured-data editor** (JSON, YAML, JSONL) with:
- Three-column tree view: `Name | Type | Value`
- Exact rational numerics via `gmpy2.mpq` (no floating-point drift)
- Strict undo/redo on every mutation
- JSON-Schema validation with live badges
- Raw numeric value preservation for unsupported literals (overflow, underflow, non-finite)

## 2) Build & Test Commands

**Always activate the venv first** — all tools (pytest, autoflake, isort, black) live in `.venv`:

```bash
source .venv/bin/activate
```

Then use `make` targets (which rely on the activated venv):

```bash
# Run full test suite (~1655 tests, ~25s)
QT_QPA_PLATFORM=offscreen pytest tests/ -q

# Run specific test file
QT_QPA_PLATFORM=offscreen pytest tests/test_raw_numeric_values.py -xvs

# Recommended for long-running commands in automation to avoid hangs
timeout 600 QT_QPA_PLATFORM=offscreen pytest tests/ -q

# Lint (autoflake + isort + black)
make lint

# Full DoD gate (lint → reflection check → isolation checks → tests)
# ALWAYS run this before committing.
make gate

# Recommended in CI/agent runs to prevent accidental hangs
timeout 1200 make gate

# Isolation checks individually
make check-editors-isolation  # editors/ must not import app/documents/tree
make check-tree-isolation     # tree/ must not import app/documents/editors/delegates/state/validation
make check-no-reflection      # no getattr/hasattr outside allowlist
```

**Commit discipline:** Run `make gate` and ensure it passes before every commit. Never skip the DoD gate.

**Hang prevention:** Prefer wrapping long-running commands (`pytest`, `make gate`, perf tests) with `timeout` in agent-driven runs.

## 3) Key Architecture: Edit Flow

Understanding the edit flow is critical for fixing value-handling bugs:

```
User types in editor widget
    ↓
editors/factory.py: set_value_model_data()
    ↓ (commits editor value)
delegates/edit_context.py: DefaultEditContext.commit()
    ↓
documents/seams/mutation_gateway.py: DocumentMutationGateway.commit_set_data()
    ↓ (routes to undo command)
documents/states/editing/command_dispatcher.py: CommandDispatcher.push_edit_value()
    ↓ (creates undo command)
undo/commands.py: _EditValueCmd.redo()
    ↓ (surgical replay)
undo/diff.py: DiffApplier.apply()
    ↓ (applies value to item)
tree/item.py: JsonTreeItem._apply_typed_value() or _set_raw_numeric_value()
```

**Critical insight**: The `DiffApplier` bypasses `JsonTreeItem.set_data()` and directly applies values. Special type handling (like `RAW_FLOAT` → `_set_raw_numeric_value`) must be added to `DiffApplier.apply()` explicitly.

## 4) Key Architecture: Type System

| Concept | Location | Purpose |
|---------|----------|---------|
| `JsonType` enum | `tree/types.py` | All type definitions including pseudo-types |
| `parse_json_type()` | `tree/types.py` | Infer type from value |
| `coerce_value_for_type()` | `tree/item_coercion.py` | Convert value for target type |
| `normalize_value_for_type()` | `tree/item_coercion.py` | Normalize value for storage |
| `TEXT_FAMILY` | `tree/types.py` | Set of text-like types |
| `PSEUDO_FAMILY` | `tree/types.py` | Non-user-selectable derived types |

**Pseudo-types** (not user-selectable, derived from content):
- `RAW_FLOAT` — unsupported numeric literals preserved as raw text
- `EMPTY_STRING`, `EMPTY_MULTILINE` — empty text values
- `WS_STRING`, `WS_UNICODE`, `WS_MULTILINE`, `WS_TEXT` — whitespace-only text

## 5) Key Architecture: Raw Numeric Values

When a numeric literal cannot be safely parsed as `mpq` (overflow, underflow, non-finite, precision limit), it's preserved as a `RawNumericValue` with type `RAW_FLOAT`.

| Component | Location | Purpose |
|-----------|----------|---------|
| `RawNumericValue` | `core/raw_numeric.py` | Dataclass holding raw text + reason |
| `raw_numeric_text_is_acceptable()` | `core/raw_numeric.py` | Narrow edit regex validator |
| `parse_mpq()` | `core/safe_mpq.py` | Safe parser returning `MpqParseResult` |
| `RawNumericLineEdit` | `editors/inline/raw_numeric_line.py` | Plain-text editor for raw values |
| `_set_raw_numeric_value()` | `tree/item.py` | Edit recovery logic |

**Edit rules for raw numeric values** (in `_set_raw_numeric_value`):
1. If text parses safely → convert to `INTEGER` (whole numbers) or `FLOAT` (fractions)
2. If text unchanged → preserve original `RawNumericValue`
3. If text matches narrow regex but still unsupported → keep as new `RawNumericValue`
4. If text violates regex → reject edit

## 6) Module Isolation Rules

Enforced by pre-commit hooks and `make check-*` targets:

| Module | Must NOT import from |
|--------|---------------------|
| `editors/inline/*`, `editors/windowed/*` | `app/`, `documents/`, `tree/` |
| `editors/factory.py`, `editors/context.py` | `app/`, `documents/` |
| `tree/` | `app/`, `documents/`, `editors/`, `delegates/`, `state/`, `validation/` |

Shared pure-data logic lives in `core/` (datetime parsing, raw numerics, safe mpq) or `tree/codecs/` (bytes, color).

## 7) Common Pitfalls

1. **DiffApplier bypasses set_data**: When fixing value handling, check both `JsonTreeItem.set_data()` AND `DiffApplier.apply()` in `undo/diff.py`.

2. **mpq vs int distinction**: `parse_json_type(mpq(42, 1))` returns `FLOAT`, not `INTEGER`. For whole-number edits, convert `mpq` to `int` before calling `parse_json_type`.

3. **Proxy model indices**: The UI uses `TreeFilterProxy` (`tree/filter_proxy.py`). Always map to source indices before accessing `JsonTreeItem`.

4. **explicit_type flag**: When `item.explicit_type` is True, edits go through strict coercion (`_coerce_value_for_type` with `strict=True`). Pseudo-types like `RAW_FLOAT` have `explicit_type=False`.

5. **No reflection**: `getattr`/`hasattr`/`TYPE_CHECKING` are banned outside a small allowlist. Tests must annotate exceptions with `# allow: <reason>`.

## 8) File Locations Quick Reference

| What you need | Where to look |
|---------------|---------------|
| Add a new JsonType | `tree/types.py` (enum + families + inference) |
| Add a new editor widget | `editors/inline/` or `editors/windowed/` + `editors/factory.py` |
| Change value coercion | `tree/item_coercion.py` |
| Change undo behavior | `undo/commands.py` + `undo/diff.py` |
| Change file I/O | `io_formats/load.py` + `io_formats/dump.py` |
| Change validation | `validation/` + `app/validation_presenter.py` |
| Change theming | `themes/` + `app/theme_controller.py` |
| Add a plan/design doc | `.kilo/plans/` |
| Architecture reports | `reports/` |

## 9) Testing Patterns

```python
# Model-level test (no Qt event loop needed)
from tree.model import JsonTreeModel
from PySide6.QtCore import QModelIndex, Qt

model = JsonTreeModel({"key": value})
item = model.get_item(model.index(0, 0, QModelIndex()))
value_index = model.index(0, 2, QModelIndex())
model.setData(value_index, new_value, Qt.ItemDataRole.EditRole)
assert item.json_type is expected_type

# Editor-level test (needs qtbot fixture)
def test_something(qtbot):
    from PySide6.QtWidgets import QWidget, QStyleOptionViewItem
    from delegates.value import ValueDelegate
    
    parent = QWidget()
    qtbot.addWidget(parent)
    delegate = ValueDelegate()
    editor = delegate.createEditor(parent, QStyleOptionViewItem(), index)
    # ... interact with editor ...
```
