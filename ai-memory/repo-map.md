# Editable-Tree-Model-Example — Fast Repo Map

_This is a condensed index and architectural summary. LLM agents should refer to direct source files for implementation
details._

## 1) High-level Purpose

A PySide6 desktop **structured-data editor** (JSON, YAML, JSONL) focusing on typed tree editing, exact numerics (mpq),
and a robust undo/redo system. It uses a three-column `Name | Type | Value` model derived from Qt's "Editable Tree
Model".

## 2) LLM Quick-Orientation (Fast Index)

| Domain              | Key Entry Points                                                     |
|:--------------------|:---------------------------------------------------------------------|
| **App Shell**       | `main.py`, `app/main_window.py`                                      |
| **Document/Tab**    | `documents/tab.py` (The main Controller for one file)                |
| **Tree Data Model** | `tree/model.py`, `tree/item.py`                                      |
| **Type System**     | `tree/types.py` (Definitions), `tree/item_coercion.py` (Conversion)  |
| **Editing / UI**    | `delegates/value.py` (Cell editors), `delegates/value_formatting.py` |
| **Undo System**     | `undo/commands.py` (Operations), `undo/diff.py` (Surgical replay)    |
| **Structural Ops**  | `tree_actions/` (Clipboard, DnD, Move, Sort)                         |
| **Validation**      | `validation/` (JSON-Schema), `app/validation_presenter.py`           |
| **Theming**         | `themes/`, `app/theme_controller.py`                                 |
| **Persistence**     | `state/` (View state, settings), `io_formats/` (File I/O)            |

## 3) Core Invariants & Repo Rules

- **Strict Undo/Redo**: ALL mutations (renames, value edits, type changes, structural moves) must be routed through
  `JsonTab.push_*` or `commit_set_data` to ensure they are undoable via `QUndoCommand`s.
- **Anchor-based Moves**: Every structural move (Drag-and-drop, Keyboard Alt+Up/Down, Cut/Paste) uses the `MoveAnchor`
  primitive in `tree_actions/anchors.py`. This ensures consistency across different UI interactions.
- **Type-Centric**: Type inference (`tree/types.py`) and coercion (`tree/item_coercion.py`) are the source of truth for
  how data is handled. Don't scatter type logic in the UI.
- **Surgical Model Updates**: The `DiffApplier` (`undo/diff.py`) is used during Undo/Redo to emit minimal Qt signals.
  This preserves UI state like selection and expansion that would be lost on a full model reset.
- **Separation of Concerns**:
    - `tree/`: Data structure and model.
    - `delegates/`: Presentation and cell-level editing.
    - `tree_actions/`: Logic for high-level operations.
    - `documents/`: Orchestration of model, view, undo, and search for a single tab.
    - `app/`: Global window management and cross-tab controllers.

## 4) Practical Mental Model

- **The Shell (`app/`)**: Manages the multi-tab interface, global settings, and theme synchronization.
- **The Tab (`documents/`)**: The "God Object" for a single document, holding its own Undo stack, filter proxy, and
  delegates.
- **The Tree (`tree/`)**: A hierarchical `JsonTreeItem` structure. Invariants like "OBJECT children must have names" are
  enforced here.
- **The Edit Flow**: `ValueDelegate` (UI) → `JsonTab.commit_set_data` → `QUndoCommand` → `JsonTreeModel.setData` →
  `JsonTreeItem.set_data`.

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
