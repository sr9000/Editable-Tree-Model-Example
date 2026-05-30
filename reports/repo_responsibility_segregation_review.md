# Repo responsibility segregation review

**Date:** 2026-05-30
**Scope reviewed:** `app/`, `documents/`, `delegates/`, `state/`, `themes/`, `tree/`, `tree_actions/`, `undo/`, `validation/`

---

## 1. Executive summary

The current repository is **much healthier than the old `JsonTab` god-object phase**, but your bird's-eye discomfort is still justified.

The main remaining problem is no longer a single mega-class. It is **boundary ambiguity between packages**:

- `MainWindow` is still a large orchestration bucket.
- `app/` is not a clean bounded context; it is a mix of shell, menu wiring, persistence-facing presenters, and cross-tab services.
- `delegates/` mixes three concepts: Qt delegates, editor widgets/dialog launchers, and value formatting/codec helpers.
- `state/` mixes **persistent preferences** (`QSettings`) with **runtime/session state** (`AffixMRU`).
- theme behavior is partly clear in code, but the **user-visible contract is not explicit**.
- `tree/` still combines domain rules and Qt model concerns too tightly.
- `validation/` works, but its layers are still implementation-shaped rather than domain-shaped.
- `tree_actions/`, `undo/`, and `documents/` are decoupled from the old `data_store`, but they are still coupled through a fairly fat `Document`/tab surface.

So the diagnosis is:

> **The repo is no longer a monolith, but it is still not partitioned into crisp bounded contexts.**

---

## 2. Verified facts from the current tree

A few concrete observations from the current sources:

- `app/main_window.py` is still **637 LOC**.
- `app/theme_controller.py` is **373 LOC**.
- `app/validation_presenter.py` is **305 LOC**.
- `app/tab_lifecycle.py` is **206 LOC**.
- `tree/model.py` is **463 LOC** and imports DnD/clipboard logic from `tree_actions/*` lazily.
- `tree/item.py` is **347 LOC** and owns both domain invariants and coercion-triggered behavior.
- `tree_actions/structure.py` is **628 LOC**.
- `undo/commands.py` is **465 LOC**.
- `documents/tab.py` is down to **233 LOC**, so the old god-object has genuinely shrunk.
- `documents/states/editing_controller.py` is also slimmed to **199 LOC**, but command construction lives in `documents/states/editing/command_dispatcher.py` (**356 LOC**), so the complexity mostly moved sideways.
- tests still import the concrete `JsonTab` directly in many places, and some tests still import undo command classes via `documents.tab` re-exports.

These metrics support the architectural feeling you described: the problem is now **distribution of responsibility**, not only raw line count.

---

## 3. Assessment by concern

### 3.1 `MainWindow` still feels like a trashcan

**Verdict: correct.**

Even after earlier extractions, `MainWindow` still owns too many kinds of policy:

- window geometry/session restore
- file open/save/reload
- drag-and-drop open
- tab orchestration glue
- theme menu plumbing
- font actions
- status bar messaging
- validation dock integration
- action enable/disable routing
- shutdown persistence

That means `MainWindow` is still both:

1. a **Qt widget**, and
2. an **application service locator / workflow coordinator**.

Those should be separate.

### 3.2 `app/` is a duct-taped collection

**Verdict: also correct.**

`app/` currently mixes:

- shell widgets (`main_window.py`)
- presenters (`validation_presenter.py`, `tab_lifecycle.py`)
- user preference controllers (`font_controller.py`, `theme_controller.py`, `app_settings.py`)
- registry-like services (`schema_tab_pool.py`, `recent_files.py`)
- wiring helpers (`main_window_actions.py`)

This is not a domain package; it is a **miscellaneous composition layer**.

### 3.3 `delegates/` is conceptually muddy

**Verdict: yes.**

Today the package contains:

- actual item delegates: `name_delegate.py`, `type_delegate.py`, `value.py`
- editor factory / editor wiring: `editor_factory.py`
- editor-specific helpers: `number_affix_delegate.py`
- data codecs/formatters: `bytes_codec.py`, `color_codec.py`, `value_formatting.py`
- presentation helper: `validation_badge.py`
- cross-cutting protocol/context: `edit_context.py`

So `delegates/` is really **editing UI infrastructure**, not just delegates.

The naming problem matters because it hides an important design distinction:

- **delegates** decide how a cell is painted and edited,
- **editors** are concrete widgets/dialogs used during editing,
- **formatters/codecs** are pure transformation helpers.

Those are different responsibilities and should not live in one flat package.

### 3.4 `state/` mixes persistent settings and runtime/session state

**Verdict: strongly correct.**

Current `state/` contains mostly `QSettings` wrappers:

- `clipboard_settings.py`
- `edit_limits.py`
- `recent_schemas.py`
- `secret_settings.py`
- `theme_settings.py`
- `validation_settings.py`
- `view_state.py`

but it also contains `affix_mru.py`, which is **in-memory runtime/session state**, not persistent preference state.

That package would be much clearer if split into:

- **persistent preferences** / `QSettings` adapters
- **workspace/session state**

### 3.5 theme source semantics are unclear

**Verdict: your suspicion is right; the behavior is narrower than the UI wording suggests.**

What the current code actually persists in `state/theme_settings.py` is:

- follow-system flag
- preferred light theme name
- preferred dark theme name
- manual theme name
- watch-user-dir flag

What it does **not** persist is any arbitrary “user-picked theme folder path”.

`ThemeRegistry` loads:

1. built-in themes, and
2. a fixed app-config user directory (`QStandardPaths.AppConfigLocation / "themes"`).

So the current contract is:

- "Reload themes" reloads built-ins plus that fixed user directory.
- "Watch user theme folder" watches only that fixed user directory and its YAML files.
- there is no generic "remember whichever folder the user once browsed" behavior.

That is defensible, but it needs to be explicit in naming and docs.

### 3.6 `tree/` is still organically grown around functions

**Verdict: yes, though this is a medium-term redesign, not a quick cleanup.**

`tree/item.py` owns:

- tree structure
- name rules
- type coercion hooks
- secret-name promotion
- datetime conversion behavior
- container morphing rules
- editability derivation

`tree/model.py` owns:

- Qt model adapter logic
- drag-and-drop plumbing
- MIME responsibilities
- validation badge lookup hooks
- read-only policy
- row move/sort/type-change behavior

That means the boundary between:

- **tree domain**, and
- **Qt presentation/model adapter**

is still weak.

The biggest design smell here is that the domain object (`JsonTreeItem`) is not a small, crisp node abstraction; it is a node + coercion gateway + edit policy holder.

### 3.7 validation survived the migration but is not yet well-shaped

**Verdict: fair.**

The current validation package has usable pieces:

- engine wrapper
- issue/index objects
- schema registry
- source loading
- error adaptation
- validator

But it still feels implementation-led:

- some modules are transport/adapter shaped (`error_adapter.py`, `_engine.py`)
- some are UI-support shaped (`index.py`)
- registry is global singleton based (`schema_registry = SchemaRegistry()`)
- app presentation still reaches directly into validation operations

It works, but the package boundary is not telling a clear story like:

- schema source management
- schema compilation/cache
- validation execution
- issue mapping/navigation
- validation UI presentation

### 3.8 `tree_actions/` and `undo/` are still tightly coupled with `documents/`

**Verdict: yes, but the coupling has changed form.**

The good news:

- they no longer leak through `data_store.*`
- they often use `Document`/marker seams instead of importing the concrete tab directly

The bad news:

- `tree_actions` still depends on owning-tab lookup and then calls into tab mutation/view services
- `undo/commands.py` still assumes a tab-like object with model, mutations, editing, affix MRU, and view controller
- `documents.mutation_gateway.DocumentMutationGateway` is still largely a forwarding facade onto `tab.editing.*`

So the coupling is now **typed and more honest**, but still strong.

### 3.9 `documents/` is still a mini-universe

**Verdict: still true.**

It is much healthier than before, but it remains the package where too many cross-cutting seams meet:

- tab widget construction
- controllers
- document protocol
- view controller
- mutation gateway
- IO controller
- appearance/editability/navigation/history
- test-facing compatibility surface

The clearest sign is the continued need for compatibility re-exports from `documents/tab.py`, especially undo command class re-exports for tests.

That means `documents/` is still acting as both:

- the runtime composition root for a tab, and
- a public namespace of convenience aliases.

### 3.10 `EditingController` still aliases other collaborators

**Verdict: yes, this is the right instinct.**

The current `EditingController` is much smaller, but it still mostly forwards to:

- `InlineEditController`
- `MoveViewState`
- `CommandDispatcher`
- `DiffApplier`

That is better than a 700-line class, but it means the name `EditingController` still covers several distinct sub-capabilities while also acting as a façade.

If it remains, it should become a **narrow coordinator with explicit sub-services** rather than a bucket of forwarded methods.

---

## 4. The main structural issue underneath all of this

The repo is still organized mostly by **historical implementation units**, not by **stable architectural boundaries**.

Right now the practical top-level boundaries are roughly:

- Qt shell/window concerns
- document/tab lifecycle
- tree domain
- editing UI
- validation
- preferences/session
- actions/undo
- themes/appearance

But the source tree does not make those boundaries explicit enough.

That is why the code can be locally improved while still feeling globally muddy.

---

## 5. Recommended target architecture

I would not do a giant rename storm. I would move toward a clearer package map in stages.

### 5.1 Shell / workbench

Suggested role: everything about the main application frame and cross-tab orchestration.

Possible target shape:

```text
app/
  shell/
    main_window.py          # thin QWidget only
    actions.py              # QAction creation + enable rules
    menus.py                # menu assembly
    dragdrop.py             # window-level file drop/open behavior
  workbench/
    tab_lifecycle.py
    recent_files.py
    schema_tabs.py
    status_bus.py
```

Goal:

- `MainWindow` becomes a thin view.
- workbench services own workflows.
- menu/action creation is not mixed with persistence and tab logic.

### 5.2 Editing UI

Rename or split `delegates/` into an editing-oriented package.

Possible target shape:

```text
editing_ui/
  delegates/
    name_delegate.py
    type_delegate.py
    value_delegate.py
  editors/
    factory.py
    secret_line_edit.py
    affix_editor.py
    dialogs.py
  formatting/
    value_formatting.py
    bytes_codec.py
    color_codec.py
  context.py
  badges.py
```

Goal:

- the term *delegate* regains meaning
- editors become explicit widgets/tools
- codecs/formatters become obviously pure helpers

### 5.3 Preferences vs session state

Split `state/` into two packages.

Possible target shape:

```text
preferences/
  clipboard.py
  edit_limits.py
  secrets.py
  themes.py
  validation.py
  view_state.py
  recent_schemas.py

session/
  affix_mru.py
  closed_tabs.py           # if promoted later
  transient_selection.py   # if needed later
```

Goal:

- `QSettings` wrappers stop being mixed with ephemeral runtime structures
- naming makes persistence intent obvious

### 5.4 Themes -> appearance

Current code already has good pieces, but the contract is scattered between `themes/`, `state/theme_settings.py`, and `app/theme_controller.py`.

Suggested target shape:

```text
appearance/
  themes/
    registry.py
    loader.py
    spec.py
    export.py
    builtin/
  settings.py
  controller.py
  icon_provider.py
```

Most important semantic rule to codify:

> Theme reload operates on built-ins plus the fixed user theme directory; there is no arbitrary remembered theme-folder path.

If you later want arbitrary directories, make that a first-class feature (`additional_theme_dirs`) rather than an implicit side effect.

### 5.5 Tree domain split: domain vs Qt adapter

This is the highest-value deep cleanup.

Suggested target shape:

```text
tree/
  domain/
    node.py
    naming.py
    typing.py
    coercion.py
    edit_rules.py
  qt/
    model.py
    roles.py
    view.py
    mime.py
```

Key rule:

- `domain/node.py` should know nothing about Qt.
- `qt/model.py` should adapt domain nodes to `QAbstractItemModel`.

That would let the tree design become intentional instead of accreted around convenience methods.

### 5.6 Validation split into stable layers

Suggested target shape:

```text
validation/
  engine/
    compile.py
    execute.py
    error_normalization.py
  schemas/
    sources.py
    registry.py
    cache.py
  issues/
    issue.py
    index.py
    mapping.py
  presentation/
    presenter.py
    dock_model.py
```

Goal:

- schema source management is separate from validation execution
- issue mapping/navigation is separate from engine details
- UI presenters stop reaching across the whole validation package

### 5.7 Undo/actions should depend on narrower services than `Document`

Today `Document` is still fairly fat. Long-term, actions/commands should consume smaller interfaces.

Suggested seam split:

- `MutationPort` — push rename/edit/type/insert/remove/move/sort/switch-case
- `ViewportPort` — select/expand/scroll/path lookup
- `TreeReadPort` — get item/index/path/root snapshot
- `HistoryPort` — undo stack + macro registration

Then:

- `tree_actions` depends mainly on `MutationPort + ViewportPort`
- `undo` depends mainly on `TreeReadPort + ViewportPort + HistoryPort`
- `documents` becomes composition, not the universal dependency hub

---

## 6. Concrete staged roadmap

### Phase A — make `MainWindow` boring

Target: `MainWindow` becomes a thin shell widget.

Move out of `app/main_window.py`:

- file open/save/reload workflows
- tab create/close/reopen workflows
- menu/action construction
- drag-and-drop open behavior
- window geometry persistence
- validation-dock wiring

Keep only:

- generated UI ownership
- current tab getters
- close event forwarding
- very thin delegations to workbench services

### Phase B — split `app/` into shell vs workbench vs preferences-facing services

This is mostly package surgery and naming.

Do not add new behavior first; just clarify the boundaries.

### Phase C — replace `delegates/` with `editing_ui/` layout

This will improve readability immediately, even before internal behavior changes.

The biggest conceptual win is separating:

- delegate classes
- editor widgets/dialog launchers
- pure value codecs/formatters

### Phase D — split `state/` into `preferences/` and `session/`

Low risk, high clarity.

This also gives you a clean place for future non-persistent per-workbench caches without hiding them under `state/`.

### Phase E — formalize theme source semantics

Add one small design document and rename the relevant actions/settings to match reality.

Example of the rule to state explicitly:

- "Open themes folder..." opens the fixed user theme directory
- "Reload themes" reloads built-ins + that directory
- "Watch user theme folder" watches only that directory

If you keep that rule, the UX becomes understandable.

### Phase F — tree redesign in two layers

This is the most invasive phase and should be done after the app/package cleanup.

Steps:

1. define a pure domain node API
2. move naming/coercion/editability rules out of the node where possible
3. leave `QAbstractItemModel` adaptation in a Qt-only layer
4. move MIME/DnD helpers away from the model if possible

### Phase G — validation package redesign

Start by deciding the stable nouns:

- schema source
- schema entry/cache
- validation session/run
- issue mapping
- issue navigation/presentation

Then move modules under those nouns.

### Phase H — reduce `documents/` to composition + document-facing API

Main goals:

- remove test-only re-export pressure from `documents/tab.py`
- stop using `documents` as the public convenience namespace for unrelated things
- reduce `Document` into smaller ports where possible
- make `EditingController` expose collaborators explicitly, or disappear behind clearer services

---

## 7. Prioritization: what to do first

If the goal is **biggest clarity gain for the least churn**, I would do this order:

1. **split `state/` into persistent vs session**
2. **split `delegates/` into delegate/editor/formatting areas**
3. **make theme source/reload semantics explicit**
4. **thin `MainWindow` into shell + workbench services**
5. **shrink `documents/` public role and test re-exports**
6. **split tree domain from Qt adapter**
7. **reshape validation package**
8. **reduce action/undo dependence on the fat `Document` seam**

This order improves architecture visibility early without starting with the riskiest rewrites.

---

## 8. Recommended principles for the next refactor pass

1. **Package by responsibility, not by historical extraction step.**
2. **Prefer narrow service interfaces over one big `Document` façade.**
3. **Separate pure logic from Qt adapter code aggressively.**
4. **Do not hide runtime/session state under a generic `state/` label.**
5. **If a module name is overloaded (`delegates`, `state`, `app`), rename the boundary before adding more code there.**
6. **Kill compatibility re-exports as soon as tests can be migrated.**
7. **Document user-visible persistence rules explicitly** (themes, recent schemas, view state, warning limits).

---

## 9. Bottom line

Your discomfort is well grounded.

The repo has already solved the first-order problem (**single god-object design**), but it has not yet solved the second-order problem (**clear architectural ownership by package**).

The next step should not be another local extraction spree. It should be a **boundary clarification pass** across packages:

- shell/workbench
- editing UI
- preferences/session
- appearance/themes
- tree domain vs Qt adapter
- validation layers
- narrow action/undo ports

That is the level at which the codebase will start to feel designed rather than historically evolved.
