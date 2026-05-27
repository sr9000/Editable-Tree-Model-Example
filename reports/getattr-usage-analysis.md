# `getattr` usage analysis

## Scope

Repository scan date: 2026-05-27  
Search method: `grep -RIn 'getattr(' --include='*.py'`

- Total call sites: **59**
- Production call sites: **52**
- Test-only call sites: **7**

This report focuses on **relations between modules, objects, and classes at each `getattr` boundary**:

- **where** the lookup happens,
- **why** the code chose `getattr` instead of direct attribute access,
- **what object/class is expected** on the receiving side,
- **what purpose** the lookup serves.

---

## Executive summary

### Main finding
`getattr` is used here mostly as a **defensive capability probe**, not as heavy metaprogramming.

The dominant patterns are:

1. **Platform / version compatibility**
   - probing optional runtime attributes from PyInstaller, Qt, `zoneinfo`, and `importlib.resources`.
2. **Loose coupling around `JsonTab`**
   - helper modules in `tree_actions/`, `documents/`, `undo/`, and `state/` treat a tab as a **capability carrier** (status callback, search box, icon provider, MRU store, move bookkeeping) instead of requiring a rigid interface.
3. **Adapter-style normalization of third-party objects**
   - `validation/validator.py` reads whatever fields are available on validation errors emitted by `jsonschema` or compatible engines.
4. **Heterogeneous tree walking**
   - `state/affix_mru.py` walks `NumberAffix`, `JsonTreeItem`, `dict`, and `list` values using duck typing.
5. **Reflective dispatch by name**
   - a few spots construct attribute names dynamically to reduce repetitive code, especially for Qt signals/slots.

### Architectural interpretation
The repository uses `getattr` as a **seam-preserving tool** in places where code intentionally crosses module boundaries without introducing formal interfaces:

- `tree_actions/*` ↔ `documents.tab.JsonTab`
- `documents/tab_setup.py` ↔ delegate edit context consumers
- `app/font_controller.py` ↔ any font-aware subscriber
- `validation/validator.py` ↔ third-party validation error objects
- `documents/tab_validation.py` ↔ monkeypatchable module-global registry

So the recurring theme is **capability-based integration** rather than “any random dynamic lookup”.

---

## High-level object/class map

## 1. `JsonTab` is the primary `getattr` target

Most production `getattr` usage is centered on objects that are expected to be a real `documents.tab.JsonTab` or a **tab-like object exposing a subset of `JsonTab` behavior**.

Common optional capabilities read from a tab-like object:

- `file_path`
- `_font_pt`
- `view`
- `_status_message_callback`
- `_icon_provider`
- `affix_mru`
- `search_edit`
- `_apply_filter`
- `edit_name_or_value_from_enter`
- `_last_move_placed`
- `validationChanged` / `schemaChanged`

This tells us `JsonTab` acts as a **hub object** shared across UI, actions, undo, validation, and persistence layers.

## 2. External/runtime objects are the second major target

These are probed for optional features that differ by runtime:

- `sys._MEIPASS` → PyInstaller-frozen app layout
- `Traversable.__fspath__()` → `importlib.resources` path extraction
- `dt.tzinfo.key` / `dt.tzinfo.zone` → timezone naming differences
- `QStyleHints.setColorScheme()` → Qt-version/platform support

## 3. Validation error objects are treated as foreign objects

`validation/validator.py` assumes only that the error object is **ValidationError-like** and may expose any subset of:

- `kind`
- `validator`
- `keyword`
- `rule`
- `context`
- `schema_path`
- `path`
- `instance_path`
- `message`

That module is explicitly acting as an **adapter boundary**.

---

## Grouped usages by use case and scenario

## A. Platform, packaging, and version compatibility probes

### Scenario A1 — Frozen-vs-source filesystem layout

| Where | Object probed | Expected class/object | Why `getattr` | Purpose |
|---|---|---|---|---|
| `main.py:17` | `sys._MEIPASS` | Python `sys` module, optionally augmented by PyInstaller | `_MEIPASS` only exists in frozen builds | Resolve bundled app icon path correctly in source checkout and PyInstaller bundle |
| `themes/registry.py:52` | `sys._MEIPASS` | Python `sys` module, optionally augmented by PyInstaller | Same reason | Find bundled `themes/builtin` directory inside frozen package |

**Relation:** application startup / theme discovery code depends on Python runtime packaging state, but does not want to crash in normal source mode.

### Scenario A2 — Resource object may or may not expose filesystem semantics

| Where | Object probed | Expected class/object | Why `getattr` | Purpose |
|---|---|---|---|---|
| `themes/registry.py:64` | `traversable.__fspath__` | `importlib.resources` `Traversable`-like object | Not every traversable is path-backed | Convert built-in theme resources into a real `Path` only when supported |

**Expected target:** an object returned by `importlib.resources.files("themes.builtin")`.

### Scenario A3 — Timezone objects vary across providers

| Where | Object probed | Expected class/object | Why `getattr` | Purpose |
|---|---|---|---|---|
| `qt2py/__init__.py:11` | `dt.tzinfo.key`, `dt.tzinfo.zone` | `zoneinfo.ZoneInfo`, pytz-like tzinfo, or other tz-aware `datetime.tzinfo` implementations | Different timezone libraries expose the timezone name under different attributes | Preserve a named timezone when converting Python `datetime` into `QDateTime` |

**Expected targets:** most likely `zoneinfo.ZoneInfo` (`key`) and older pytz-style timezones (`zone`).

### Scenario A4 — Qt API is version/platform dependent

| Where | Object probed | Expected class/object | Why `getattr` | Purpose |
|---|---|---|---|---|
| `app/theme_controller.py:183` | `style_hints.setColorScheme` | `QStyleHints` from `QGuiApplication.styleHints()` | Some Qt builds expose `setColorScheme`, others do not | Synchronize Qt application color scheme with the selected theme only when the API exists |
| `tests/test_app_color_scheme.py:29,51,76,99,134` | same | same | tests mirror runtime feature detection | Skip or restore safely on Qt versions lacking the setter |
| `tests/test_theme_switching.py:24,173` | same | same | same | Same compatibility guard in theme-related tests |

**Relation:** `ThemeController` manages app-wide theme state, but the final Qt color-scheme handshake is optional and negotiated at runtime.

---

## B. `JsonTab` as a capability carrier across modules

This is the largest cluster in the repository.

### Scenario B1 — View-state persistence tolerates tab-like hosts

| Where | Object probed | Expected class/object | Why `getattr` | Purpose |
|---|---|---|---|---|
| `state/view_state.py:72,94` | `tab.file_path` | Usually `documents.tab.JsonTab` | Avoid failure when state helpers receive a tab without a file path yet | Skip persistence for untitled/unbound tabs |
| `state/view_state.py:84` | `tab._font_pt` | Usually `JsonTab` | `_font_pt` is internal tab state, not a formal interface | Persist current zoom/font size when present, else fall back to widget font |

**Why this exists:** `state/view_state.py` is intentionally kept as a generic state helper, not deeply coupled to the full `JsonTab` implementation surface.

### Scenario B2 — `JsonTab` may receive events before full layout is ready

| Where | Object probed | Expected class/object | Why `getattr` | Purpose |
|---|---|---|---|---|
| `documents/tab.py:135` | `self.view` | `JsonTab` itself | Defensive during early lifecycle / partially initialized state | Only special-case key handling when the tab already owns a tree view |
| `documents/tab.py:485` | `self._font_pt` | `JsonTab` | Defensive read of internal state | Ensure a valid point size exists before applying a new regular font |
| `documents/tab.py:615` | `self.type_delegate._interactive` | `JsonTypeDelegate` | Reads a private backchannel without hard-requiring it | Reopen the value editor only after a user-driven type change |

**Important relation:** `JsonTab` reaches into `JsonTypeDelegate`’s private `_interactive` flag, but does so defensively so tests or alternative delegates do not break.

### Scenario B3 — Delegate edit context pulls optional collaborators from the tab

| Where | Object probed | Expected class/object | Why `getattr` | Purpose |
|---|---|---|---|---|
| `documents/tab_setup.py:44` | `self._tab._status_message_callback` | `JsonTab` | Optional host callback | Let delegates report user-facing messages without hard dependency |
| `documents/tab_setup.py:53` | `self._tab._icon_provider` | `JsonTab` | Optional collaboration surface | Allow delegates to resolve type icons through the tab |
| `documents/tab_setup.py:56` | `self._tab.affix_mru` | `JsonTab` | Optional collaboration surface | Provide number-affix MRU choices to editors |

**Purpose of the pattern:** `JsonTabEditContext` bridges delegates to the host tab while keeping `delegates/*` independent from parent-widget crawling.

### Scenario B4 — Tree action modules treat the parent tab as an optional service provider

| Where | Object probed | Expected class/object | Why `getattr` | Purpose |
|---|---|---|---|---|
| `tree_actions/structure.py:217,223` | `tab._status_message_callback` | Usually `JsonTab` returned by `_tab_of(...)` | Status callback is optional | Report partial move / invalid root move feedback |
| `tree_actions/structure.py:337,424` | `tab._last_move_placed` | `JsonTab` after `push_move_rows_anchor()` | Internal bookkeeping may be absent on nonstandard tabs | Restore selection after multi-block move macros |
| `tree_actions/context_menu.py:88` | `tab.edit_name_or_value_from_enter` | `JsonTab` or any ancestor exposing that method | Context menu walks parent chain, so result is only capability-based | Trigger the same edit path used by Enter key handling |
| `tree_actions/context_menu.py:134` | `tab._status_message_callback` | `JsonTab` | Optional callback | Show context-menu feedback in status bar |
| `tree_actions/context_menu.py:143,167` | `tab.search_edit` | `JsonTab` | Search UI may not exist on every host | Detect active filter and access the line edit |
| `tree_actions/context_menu.py:173` | `tab._apply_filter` | `JsonTab` | Private helper, not formal interface | Re-run filtering after clearing search text |
| `tree_actions/dnd.py:89` | `tab._status_message_callback` | `JsonTab` from drag source view parent | Optional callback | Announce copy/move drop result in status bar |

**Relation:** `tree_actions/*` modules are intentionally reusable helpers that only assume the surrounding host provides a few capabilities. They are coupled to `JsonTab` in practice, but not through a strict typed interface.

### Scenario B5 — Undo code reads optional tab services and item metadata

| Where | Object probed | Expected class/object | Why `getattr` | Purpose |
|---|---|---|---|---|
| `undo/commands.py:178` | `self._tab.affix_mru` | Usually `JsonTab` | Undo command can run even if MRU support is absent | After type change to currency/units, seed an empty affix from recent affixes |
| `undo/commands.py:293` | `item.name` | Usually `tree.item.JsonTreeItem` or detached tree item | Fallback for source name recovery without constraining item type | Preserve original row names through move undo/redo |

### Scenario B6 — Headless helper keeps model contract loose

| Where | Object probed | Expected class/object | Why `getattr` | Purpose |
|---|---|---|---|---|
| `model_actions.py:175` | `model.show_root` | Usually `tree.model.JsonTreeModel`, but any compatible model is allowed | Helper should tolerate models that do not expose `show_root` | Decide whether an invalid root index should map to the first visible row before key sorting |

### Scenario B7 — Font controller uses runtime protocol dispatch instead of inheritance

| Where | Object probed | Expected class/object | Why `getattr` | Purpose |
|---|---|---|---|---|
| `app/font_controller.py:194` | `target.apply_font_profile` | `JsonTab` or any `FontProfileAware` subscriber | Capability-based protocol; no common base class required | Prefer high-level font application when available |
| `app/font_controller.py:202` | `target.setFont` | Any `QWidget`-like subscriber | Fallback if no richer protocol is implemented | Apply regular font to generic widgets |
| `app/font_controller.py:205` | `target.font` | Any widget with a `font()` accessor | Optional base-font source | Preserve existing font details while replacing family/point size |

**This is one of the cleanest uses of `getattr` in the repo.** The module explicitly documents the subscriber protocol and uses runtime probing to implement it.

---

## C. Reflective dispatch across known names

### Scenario C1 — Disconnecting Qt signals by generated attribute names

| Where | Object probed | Expected class/object | Why `getattr` | Purpose |
|---|---|---|---|---|
| `app/validation_dock.py:145` | `self._tab.<sig_name>` where `sig_name ∈ {"validationChanged", "schemaChanged"}` | `JsonTab` | Avoid writing duplicated disconnect code for each signal | Disconnect the old tab when the dock switches to another tab |
| `app/validation_dock.py:146` | `self._on_<derived_name>` | `ValidationDock` | Same reflective pairing | Resolve the matching local slot method for the generated signal name |

**Expected classes:**
- sender: `documents.tab.JsonTab`
- receiver: `app.validation_dock.ValidationDock`

**Why it matters:** this is not open-ended dynamic behavior; it is **bounded reflection over a closed set of signal names**.

### Scenario C2 — Late-bound module-global collaborator for test seams

| Where | Object probed | Expected class/object | Why `getattr` | Purpose |
|---|---|---|---|---|
| `documents/tab_validation.py:37` | `documents.tab.schema_registry` | The imported `documents.tab` module | Allow module-level override / monkeypatch | Use a custom registry when tests or callers replace the module-global binding |

**Relation:** `TabValidationController` depends on schema-registry services, but deliberately resolves them through the `documents.tab` module to keep old monkeypatch-style tests viable.

---

## D. Heterogeneous object traversal and configuration probing

### Scenario D1 — Optional settings constant

| Where | Object probed | Expected class/object | Why `getattr` | Purpose |
|---|---|---|---|---|
| `state/affix_mru.py:12` | `settings.NUMBER_AFFIX_MRU_SIZE` | `settings` module | The constant may be absent in older configs | Default the MRU size to `50` if the setting is not defined |

### Scenario D2 — Walking mixed tree/data structures by shape

| Where | Object probed | Expected class/object | Why `getattr` | Purpose |
|---|---|---|---|---|
| `state/affix_mru.py:40,41` | `node.value` | Typically `tree.item.JsonTreeItem` | `bootstrap_from_tree()` accepts more than one node shape | Extract `NumberAffix` values stored inside tree items |
| `state/affix_mru.py:44` | `node.child_items` | Typically `JsonTreeItem` | Same | Recurse through model-backed tree nodes |

**Accepted inputs for `bootstrap_from_tree(root)`**

- `NumberAffix`
- `JsonTreeItem`
- plain `dict`
- plain `list`

**Purpose:** bootstrap MRU affixes from either in-memory raw data or an already-built tree model.

---

## E. Validation-error adaptation boundary

`validation/validator.py` contains the most concentrated use of `getattr` in production code. It is adapting **foreign error objects** into the app’s own `ValidationIssue` model.

### Scenario E1 — Normalize error kind across engines/shapes

| Where | Object probed | Expected class/object | Why `getattr` | Purpose |
|---|---|---|---|---|
| `validation/validator.py:119` | `err.kind`, `err.validator`, `err.keyword`, `err.rule` | Mostly `jsonschema.exceptions.ValidationError` or compatible error objects | Different validators expose the error category under different attribute names | Produce one stable internal `kind` string |

### Scenario E2 — Handle combinator errors (`oneOf` / `anyOf`) generically

| Where | Object probed | Expected class/object | Why `getattr` | Purpose |
|---|---|---|---|---|
| `validation/validator.py:134` | `err.validator`, `err.context` | Validation error object | Not all errors are combinators or expose context | Detect branching schema errors |
| `validation/validator.py:144` | `err.schema_path` | Validation error object | Path may be absent or engine-specific | Determine which branch inside `oneOf`/`anyOf` produced a sub-error |
| `validation/validator.py:192,193` | `err.path`, `err.schema_path` | Validation error object | Same | Score error specificity by instance depth and schema depth |
| `validation/validator.py:231,232` | `err.path`, `err.schema_path` | Validation error object | Same | Rebuild absolute paths when unwrapping nested combinator errors |

### Scenario E3 — Convert unknown error shape into internal `ValidationIssue`

| Where | Object probed | Expected class/object | Why `getattr` | Purpose |
|---|---|---|---|---|
| `validation/validator.py:242,244` | `err.instance_path` then `err.path` | Validation error object | Different libraries use different names for the instance location | Build normalized `instance_path` |
| `validation/validator.py:246` | `err.message` | Validation error object | Message may not exist; object itself may still stringify well | Build user-visible issue text |
| `validation/validator.py:248` | `err.schema_path` | Validation error object | Optional path contract | Resolve schema path into app-level issue coordinates |

**Expected classes:** primarily `jsonschema.exceptions.ValidationError`, but the code intentionally allows any object with a similar attribute set.

**Purpose of the whole cluster:** convert unstable third-party object APIs into stable app-owned `ValidationIssue` records.

---

## F. Schema reference compatibility probes

### Scenario F1 — `SchemaRef`-like objects may or may not carry URL information

| Where | Object probed | Expected class/object | Why `getattr` | Purpose |
|---|---|---|---|---|
| `app/validation_dock.py:189` | `ref.url` | Usually `validation.schema_source.SchemaRef` | Keeps compatibility with ref-like objects that may lack `url` | Decide whether reload/open actions should be enabled for URL-backed schemas |
| `app/validation_dock.py:226` | `self._tab.schema_ref.url` | Usually `SchemaRef` on a `JsonTab` | Same | Enable “Go to schema rule” / schema actions when a schema comes from URL instead of file |

**Note:** current `SchemaRef` does define `url`, but the dock still probes defensively. That implies this code is protecting either older object shapes, alternate test doubles, or future ref-like substitutions.

---

## Dominant relations by subsystem

## `tree_actions/*` → `documents.tab.JsonTab`

`tree_actions/structure.py`, `tree_actions/context_menu.py`, and `tree_actions/dnd.py` all use `getattr` to treat the tab as an **optional service provider**.

Services consumed:

- user status reporting (`_status_message_callback`)
- edit entry point (`edit_name_or_value_from_enter`)
- filtering UI (`search_edit`, `_apply_filter`)
- move bookkeeping (`_last_move_placed`)

**Why:** the action modules want to remain callable from a view-centric context without importing a hard tab interface everywhere.

## `documents/*` ↔ delegates / controllers

- `documents/tab_setup.py` exposes tab services to delegates via `JsonTabEditContext`
- `documents/tab_validation.py` late-binds `schema_registry`
- `documents/tab.py` safely reads optional/private state during lifecycle-sensitive UI code

**Why:** document code is in the middle of a staged refactor toward controller objects and narrow seams. `getattr` preserves those seams while internal ownership moves between components.

## `app/*` → generic Qt or app-owned collaborators

- `app/font_controller.py` dispatches by protocol (`apply_font_profile`, `setFont`, `font`)
- `app/theme_controller.py` probes Qt API availability
- `app/validation_dock.py` uses bounded reflection for signal names and schema-ref compatibility

**Why:** the app layer integrates many heterogeneous Qt objects and values from multiple modules.

## `validation/*` → third-party error objects

`validation/validator.py` is intentionally tolerant of multiple validation error shapes.

**Why:** the application wants a stable internal issue model even if the validator backend or error API changes.

---

## Risk / maintenance notes

### Good `getattr` uses in this repo

These usages are intentional and well-justified:

- runtime feature detection for Qt / PyInstaller / timezone implementations
- protocol-style dispatch in `app/font_controller.py`
- validation-error normalization in `validation/validator.py`
- bounded reflection over a closed signal-name set in `app/validation_dock.py`

### More fragile `getattr` uses

These depend on private or implicit contracts:

- `JsonTab` private collaborators such as `_status_message_callback`, `_icon_provider`, `_last_move_placed`, `_apply_filter`
- `JsonTypeDelegate._interactive`
- `JsonTab._font_pt`

These are not necessarily wrong, but they mean some cross-module contracts are **convention-based rather than interface-based**.

### Strongest architectural pattern revealed

The repository uses `getattr` mostly to support **soft interfaces** during refactoring and between UI layers. The code usually knows which concrete class it expects, but it intentionally checks capabilities rather than importing a formal interface or risking lifecycle/version breakage.

---

## Condensed inventory by scenario

| Group | Call sites |
|---|---:|
| Platform / packaging / Qt compatibility | 13 |
| `JsonTab` capability carrier / loose UI seams | 25 |
| Reflective dispatch / late binding | 3 |
| Heterogeneous traversal / config probing | 4 |
| Validation-error adaptation | 12 |
| SchemaRef compatibility | 2 |
| **Total** | **59** |

> The largest single theme is **loose coupling around `JsonTab`**.

---

## Bottom line

If you read this repository through the lens of `getattr`, the most important relationship is:

**`JsonTab` is the central object whose optional capabilities are consumed by many helper modules.**

The rest of the `getattr` usage falls into three secondary roles:

1. **runtime compatibility** (`sys`, Qt, timezone/resource objects),
2. **adaptation of foreign object models** (`ValidationError`-like errors),
3. **bounded reflection for convenience** (signal names, swappable module globals).

So `getattr` here is not primarily “dynamic programming for its own sake”; it is being used to keep subsystem boundaries flexible while preserving behavior across runtime variations, staged refactors, and test seams.
