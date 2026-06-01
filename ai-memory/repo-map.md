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

## 7) `documents/` module layout (post Plan 20 + responsibility-segregation split)

```
documents/
├── tab.py                   JsonTab QWidget — thin-ish facade / routing surface.
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
└── states/                  Passive substates + editing collaborators (Plan 20/22).
    ├── io_controller.py     IoState (file_path, save_format, dirty + dirtyChanged).
    ├── view_state.py        ViewState (ui, view, search_edit, proxy, delegates).
    ├── editing_controller.py EditingController (still a forwarding shell — Plan §3.2).
    └── editing/             command_dispatcher / inline_edit_controller /
                             move_view_state / tree_actions / context.
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
