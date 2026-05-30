# Editable-Tree-Model-Example — Fast Repo Map

_This is a condensed index and architectural summary. LLM agents should refer to direct source files for implementation
details._
**Last updated:** 2026-05-29 (after Plan 20 Phase I).

## 1) High-level Purpose

A PySide6 desktop **structured-data editor** (JSON, YAML, JSONL) focusing on typed tree editing, exact numerics (mpq),
and a robust undo/redo system. It uses a three-column `Name | Type | Value` model derived from Qt's "Editable Tree
Model".

## 2) LLM Quick-Orientation (Fast Index)

| Domain              | Key Entry Points                                                               |
|:--------------------|:-------------------------------------------------------------------------------|
| **App Shell**       | `main.py`, `app/main_window.py`                                                |
| **Document/Tab**    | `documents/tab.py` (JsonTab — still the routing surface; see §7)               |
| **Tab Substates**   | `documents/states/{io,view,editing,validation}_state.py` (Plan 20 Phase I)     |
| **Tab Helpers**     | `documents/tab_{commands,editing,setup,tree_actions,move_view_state,paths}.py` |
| **Document Seams**  | `documents/{mutation_gateway,view_controller,document_protocol}.py`            |
| **Tree Data Model** | `tree/model.py`, `tree/item.py`                                                |
| **Type System**     | `tree/types.py` (Definitions), `tree/item_coercion.py` (Conversion)            |
| **Editing / UI**    | `delegates/value.py` (Cell editors), `delegates/value_formatting.py`           |
| **Undo System**     | `undo/commands.py` (Operations), `undo/diff.py` (Surgical replay)              |
| **Structural Ops**  | `tree_actions/` (Clipboard, DnD, Move, Sort)                                   |
| **Validation**      | `validation/` (JSON-Schema), `app/validation_presenter.py`                     |
| **Theming**         | `themes/`, `app/theme_controller.py`                                           |
| **Persistence**     | `state/` (View state, settings), `io_formats/` (File I/O)                      |

## 3) Core Invariants & Repo Rules

- **Strict Undo/Redo**: ALL mutations (renames, value edits, type changes, structural moves) must be routed through
  `JsonTab.push_*` or `commit_set_data` to ensure they are undoable via `QUndoCommand`s.
- **Anchor-based Moves**: Every structural move (Drag-and-drop, Keyboard Alt+Up/Down, Cut/Paste) uses the `MoveAnchor`
  primitive in `tree_actions/anchors.py`. This ensures consistency across different UI interactions.
- **Type-Centric**: Type inference (`tree/types.py`) and coercion (`tree/item_coercion.py`) are the source of truth for
  how data is handled. Don't scatter type logic in the UI.
- **Surgical Model Updates**: The `DiffApplier` (`undo/diff.py`) is used during Undo/Redo to emit minimal Qt signals.
  This preserves UI state like selection and expansion that would be lost on a full model reset.
- **No external `data_store.*` reads** (Plan 20). External callers (`app/`, `undo/`, `tree_actions/`, `state/`) must
  reach state through typed `JsonTab.*` properties. The pre-commit hook
  `.githooks/_check_data_store_leaks.sh` enforces this for 17 retired attributes.
- **Viewport via signal** (Plan 20 Phase D). Selection / expand / scroll happen through
  `JsonTab.view_controller.request_*` calls that emit `viewportRequested(kind, payload)`. Undo commands NEVER call
  `setCurrentIndex` directly.
- **No reflection**: `getattr` / `hasattr` / `TYPE_CHECKING` / `AttributeError` are banned outside a tiny allowlist
  (`.githooks/pre-commit-ci`); tests must annotate exceptions with `# allow: <reason>`.
- **Separation of Concerns**:
    - `tree/`: Data structure and model.
    - `delegates/`: Presentation and cell-level editing.
    - `tree_actions/`: Logic for high-level operations.
    - `documents/`: Orchestration of model, view, undo, and search for a single tab.
    - `app/`: Global window management and cross-tab controllers.

## 4) Practical Mental Model

- **The Shell (`app/`)**: Manages the multi-tab interface, global settings, and theme synchronization.
- **The Tab (`documents/`)**: Still the de-facto routing surface for a single document — see §7 for the honest
  caveat about JsonTab remaining a God Object internally.
- **The Tree (`tree/`)**: A hierarchical `JsonTreeItem` structure. Invariants like "OBJECT children must have names" are
  enforced here.
- **The Edit Flow**: `ValueDelegate` (UI) → `JsonTab.commit_set_data` → `DocumentMutationGateway` →
  `QUndoCommand` → `JsonTreeModel.setData` → `JsonTreeItem.set_data`.

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

## 7) `documents/` module layout (post Plan 20)

```
documents/
├── tab.py                   JsonTab QWidget — 607 LOC / 117 methods+properties.
│                            STILL a God Object internally (Plan 21 target).
├── tab_data.py              JsonTabData — composes 4 substates + 2 cross-cutting
│                            controllers + ~30 @property forwards for tests.
├── tab_init.py              bootstrap() — dense __init__ body extracted from JsonTab.
├── tab_setup.py             init_layout / init_model / init_delegates / init_shortcuts.
├── tab_data_facade.py       (deleted in Plan 20 I5; contents merged into tab_data.py)
│
├── states/                  (Plan 20 Phase I — passive containers)
│   ├── io_state.py          IoState   (file_path, save_format, dirty + dirtyChanged)
│   ├── view_state.py        ViewState (ui, view, search_edit, proxy, 3× delegate)
│   ├── editing_state.py     EditingState (model, mutations, affix_mru, history,
│   │                                       last_move_placed)
│   └── validation_state.py  ValidationState (alias for TabValidationController)
│
├── mutation_gateway.py      DocumentMutationGateway — the only entry point for
│                            tree edits. Has both QModelIndex- and path-typed APIs
│                            (Plan 20 H1+H2).
├── view_controller.py       DocumentView — viewport controller. Owns selection /
│                            expand / scroll; writes go through
│                            `viewportRequested(kind, payload)` (Plan 20 D-full).
├── document_protocol.py     Narrow Document Protocol stub (Plan 20 A1). NOT YET the
│                            advertised return type — see report.
├── tab_marker.py            JsonTabWidgetMarker isinstance base for tree_actions/
│                            ancestor walks (Plan 20 G).
│
├── tab_appearance.py        JsonTabAppearanceController — fonts, theme, column scale
├── tab_navigation.py        JsonTabNavigationController — keyboard nav / event filter
├── tab_editability.py       JsonTabEditabilityController — read-only mode
├── tab_history.py           TabHistoryController — wraps QUndoStack
├── tab_io_controller.py     back-compat re-export (`TabIOController = IoState`)
├── tab_io.py                save / save_as / snapshot primitives
├── tab_validation.py        TabValidationController (aliased as ValidationState)
├── tab_validation_view.py   JsonTabValidationViewController — goto-issue navigation
│
├── tab_commands.py          Free functions taking `tab` first: push_*. Action layer.
├── tab_editing.py           Free functions: on_type_changed, edit_from_enter, etc.
├── tab_tree_actions.py      Free functions: run_tree_action + insert_sibling helpers
├── tab_move_view_state.py   Free functions: capture/apply move-view caches
├── tab_paths.py             Free functions: index_path / index_from_path
├── tab_status.py            Free functions: on_current_changed + size_hint
├── tab_number_types.py      would_drop_fraction_on_type_change predicate
├── tab_demo_data.py         build_demo_data for empty new tabs
└── tab_dependencies.py      JsonTabHost / JsonTabServices DI bundles
```

## 8) Status of Plan 20 (decouple-json-tab)

- **Phases A → I**: ✅ complete (6 sessions, ~22 commits on branch `decouple-json-tab`).
- **Phase J**: ⏳ closeout pending (ai-memory updates + tag + merge).
- **What Plan 20 actually achieved**: external `data_store.*` leaks **212 → 0**; viewport-via-signal
  in place; mutation gateway gained a path-typed parallel API; `JsonTabData` decomposed into 4 substates;
  `JsonTabDataFacade` and `tab_protocols.py` deleted; test suite stable (1124 pass, ~18.5s).
- **What Plan 20 did NOT achieve**: `JsonTab` itself is still a God Object — it grew from 407 LOC / ~60
  methods to 607 LOC / 117 methods because every retired leak was replaced by a typed `@property` forward on
  JsonTab. See `reports/jsontab_god_object_followup_report.md` for the honest assessment and
  `plans/21-promote-substates-to-controllers.md` for the next pass.

## 9) Commands & Gates

```bash
make test               # QT_QPA_PLATFORM=offscreen timeout 600 pytest -q (1124 pass)
make check-no-reflection # forbid getattr/hasattr/TYPE_CHECKING outside allowlist
make lint               # isort + black + ruff in place
make gate               # full DoD gate used per Plan 20 step
```

Branch `decouple-json-tab` is shippable at any phase boundary; merge to `master` is gated on Phase J.
