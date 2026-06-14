# Editable-Tree-Model-Example — Fast Repo Map

_This is a condensed index and architectural summary. LLM agents should refer to direct source files for implementation
details._
**Last updated:** 2026-06-13 (after raw-numeric edit-flow fix; added DiffApplier RAW_FLOAT routing,
integer promotion for whole-number mpq edits, and `agent.md`).

## 1) High-level Purpose

A PySide6 desktop **structured-data editor** (JSON, YAML, JSONL) focusing on typed tree editing, exact numerics (mpq),
and a robust undo/redo system. It uses a three-column `Name | Type | Value` model derived from Qt's "Editable Tree
Model".

## 2) LLM Quick-Orientation (Fast Index)

| Domain              | Key Entry Points                                                                                                |
|:--------------------|:----------------------------------------------------------------------------------------------------------------|
| **App Shell**       | `main.py`, `app/main_window.py`                                                                                 |
| **Document/Tab**    | `documents/tab.py` (JsonTab — thin facade / routing surface)                                                    |
| **Tab Composition** | `documents/composition/` (bootstrap, setup, factory, dependencies, marker, demo_data)                           |
| **Tab Controllers** | `documents/controllers/` (appearance, navigation, editability, validation, history, view, status, number_types) |
| **Tab States**      | `documents/states/` (io_controller, view_state, editing_controller + editing/)                                  |
| **Document Seams**  | `documents/seams/mutation_gateway.py`, `documents/seams/document_protocol.py`                                   |
| **Tree Data Model** | `tree/model.py`, `tree/item.py`, `tree/filter_proxy.py`                                                         |
| **Type System**     | `tree/types.py` (Definitions), `tree/item_coercion.py` (Conversion)                                             |
| **Editor Widgets**  | `editors/factory.py` (dispatch), `editors/inline/`, `editors/windowed/`                                         |
| **Delegates**       | `delegates/value.py` (paint + createEditor → editors.factory), `delegates/formatting/`                          |
| **Undo System**     | `undo/commands.py` (Operations), `undo/diff.py` (Surgical replay + RAW_FLOAT routing)                            |
| **Structural Ops**  | `tree_actions/` (Clipboard, DnD, Move, Sort, Anchors)                                                           |
| **Validation**      | `validation/` (JSON-Schema), `app/validation_presenter.py`                                                      |
| **Theming**         | `themes/`, `app/theme_controller.py`                                                                            |
| **Persistence**     | `state/` (View state, settings), `io_formats/` (File I/O)                                                       |
| **Generated UI**    | `ui/` (mainwindow, json_tab + .ui sources), `ui/dialogs/` (.ui-backed dialog schemas)                           |
| **Reviews/Reports** | `reports/` (architecture & code-quality review docs)                                                            |

## 3) Core Invariants & Repo Rules

- **Strict Undo/Redo**: ALL mutations (renames, value edits, type changes, structural moves) must be routed through
  `JsonTab.push_*` or `commit_set_data` to ensure they are undoable via `QUndoCommand`s.
- **Anchor-based Moves**: Every structural move (Drag-and-drop, Keyboard Alt+Up/Down, Cut/Paste) uses the `MoveAnchor`
  primitive in `tree_actions/anchors.py`. This ensures consistency across different UI interactions.
- **Type-Centric**: Type inference (`tree/types.py`) and coercion (`tree/item_coercion.py`) are the source of truth for
  how data is handled. Don't scatter type logic in the UI.
- **Surgical Model Updates**: The `DiffApplier` (`undo/diff.py`) is used during Undo/Redo to emit minimal Qt signals.
  This preserves UI state like selection and expansion that would be lost on a full model reset.
  **Important**: `DiffApplier.apply()` bypasses `JsonTreeItem.set_data()` — special type handling (e.g., `RAW_FLOAT`
  routing to `_set_raw_numeric_value`) must be added to `DiffApplier.apply()` explicitly.
- **Edit flow path**: Editor → `editors/factory.set_value_model_data()` → `DefaultEditContext.commit()` →
  `DocumentMutationGateway.commit_set_data()` → `CommandDispatcher.push_edit_value()` → `_EditValueCmd` →
  `DiffApplier.apply()` → `JsonTreeItem._apply_typed_value()` / `_set_raw_numeric_value()`.
- **Raw numeric values**: Unsupported numeric literals (overflow, underflow, non-finite) are preserved as
  `RawNumericValue` (`core/raw_numeric.py`) with type `JsonType.RAW_FLOAT`. Edits go through
  `JsonTreeItem._set_raw_numeric_value()` which handles: safe-parse → int/float conversion, unchanged → preserve,
  regex-match → keep raw, regex-violate → reject. Whole-number mpq results are promoted to `int` for `INTEGER` type.
- **No external `data_store.*` reads** (Plan 20). External callers (`app/`, `undo/`, `tree_actions/`, `state/`) must
  reach state through typed `JsonTab.*` properties. The pre-commit hook
  `.githooks/_check_data_store_leaks.sh` enforces this for 17 retired attributes.
- **Viewport via signal** (Plan 20 Phase D). Selection / expand / scroll happen through
  `JsonTab.view_controller.request_*` calls that emit `viewportRequested(kind, payload)`. Undo commands NEVER call
  `setCurrentIndex` directly.
- **No reflection**: `getattr` / `hasattr` / `TYPE_CHECKING` / `AttributeError` are banned outside a tiny allowlist
  (`.githooks/pre-commit-ci`); tests must annotate exceptions with `# allow: <reason>`.
- **Editors isolation**: Concrete editor widgets (`editors/inline/*`, `editors/windowed/*`) must **never** import from
  `app/`, `documents/`, or `tree/`. The dispatch seam (`editors/factory.py`, `editors/context.py`) may import
  `tree.types` / `tree.item` for type dispatch, but never `app/` or `documents/`. Enforced by
  `make check-editors-isolation`.
- **Tree isolation**: `tree/` must **never** import from `app/`, `documents/`, `editors/`, `delegates/`, `state/`, or
  `validation/`. Shared pure-data logic (datetime parsing, bytes/color codecs) lives in `core/` or `tree/codecs/`;
  secret-name matching is injected via `SecretNamePredicate`. Enforced by `make check-tree-isolation`.
- **Separation of Concerns**:
    - `tree/`: Data structure and model.
    - `core/`: Shared pure-data logic (datetime parsing) consumed by both `tree/` and `editors/`.
    - `editors/`: Value-editing widgets (inline + windowed) and dispatch.
    - `delegates/`: Presentation, cell-level editing delegation, and formatting helpers.
    - `tree_actions/`: Logic for high-level operations.
    - `documents/`: Orchestration of model, view, undo, and search for a single tab.
    - `app/`: Global window management and cross-tab controllers.
    - `ui/`: Generated UI code (pyside6-uic output) and `.ui` schemas.

## 4) Practical Mental Model

- **The Shell (`app/`)**: Manages the multi-tab interface, global settings, and theme synchronization.
- **The Tab (`documents/`)**: Thin facade routing to composition, controllers, states, and seams.
- **The Tree (`tree/`)**: A hierarchical `JsonTreeItem` structure. Invariants like "OBJECT children must have names" are
  enforced here.
- **The Edit Flow**: `ValueDelegate` (UI) → `editors.factory.create_value_editor` → `JsonTab.commit_set_data` →
  `DocumentMutationGateway` → `QUndoCommand` → `JsonTreeModel.setData` → `JsonTreeItem.set_data`.
- **The Editor Widgets (`editors/`)**: Self-hosted, app-agnostic QWidgets. Inline editors edit in-cell; windowed editors
  open modal dialogs. The factory dispatches by `JsonType`; concrete widgets know nothing of the host.

## 5) Key Technical Detail: Persistence

- **Data**: Handled by `io_formats/`. Uses atomic writes (`os.replace`).
- **View State**: `state/view_state.py` saves column widths, expanded paths, selection, and zoom per-file (keyed by SHA1
  of path) in `QSettings`.
- **Theming**: App-level `Qt.ColorScheme` is synced to match the current theme mode (Light/Dark) to ensure native
  dialogs match the app theme.

## 6) Validation Workflow

- **Discovery**: `JsonTab` looks for `$schema` in data, then sibling files, then persisted manual bindings.
- **Registry**: `SchemaRegistry` handles shared loading and hot-reloading (via `QFileSystemWatcher`) of schema files
  across multiple tabs.
- **Indexing**: `IssueIndex` maps `jsonschema` errors to tree model indexes for the validation dock and in-tree badges.

## 7) `documents/` module layout (post responsibility-segregation split)

```
documents/
├── tab.py                   JsonTab QWidget — thin facade / routing surface.
├── composition/             Wiring & construction of a tab.
│   ├── init.py              bootstrap() — dense __init__ body extracted from JsonTab.
│   ├── setup.py             init_layout / init_model / init_delegates / init_shortcuts.
│   ├── factory.py           tab construction helpers.
│   ├── dependencies.py      JsonTabHost / JsonTabServices DI bundles.
│   ├── marker.py            JsonTabWidgetMarker isinstance base for ancestor walks.
│   └── demo_data.py         build_demo_data for empty new tabs.
├── controllers/             Per-tab controllers (mostly stateful).
│   ├── appearance.py        fonts / theme / column scale.
│   ├── navigation.py        keyboard nav / event filter.
│   ├── editability.py       read-only mode.
│   ├── validation.py        TabValidationController (aliased ValidationState).
│   ├── history.py           TabHistoryController — wraps QUndoStack.
│   ├── view.py              ViewController — viewport (selection/expand/scroll).
│   ├── status.py            on_current_changed + size_hint.
│   └── number_types.py      stateless type-change predicates (would_drop_fraction…).
├── seams/                   Narrow boundaries.
│   ├── mutation_gateway.py  DocumentMutationGateway — only entry point for tree edits.
│   └── document_protocol.py narrow Document Protocol.
└── states/                  Passive substates + editing collaborators.
    ├── io_controller.py     IoState (file_path, save_format, dirty + dirtyChanged).
    ├── view_state.py        ViewState (ui, view, search_edit, proxy, delegates).
    ├── editing_controller.py EditingController — exposes commands/inline/move/diff.
    └── editing/             command_dispatcher / inline_edit_controller /
                             move_view_state / tree_actions / context.
```

## 8) `editors/` module layout

```
editors/
├── __init__.py
├── factory.py               create_value_editor dispatch + set/getEditorData.
├── context.py               EditorContextProtocol + ValueDelegateProtocol.
├── inline/                  In-cell editor widgets (no app/documents/tree imports).
│   ├── bigint_spinbox/      QBigIntSpinBox (spinbox.py + validator.py).
│   ├── mpq_spinbox/         QMpqSpinBox (spinbox.py + validator.py).
│   ├── datetime/            BetterDateTimeEditor + validator (enums/regex imported from core/).
│   ├── affix_composite.py   AffixCompositeEditor (prefix/suffix + spinbox).
│   ├── raw_numeric_line.py  RawNumericLineEdit + RawNumericValidator for RAW_FLOAT.
│   ├── secret_line.py       _SecretLineEdit + _SecretEditorWatcher.
│   └── caps_safe_line.py    _CapsLockSafeLineEdit + lock-key constants.
└── windowed/                Modal dialog editors (no app/documents/tree imports).
    ├── multiline_widget.py  QMultilineEditor widget.
    ├── multiline_dialog.py  QMultilineDialog wrapper.
    ├── hexedit/             Hex editor widget (widget.py + chunks/commands/color_manager).
    ├── hex_dialog.py        QHexDialog wrapper.
    └── color_dialog.py      ColorPickerDialog (QColorDialog wiring).
```

## 8a) `core/` module layout

```
core/
├── __init__.py
├── raw_numeric.py           RawNumericValue dataclass + narrow edit regex validator.
├── safe_mpq.py              Safe mpq parsing (parse_mpq, safe_mpq_from_text, MpqParseResult).
├── frozen_value.py          Legacy FrozenValue alias → RawNumericValue (compatibility).
└── datetime_parsing/        Pure datetime parsing (no Qt dependency).
    ├── __init__.py          Re-exports DateTimeCategory, parse_datetime_text, etc.
    ├── enums.py             DateTimeCategory enum.
    ├── regex.py             parse_datetime_text + regex tables.
    ├── compat.py            Thin adapter for pandas Timestamp / datetime.
    └── nano_time.py         NanoTime dataclass for exact nanosecond precision.
```

## 8b) `tree/` module layout (partial — codecs subpackage)

```
tree/
├── codecs/                  Encode/decode for binary and color types.
│   ├── __init__.py
│   ├── bytes_codec.py       decode_bytes / encode_bytes for BYTES/ZLIB/GZIP.
│   └── color_codec.py       parse_color / color_to_html / normalize_color_string.
├── model.py
├── item.py
├── filter_proxy.py
├── types.py
├── item_coercion.py
├── actions/anchors.py
├── commands.py
├── diff.py
├── actions/anchors.py
├── actions/clipboard.py
├── actions/dnd.py
├── actions/move.py
├── actions/sort.py
├── validation/
├── app/validation_presenter.py
├── themes/
├── app/theme_controller.py
├── state/
├── io_formats/
├── ui/
├── dialogs/
```

## 9) `delegates/` module layout (post editors/ extraction)

```
delegates/
├── __init__.py
├── base.py                  Delegate base class.
├── value.py                 ValueDelegate: paint + createEditor → editors.factory.
├── name_delegate.py         Name column delegate.
├── type_delegate.py         Type column delegate.
├── number_affix_delegate.py Affix helpers (editor part moved to editors/inline/).
├── edit_context.py          Delegate-side edit context.
├── validation_badge.py      Presentation helper for validation badges.
└── formatting/              Pure formatting helpers.
    └── value_formatting.py  Display-text formatting for value column.
```

## 10) `ui/` module layout (generated UI + dialog schemas)

```
ui/
├── __init__.py
├── mainwindow.ui            Qt Designer source for main window.
├── mainwindow.py            pyside6-uic generated output.
├── json_tab.ui              Qt Designer source for JsonTab widget.
├── json_tab_ui.py           pyside6-uic generated output.
└── dialogs/                 .ui-backed dialog schemas + generated code.
    ├── attach_schema_dialog.ui / .py
    ├── qhex_dialog.ui / .py
    ├── qmultiline_dialog.ui / .py
    └── secret_prefixes_dialog.ui / .py
```

App-level dialog implementations live in `app/dialogs/` (`attach_schema_dlg.py`,
`secret_prefixes_dlg.py`); editor-level dialog implementations live in
`editors/windowed/` (`multiline_dialog.py`, `hex_dialog.py`, `color_dialog.py`).

## 11) Commands & Gates

```bash
make test                    # QT_QPA_PLATFORM=offscreen timeout 600 pytest -q (1124 pass)
make check-no-reflection     # forbid getattr/hasattr/TYPE_CHECKING outside allowlist
make check-editors-isolation # forbid app/documents/tree imports in concrete editor widgets
make check-tree-isolation    # forbid app/documents/editors/delegates/state/validation imports in tree/
make lint                    # autoflake + isort + black (in place; line-length 120, UI files skipped)
make gate                    # full DoD gate (lint → reflection → editors-isolation → tree-isolation → tests)
```
