# Code Quality Audit — Editable-Tree-Model-Example

**Date:** 2026-06-01  
**Scope:** Full production codebase (~21 300 LOC across 80+ modules)  
**Focus:** Responsibility segregation, architectural boundaries, code hygiene  
**Test surface:** 1 124 collected

---

## Executive Summary

| Dimension                      | Grade  | Notes                                                                    |
|:-------------------------------|:------:|:-------------------------------------------------------------------------|
| **Responsibility Segregation** | **A−** | Exceptional post-refactor state; a few upward-import leaks remain        |
| **Module Cohesion**            | **A**  | Every module has a clear, single purpose                                 |
| **Coupling Control**           | **B+** | Protocol-based seams are strong; `tree/` has 6 upward imports            |
| **File Size Discipline**       | **A−** | One outlier at 1 130 lines (hex widget); all others ≤ 774                |
| **Undo/Mutation Discipline**   | **A**  | Gateway pattern is enforced; all mutations are typed commands            |
| **Editor Isolation**           | **A**  | Concrete editors import nothing from app/documents/tree; enforced by CI  |
| **Reflection Ban**             | **A**  | `getattr`/`hasattr`/`TYPE_CHECKING` forbidden by pre-commit hook         |
| **Type Safety**                | **B+** | Modern Python 3.12+ throughout; some `Any` and loose `tab` typing        |
| **Test Coverage**              | **B**  | 1 124 tests; delegate matrix and round-trip property tests still missing |
| **Tooling & CI**               | **B**  | `make gate` is solid; no coverage snapshot, `pytest-qt` not pinned       |

**Overall: A−** — This is a well-above-average codebase. The responsibility-segregation refactoring (Plan 20 / Plan 21)
has been executed thoroughly, and the architectural seams are genuinely narrow. The remaining issues are mostly about
tightening a few upward imports and closing test gaps.

---

## 1. Responsibility Segregation — Detailed Analysis

### 1.1 The `documents/` Package (Grade: A)

The `documents/` package is the architectural centrepiece, and it shows the most deliberate segregation work:

**Structure:**

```
documents/
├── tab.py                   219 lines — thin facade
├── composition/             Bootstrap & construction
│   ├── init.py              119 lines — bootstrap()
│   ├── setup.py             init_layout / init_model / init_delegates / init_shortcuts
│   ├── factory.py           Tab construction helpers
│   ├── dependencies.py      84 lines — DI bundles (JsonTabHost, JsonTabServices)
│   ├── marker.py            isinstance base for ancestor walks
│   └── demo_data.py         Demo data builder
├── controllers/             Per-tab stateful controllers
│   ├── appearance.py        268 lines — fonts / theme / column scale
│   ├── navigation.py        Keyboard nav / event filter
│   ├── editability.py       Read-only mode
│   ├── validation.py        TabValidationController
│   ├── history.py           QUndoStack wrapper
│   ├── view.py              279 lines — selection / expansion / scroll
│   ├── status.py            on_current_changed + size_hint
│   └── number_types.py      Stateless type-change predicates
├── seams/
│   ├── mutation_gateway.py  104 lines — ONLY entry point for tree edits
│   └── document_protocol.py 86 lines — typed Document Protocol
└── states/
    ├── io_controller.py     92 lines — file path, dirty flag, save
    ├── view_state.py        31 lines — passive dataclass for UI refs
    ├── editing_controller.py 100 lines — editing state + collaborators
    └── editing/             command_dispatcher / inline_edit / move_view_state / tree_actions / context
```

**Strengths:**

1. **`JsonTab` is genuinely thin.** At 219 lines, it is a pure routing surface — every method either delegates to a
   controller/state or exposes a property. The `__init__` body is a single call to `tab_init.bootstrap()`. This is the
   ideal facade pattern.

2. **`DocumentMutationGateway` is a real seam.** It is the *only* entry point for tree edits. Every mutation (rename,
   edit value, change type, insert, remove, move, sort, switch case) flows through `commit_set_data` or one of the
   `push_*` methods. The gateway itself is a thin forwarding facade (104 lines) that routes to
   `EditingController.commands` — it does not contain business logic.

3. **`Document` Protocol is narrow and typed.** The `@runtime_checkable` protocol in `document_protocol.py` defines
   exactly the surface that `app/` and `tree_actions/` may call. This is a proper Interface Segregation Principle
   application — consumers depend on the protocol, not the concrete `JsonTab`.

4. **DI via `JsonTabServices`.** The `dependencies.py` module provides a frozen dataclass bundle (`JsonTabServices`)
   with a `JsonTabHost` protocol, a `ThemeSpec`, and an `IconProvider`. Legacy callback-based construction is supported
   via `build_legacy_json_tab_services`. This is clean dependency injection without a framework.

5. **`ViewState` is a passive dataclass.** At 31 lines, it holds only UI widget references. No logic, no signals — pure
   data. Controllers read from it; they don't write to it (except during bootstrap).

6. **Viewport via signal.** `ViewController.viewportRequested` is a signal that carries `(kind, payload)` tuples. Undo
   commands never call `setCurrentIndex` directly — they emit a request, and the controller applies it. This prevents
   stale-index crashes.

**Minor concerns:**

- `IoController.save()` catches `Exception` broadly (line 54). The comment in `todo-n-fixme.md` already flags this. A
  narrower catch with structured diagnostics would improve the seam.
- `IoController.save_as()` directly uses `QFileDialog` — this couples the IO controller to a Qt dialog. For testability,
  the dialog could be injected, but this is a low-priority concern since `IoController` is already per-tab and the
  dialog is only reachable from user action.

### 1.2 The `tree/` Package (Grade: B+)

**Structure:**

```
tree/
├── item.py           348 lines — JsonTreeItem (data node)
├── item_coercion.py  571 lines — type coercion logic
├── item_names.py     Name validation / unique-child-name
├── model.py          464 lines — JsonTreeModel (QAbstractItemModel)
├── model_protocol.py 27 lines — TreeModelLike protocol
├── model_roles.py    Role helpers
├── types.py          343 lines — JsonType enum + inference
├── types_datetime.py Datetime conversion lattice
├── filter_proxy.py   54 lines — TreeFilterProxy
├── stubs.py          Placeholder values for coercion
├── view.py           JsonTreeView
```

**Strengths:**

1. **Data/model separation is clean.** `JsonTreeItem` owns data and child management; `JsonTreeModel` owns the Qt model
   API. The model never stores business logic — it delegates to items.

2. **Type system is centralized.** `tree/types.py` is the single source of truth for `JsonType`, type families, and
   `parse_json_type`. Coercion logic lives in `tree/item_coercion.py`. This is good — type logic is not scattered in the
   UI.

3. **`TreeModelLike` protocol.** `tree_actions/` consumes `TreeModelLike` rather than the concrete `JsonTreeModel`,
   enabling test doubles.

4. **Filter proxy is minimal.** At 54 lines, `TreeFilterProxy` does one thing: recursive name+value substring filtering.
   No business logic leaks in.

**Concerns — upward imports:**

The `tree/` package imports from packages that sit *above* it in the dependency hierarchy:

| Source file             | Import                                                                       | Direction         |
|:------------------------|:-----------------------------------------------------------------------------|:------------------|
| `tree/item.py`          | `from editors.inline.datetime.enums import DateTimeCategory`                 | tree → editors    |
| `tree/item.py`          | `from editors.inline.datetime.regex import parse_datetime_text`              | tree → editors    |
| `tree/item.py`          | `from state.secret_settings import get_secret_word_prefixes`                 | tree → state      |
| `tree/item.py`          | `from validation.secret_names import name_looks_secret`                      | tree → validation |
| `tree/item_coercion.py` | `from editors.inline.datetime.enums import DateTimeCategory`                 | tree → editors    |
| `tree/item_coercion.py` | `from editors.inline.datetime.regex import parse_datetime_text`              | tree → editors    |
| `tree/item_coercion.py` | `from delegates.formatting.bytes_codec import decode_bytes` (lazy)           | tree → delegates  |
| `tree/item_coercion.py` | `from delegates.formatting.color_codec import normalize_color_string` (lazy) | tree → delegates  |
| `tree/types.py`         | `from editors.inline.datetime import parse_datetime_text`                    | tree → editors    |

These are **architectural inversions**: `tree/` is documented as a low-level data package, but it reaches up to
`editors/`, `delegates/`, `state/`, and `validation/`. The lazy imports in `item_coercion.py` mitigate the runtime
impact (no circular import), but the dependency direction is still wrong.

**Recommended fix:** Extract the datetime parsing regex/enums into a shared `tree/_datetime_parsing.py` or a `core/`
package that both `tree/` and `editors/` can import. Similarly, move `bytes_codec` decode/encode and `color_codec`
normalization into `tree/` or a shared `codecs/` package, since they are data-layer concerns, not presentation concerns.
The `secret_names` and `secret_settings` imports could be resolved by injecting a name-matching predicate into
`JsonTreeItem.__init__`.

### 1.3 The `editors/` Package (Grade: A)

**Structure:**

```
editors/
├── factory.py        360 lines — dispatch + set/getEditorData
├── context.py        56 lines — EditorContextProtocol + ValueDelegateProtocol
├── inline/           In-cell editor widgets
│   ├── bigint_spinbox/
│   ├── mpq_spinbox/
│   ├── datetime/     BetterDateTimeEditor + validator/regex/enums
│   ├── affix_composite.py
│   ├── secret_line.py
│   └── caps_safe_line.py
└── windowed/         Modal dialog editors
    ├── multiline_widget.py / multiline_dialog.py
    ├── hexedit/      widget.py (1 130 lines) + chunks/commands/color_manager
    ├── hex_dialog.py
    └── color_dialog.py
```

**Strengths:**

1. **Concrete editors are truly isolated.** `editors/inline/` and `editors/windowed/` import nothing from `app/`,
   `documents/`, or `tree/`. This is enforced by `make check-editors-isolation` (a CI gate). This is excellent — the
   editors are reusable, testable widgets.

2. **Protocol-based dispatch seam.** `editors/context.py` defines `EditorContextProtocol` and `ValueDelegateProtocol`.
   The factory receives a delegate that implements `ValueDelegateProtocol`, and commits values through
   `EditorContextProtocol.commit()`. This is a proper dependency inversion — the factory doesn't know about `JsonTab` or
   `DocumentMutationGateway`.

3. **Factory is the single dispatch point.** `create_value_editor`, `set_value_editor_data`, and `set_value_model_data`
   are the only ways editors are created and populated. The `match`/`case` dispatch is exhaustive (the final `_` case
   raises `ValueError`).

**Concerns:**

- `editors/factory.py` imports from `delegates/` (formatting codecs, number_affix_delegate helpers) and `state/` (
  edit_limits). These are acceptable since the factory is the *dispatch seam* (explicitly allowed to import `tree.types`
  and `tree.item` per the repo rules), but the `delegates/` and `state/` imports push the boundary. The
  `state.edit_limits` import is a pure-function call (no Qt state), so it's pragmatically fine.

- `editors/windowed/hexedit/widget.py` at 1 130 lines is the largest file in the codebase. It's a self-contained hex
  editor widget with its own chunk model, commands, and color manager. While large, it's cohesive — splitting it would
  create artificial boundaries inside a single-responsibility widget.

### 1.4 The `delegates/` Package (Grade: A−)

**Structure:**

```
delegates/
├── base.py                  Delegate base class
├── value.py                 223 lines — ValueDelegate (paint + createEditor → factory)
├── name_delegate.py         Name column delegate
├── type_delegate.py         Type column delegate
├── number_affix_delegate.py Affix helpers
├── edit_context.py          Delegate-side edit context
├── validation_badge.py      Presentation helper
└── formatting/              Pure formatting/codec helpers
    ├── value_formatting.py  Display-text formatting
    ├── bytes_codec.py       Encode/decode for BYTES/ZLIB/GZIP
    └── color_codec.py       Encode/decode for COLOR_RGB/RGBA
```

**Strengths:**

1. **Presentation-only responsibility.** Delegates paint cells and create editors — they don't contain business logic.
   `ValueDelegate.createEditor` delegates to `editors/factory.create_value_editor`, and `setEditorData`/`setModelData`
   delegate to the factory's corresponding functions.

2. **Formatting helpers are pure functions.** `delegates/formatting/` contains only pure functions for display text,
   bytes encoding/decoding, and color parsing. No Qt state, no side effects.

3. **Edit context injection.** `ValueDelegate` receives a `DelegateEditContext` that implements `EditorContextProtocol`.
   This is the bridge between the delegate (presentation) and the tab (mutation gateway).

**Concern:**

- `delegates/formatting/bytes_codec.py` and `color_codec.py` are imported by `tree/item_coercion.py` (upward import).
  These codec functions are data-layer concerns (encode/decode bytes for storage) that happen to live in the
  presentation package. They should be in `tree/` or a shared `codecs/` package.

### 1.5 The `undo/` Package (Grade: A)

**Structure:**

```
undo/
├── commands.py   466 lines — 8 typed QUndoCommand subclasses
└── diff.py       155 lines — DiffApplier (surgical model replay)
```

**Strengths:**

1. **Every mutation is a typed command.** `_RenameCmd`, `_EditValueCmd`, `_ChangeTypeCmd`, `_InsertRowsCmd`,
   `_RemoveRowsCmd`, `_MoveRowsCmd`, `_SortKeysCmd`, `_SwitchFieldCaseCmd` — all are `QUndoCommand` subclasses with
   path-based addressing (not `QModelIndex`-based), which sidesteps index invalidation.

2. **`mergeWith` collapsing.** `_RenameCmd` and `_EditValueCmd` collapse same-path edits within a 500 ms window. This is
   a UX win — rapid typing produces a single undo step.

3. **`DiffApplier` is surgical.** It emits minimal `dataChanged` signals (row-level, not model-reset), preserving
   expansion and selection through undo/redo. The `diff_object` and `diff_array` methods do recursive structural
   diffing.

4. **No upward imports.** `undo/` imports only from `tree/` and `units/`. It never imports from `app/`, `documents/`, or
   `delegates/`. Commands hold a `tab` reference (loosely typed), but they access it only through the `Document`
   -protocol surface.

**Minor concern:**

- Undo commands hold a `_tab` reference typed as `"JsonTab"` (string annotation). Since they only call `Document`
  -protocol methods, the type annotation could be narrowed to `Document` for clarity.

### 1.6 The `tree_actions/` Package (Grade: B+)

**Structure:**

```
tree_actions/
├── _tab_lookup.py    43 lines — find_owning_tab (ancestor walk)
├── anchors.py        MoveAnchor primitives
├── clipboard.py      413 lines — MIME (de)serializer + copy actions
├── context_menu.py   547 lines — context menu construction
├── dnd.py            Drag-and-drop handling
├── field_case.py     Case conversion tokenizer
├── paste.py          439 lines — Multi-action paste semantics
├── selection.py      Selection helpers
└── structure.py      774 lines — Insert/delete/move/sort/expand/collapse
```

**Strengths:**

1. **`_tab_lookup.py` is a proper seam.** It uses `isinstance(JsonTabWidgetMarker)` to find the owning tab, then returns
   it typed as `Document`. This avoids importing `documents.tab` from `tree_actions/`.

2. **Dual-path functions.** Most functions in `structure.py` have two paths: one for when a `tab` is found (uses the
   undo-aware `tab.mutations.push_*` API), and one for when no tab exists (direct model manipulation for headless test
   fixtures). This is pragmatic — it keeps the functions testable without a full tab.

3. **Anchor-based move primitive.** Every move operation (keyboard, drag-drop, paste cleanup) feeds a `MoveAnchor` into
   `push_move_rows_anchor`. This collapsed three previously overlapping move algorithms into one.

**Concerns:**

- **`structure.py` at 774 lines** is the largest non-widget production file. It handles insert, delete, move, sort,
  expand, collapse, and case switching. These are related but distinct operations. A split into `structure_insert.py`,
  `structure_move.py`, `structure_sort.py`, and `structure_expand.py` would improve navigability, though the current
  monolith is still within reason.

- **Underscore-prefixed names re-exported across modules.** `_resolve_model`, `_to_source_index`, `_index_path`, etc.
  are defined in `selection.py` with underscore prefixes but imported by sibling modules. The underscore convention
  implies "private to this module," but they're used as a shared internal API. This is a naming smell, not a functional
  issue.

- **`clipboard.py` imports from `state.clipboard_settings`** (a lazy import inside `_dump_text`). This is an upward
  import from `tree_actions/` to `state/`, but it's pragmatically fine since `_dump_text` is a pure function that reads
  a QSettings value.

### 1.7 The `app/` Package (Grade: B+)

**Structure:**

```
app/
├── main_window.py         638 lines — MainWindow
├── main_window_actions.py Action setup + update_actions
├── app_settings.py        Edit-warning-limits + secret-prefixes presenter
├── close_confirm.py       Save/Discard/Cancel dialog
├── font_controller.py     Font preferences (broadcasts to tabs)
├── history.py             Undo view binding
├── recent_files.py        Recent files menu
├── schema_tab_pool.py     Schema tab reuse
├── tab_lifecycle.py       Tab open/close/reopen presenter
├── theme_controller.py    373 lines — Theme loading + switching
├── validation_dock.py     Validation dock widget
├── validation_presenter.py 306 lines — Dock ↔ validation bridge
├── runtime_compat.py      Runtime compatibility shims
└── dialogs/               App-level dialog implementations
```

**Strengths:**

1. **`MainWindow` delegates heavily.** Tab lifecycle is in `TabLifecyclePresenter`, font management in `FontController`,
   theme in `ThemeController`, validation in `DockValidationPresenter`, action setup in `main_window_actions.py`. The
   window itself is a thin orchestrator.

2. **`_current_tab()` returns `Document | None`.** The main window consumes tabs through the `Document` protocol, not
   the concrete `JsonTab`. This is proper interface segregation.

3. **Tab lifecycle is well-encapsulated.** `TabLifecyclePresenter` owns the closed-tabs stack, tab creation, and tab
   closing. The main window just calls `self._tab_lifecycle.close_current_tab()` etc.

**Concerns:**

- **`MainWindow` at 638 lines** is the second-largest production file. It still contains some logic that could be
  extracted (e.g., `_confirm_reload_dirty_tab`, `_reload_tab_from_path`, `_save_tab`). These are file-operation
  workflows that could live in a `FileOperationsPresenter`.

- **Deprecated shim properties.** `_closed_tabs_stack` and `_MAX_CLOSED_TABS` are retained for test back-compat. These
  should be removed once tests migrate.

- **`_setup_validation_dock` and `_setup_schemas_menu` are no-op stubs** (lines 200–204) retained for back-compat. Dead
  code.

### 1.8 The `validation/` Package (Grade: A−)

**Structure:**

```
validation/
├── __init__.py
├── _engine.py          jsonschema validation engine
├── _sanitize.py        Sanitize mpq/Decimal/datetime/bytes for jsonschema
├── error_adapter.py    Adapt jsonschema errors
├── index.py            IssueIndex (path → severity)
├── issue.py            ValidationIssue
├── json_pointer.py     JSON Pointer utilities
├── schema_registry.py  Shared schema loading + hot-reload
├── schema_source.py    Schema source (file/URL/inline)
├── schema_types.py     SchemaEntry / SchemaBinding types
├── secret_names.py     22 lines — name_looks_secret
├── validator.py        274 lines — top-level validator
└── yaml_validate.py    YAML multi-doc validation
```

**Strengths:**

1. **No upward imports.** `validation/` imports nothing from `app/` or `documents/`. It's a pure library.

2. **`secret_names.py` is minimal.** At 22 lines, it's a pure function with no Qt dependency. It's imported by
   `tree/item.py` (upward, but the function is stateless).

3. **Schema registry is shared across tabs.** One `SchemaEntry` per source, with `QFileSystemWatcher`-driven hot reload.
   This avoids redundant file reads.

**Concern:**

- `validation/secret_names.py` is imported by `tree/item.py`, creating an upward dependency. Since `name_looks_secret`
  is a pure function with no Qt or app dependency, it could live in a shared `core/` or `utils/` package.

### 1.9 The `state/` Package (Grade: A−)

**Structure:**

```
state/
├── affix_mru.py           Per-tab MRU for number affixes
├── clipboard_settings.py  Copy-as-YAML toggle (QSettings)
├── edit_limits.py         Edit warning limits (QSettings)
├── qsettings_coercion.py  Safe QSettings type coercion
├── recent_schemas.py      Recent schemas menu (QSettings)
├── secret_settings.py     Secret word prefixes (QSettings)
├── theme_settings.py      Theme preference (QSettings)
├── validation_settings.py Schema path binding (QSettings)
└── view_state.py          Per-file view state persistence
```

**Strengths:**

1. **Each module is a focused QSettings wrapper.** No module exceeds ~100 lines. Each reads/writes a specific set of
   settings.

2. **`view_state.py` has safe coercion.** QSettings can return unexpected types across platforms;
   `qsettings_coercion.py` handles this.

**Concern:**

- `state/secret_settings.py` is imported by `tree/item.py` (upward). The `get_secret_word_prefixes` function reads from
  QSettings at call time. This couples the data layer to a Qt persistence mechanism. An injection pattern (passing the
  prefixes as a parameter) would be cleaner.

### 1.10 The `io_formats/` Package (Grade: A)

**Structure:**

```
io_formats/
├── __init__.py    Re-exports
├── atomic.py      Atomic writes via os.replace
├── detect.py      Format detection from file extension
├── dump.py        47 lines — Serialize to JSON/YAML/JSONL/YAML-multi
├── load.py        83 lines — Load from JSON/YAML/JSONL/YAML-multi
```

**Strengths:**

1. **No upward imports.** `io_formats/` imports only from `settings`, `tree.types`, `units.number_affix`, and `mpq2py`.
   It's a pure I/O library.

2. **Atomic writes.** `save_file` uses `os.replace` for atomic file replacement.

3. **Number-affix round-trip.** `_decode_number_affixes` and `_encode_number_affixes` ensure `NumberAffix` values
   survive JSON/YAML serialization.

4. **Tiny modules.** `dump.py` at 47 lines and `load.py` at 83 lines are exemplary in their focus.

---

## 2. Cross-Boundary Import Map

The intended dependency direction is:

```
app/ → documents/ → tree/
                  → editors/ (via delegates/)
                  → undo/
                  → tree_actions/
                  → validation/
                  → state/
                  → io_formats/

editors/ ← delegates/ (factory ↔ delegate)
tree/ ← (nothing above it)
```

**Actual violations (tree/ reaching upward):**

| From                    | To                                 |  Count   | Severity |
|:------------------------|:-----------------------------------|:--------:|:--------:|
| `tree/item.py`          | `editors.inline.datetime`          |    2     |  Medium  |
| `tree/item.py`          | `state.secret_settings`            |    1     |  Medium  |
| `tree/item.py`          | `validation.secret_names`          |    1     |   Low    |
| `tree/item_coercion.py` | `editors.inline.datetime`          |    2     |  Medium  |
| `tree/item_coercion.py` | `delegates.formatting.bytes_codec` | 3 (lazy) |  Medium  |
| `tree/item_coercion.py` | `delegates.formatting.color_codec` | 1 (lazy) |  Medium  |
| `tree/types.py`         | `editors.inline.datetime`          |    1     |  Medium  |

**Total: 11 upward imports from `tree/`.** The lazy imports in `item_coercion.py` avoid circular-import crashes, but the
architectural direction is still wrong.

**Recommended resolution:**

1. **Extract `editors/inline/datetime/regex.py` and `enums.py`** into a shared package (e.g., `core/datetime_parsing/`)
   that both `tree/` and `editors/` can import. These modules contain no Qt code — they're pure parsing logic.

2. **Move `delegates/formatting/bytes_codec.py` and `color_codec.py`** into `tree/` or a shared `codecs/` package.
   Encode/decode is a data-layer concern, not a presentation concern.

3. **Inject `get_secret_word_prefixes` and `name_looks_secret`** into `JsonTreeItem.__init__` as optional callables,
   defaulting to the current implementations. This removes the hard upward dependency.

---

## 3. File Size Analysis

| File                                          | Lines | Assessment                                     |
|:----------------------------------------------|------:|:-----------------------------------------------|
| `editors/windowed/hexedit/widget.py`          | 1 130 | Large but cohesive (self-contained hex widget) |
| `tree_actions/structure.py`                   |   774 | Could split; still navigable                   |
| `app/main_window.py`                          |   637 | Could extract file-operation presenter         |
| `tree/item_coercion.py`                       |   571 | Dense but single-purpose                       |
| `tree_actions/context_menu.py`                |   547 | Acceptable                                     |
| `editors/inline/datetime/better_dt_editor.py` |   491 | Acceptable                                     |
| `undo/commands.py`                            |   465 | Acceptable                                     |
| `tree/model.py`                               |   463 | Acceptable                                     |
| `tree_actions/paste.py`                       |   439 | Acceptable                                     |
| `tree_actions/clipboard.py`                   |   413 | Acceptable                                     |

All production files except `hexedit/widget.py` are under 800 lines. The `hexedit/widget.py` outlier is a self-contained
third-party-style widget — splitting it would create artificial boundaries. The `pros-n-cons.md` claim of "no source
file outside generated `mainwindow.py` exceeds ~580 lines" is **inaccurate** — `hexedit/widget.py` is at 1 130,
`structure.py` at 774, and `main_window.py` at 637. The spirit of the claim (no god classes) holds, but the specific
number is wrong.

---

## 4. Mutation Discipline

**All mutations flow through the gateway:**

```
ValueDelegate → editors.factory._commit() → EditorContextProtocol.commit()
    → DocumentMutationGateway.commit_set_data()
        → EditingController.commands.push_*()
            → QUndoCommand subclass
                → JsonTreeModel.setData() / removeRows() / move_row()
                    → JsonTreeItem.set_data()
```

This chain is **unbroken**. I found no places where production code bypasses the gateway to mutate the tree directly (
except in the headless fallback paths in `tree_actions/structure.py`, which are intentional for test fixtures).

**Read-only guard is triple-checked:**

1. `DocumentMutationGateway.commit_set_data` checks `tab.editability.is_read_only`
2. `CommandDispatcher.push_*` methods check `tab.editability.is_read_only`
3. `JsonTreeModel.setData/removeRows/insertRows/move_row/sort_keys` check `self._read_only`

This triple-check is defensive but not harmful — it ensures that even if a caller bypasses one layer, the model still
rejects mutations.

---

## 5. Protocol & Seam Quality

| Seam                                         | Protocol             | Runtime-checkable |              Enforced by CI              |
|:---------------------------------------------|:---------------------|:-----------------:|:----------------------------------------:|
| `Document` (tab → app)                       | `@runtime_checkable` |         ✓         | No (but `_tab_lookup` uses `isinstance`) |
| `TreeModelLike` (model → tree_actions)       | `Protocol`           |         ✓         |                    No                    |
| `JsonTabHost` (host → tab)                   | `@runtime_checkable` |         ✓         |                    No                    |
| `EditorContextProtocol` (tab → editors)      | `Protocol`           |         ✗         |                    No                    |
| `ValueDelegateProtocol` (delegate → editors) | `Protocol`           |         ✗         |                    No                    |

The `Document` and `JsonTabHost` protocols are `@runtime_checkable`, which is good for the `isinstance` checks in
`_tab_lookup.py`. The editor-side protocols are not runtime-checkable, but they're used only for static type checking —
the factory receives a `ValueDelegateProtocol` and calls methods on it. This is fine.

**Missing enforcement:** There's no CI check that verifies `JsonTab` actually implements all `Document` protocol
attributes. A `mypy` check or a dedicated test would catch protocol violations at CI time.

---

## 6. Code Hygiene Issues

| Issue                                                                  | Severity | Location                                    |
|:-----------------------------------------------------------------------|:--------:|:--------------------------------------------|
| `tree/item.py` → `editors/`, `state/`, `validation/` upward imports    |  Medium  | `tree/item.py:6-8,13`                       |
| `tree/item_coercion.py` → `delegates/` upward imports (lazy)           |  Medium  | `tree/item_coercion.py:276,368,475,504,539` |
| `tree/types.py` → `editors/` upward import                             |  Medium  | `tree/types.py:12`                          |
| `hexedit/widget.py` at 1 130 lines                                     |   Low    | `editors/windowed/hexedit/widget.py`        |
| `structure.py` at 774 lines                                            |   Low    | `tree_actions/structure.py`                 |
| `main_window.py` at 637 lines                                          |   Low    | `app/main_window.py`                        |
| `_closed_tabs_stack` deprecated shim                                   |   Low    | `app/main_window.py:356-358`                |
| `_setup_validation_dock` / `_setup_schemas_menu` no-op stubs           |   Low    | `app/main_window.py:200-204`                |
| Underscore-prefixed names re-exported across `tree_actions/`           |   Low    | `tree_actions/selection.py`                 |
| `IoController.save()` catches `Exception` broadly                      |   Low    | `documents/states/io_controller.py:54`      |
| `JsonTreeItem.row()` returns 0 for root (footgun)                      | Very Low | `tree/item.py:73`                           |
| `ValueDelegate.createEditor` raises `ValueError` for OBJECT/ARRAY/NULL | Very Low | `editors/factory.py:232`                    |
| `state.view_state` persists expansion as positional paths              | Very Low | `state/view_state.py`                       |

---

## 7. Test Surface Assessment

| Area                              |           Tests | Coverage Quality |
|:----------------------------------|----------------:|:-----------------|
| Kind-switch coercion              | Dedicated suite | Good             |
| Container preview                 | Dedicated suite | Good             |
| Drag-and-drop (11 suites)         |       Extensive | Excellent        |
| Validation (3 suites + registry)  |            Good | Good             |
| Theme (50+ tests)                 |            Good | Good             |
| Clipboard/YAML                    | Dedicated suite | Good             |
| Tab lifecycle                     | Dedicated suite | Good             |
| **Delegate matrix**               |     **Missing** | **Gap**          |
| **I/O round-trip property tests** |     **Missing** | **Gap**          |
| **Model invariants**              |     **Missing** | **Gap**          |
| **Theme accessibility (WCAG)**    |     **Missing** | **Gap**          |
| **End-to-end MainWindow smoke**   |     **Partial** | **Gap**          |

The test surface is strong for the features added in recent phases (drag-and-drop, validation, file-UX) but has gaps in
foundational areas (delegate round-trips, I/O property tests, model invariants).

---

## 8. Summary of Recommendations

### High Priority

1. **Resolve `tree/` upward imports.** Extract `editors/inline/datetime/regex.py` + `enums.py` into a shared package.
   Move `delegates/formatting/bytes_codec.py` and `color_codec.py` into `tree/` or `codecs/`. Inject secret-name
   matching into `JsonTreeItem`.

2. **Add `make test` target.** Already defined in the Makefile — just needs `pytest-qt` pinned in `requirements.txt`.

3. **Add delegate matrix tests.** `tests/test_value_delegate.py` covering editor type per `JsonType`, `setEditorData`/
   `setModelData` round-trips.

### Medium Priority

4. **Split `tree_actions/structure.py`.** Extract move logic, sort logic, and expand/collapse into separate modules.

5. **Extract file-operation presenter from `MainWindow`.** Move `_confirm_reload_dirty_tab`, `_reload_tab_from_path`,
   `_save_tab` into a `FileOperationsPresenter`.

6. **Narrow `IoController.save()` exception handling.** Catch specific I/O and serialization exceptions; surface
   structured diagnostics.

7. **Add I/O round-trip property tests.** Load → mutate → save → reload equality across all four formats.

### Low Priority

8. **Remove deprecated shims.** `_closed_tabs_stack`, `_MAX_CLOSED_TABS`, `_setup_validation_dock`,
   `_setup_schemas_menu`.

9. **Rename underscore-prefixed cross-module helpers** in `tree_actions/`.

10. **Add `mypy` or protocol-conformance CI check** to verify `JsonTab` implements `Document`.

11. **Fix `JsonTreeItem.row()` to return -1 for root.**

12. **Change `ValueDelegate.createEditor` to return `None`** for OBJECT/ARRAY/NULL instead of raising `ValueError`.

---

## 9. Grade Justification

**Responsibility Segregation: A−**

The codebase demonstrates exceptional segregation discipline. The `documents/` package is a textbook example of the
facade + controllers + states + seams pattern. The `DocumentMutationGateway` is a genuine chokepoint — all mutations
flow through it. The `Document` protocol is narrow and typed. Editor isolation is enforced by CI.

The grade is held back from A by the 11 upward imports from `tree/` to `editors/`, `delegates/`, `state/`, and
`validation/`. These are not circular imports (lazy imports and the one-way dependency prevent that), but they violate
the stated architectural rule that `tree/` is a low-level data package. Resolving these would push the grade to A.

**Overall: A−**

This is a well-above-average codebase with genuine architectural discipline. The segregation refactoring has been
executed thoroughly, the undo system is rigorous, and the editor isolation is enforced by CI. The remaining issues are
mostly about tightening a few dependency inversions and closing test gaps — not about fundamental design problems.
