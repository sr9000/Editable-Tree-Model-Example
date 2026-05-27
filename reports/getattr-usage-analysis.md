# `getattr` / `hasattr` boundary analysis

## Scope

Repository scan date: 2026-05-27

Commands used:

```bash
grep -RIn --exclude-dir=.venv --include='*.py' 'getattr(' .
grep -Irn --exclude-dir=.venv --exclude-dir=tests -E "hasattr" .
```

Normalized counts used in this report:

- `getattr(...)`: **52** production Python expressions in **17** files
- `hasattr(...)`: **43** production Python expressions in **14** files
- Combined dynamic boundary probes: **95** production Python expressions across **23** files
- Test-only `getattr(...)`: **7** expressions

Notes:

- The raw `hasattr` grep requested by the user is **report-sensitive** because it searches the whole workspace except
  `.venv` and `tests`, so it also matches Markdown reports; the boundary analysis below normalizes to production Python
  code.
- The raw `getattr` grep line count is lower than the exact expression count because a few lines contain more than one
  `getattr(...)` call.

This report now covers both mechanisms because they work together:

- `hasattr(...)` usually answers **“is this capability present?”**
- `getattr(...)` usually answers **“read or call the capability if present”**

So the full picture of boundary crossing is not visible from `getattr` alone.

---

## Executive summary

### Main finding

This repository uses `getattr` and `hasattr` mainly for **capability-based boundary crossing**.

The dominant pattern is:

1. **Probe a foreign object for a capability** with `hasattr`
2. **Consume that capability defensively** with `getattr`
3. **Avoid hard interface coupling** across modules, runtime versions, or Qt/Python implementation differences

### Reevaluated architectural picture

After adding `hasattr`, the previous `getattr`-only picture becomes clearer:

- `JsonTab` is still the main dynamic target, but now it is obvious that several action modules first **discover** a tab
  by checking for methods like `push_insert_rows`, `push_move_rows`, or `edit_name_or_value_from_enter`, then later *
  *consume** other tab-owned attributes and collaborators via `getattr`.
- `model_actions.py` is a second major boundary: it treats the model as a **model-like protocol**, not strictly as
  `tree.model.JsonTreeModel`.
- `delegates/editor_factory.py` and `app/font_controller.py` together show a reusable **protocol-dispatch style**:
  objects are accepted based on capabilities (`items`, `push`, `for_key`, `apply_font_profile`, `setFont`, `font`)
  rather than inheritance.
- `validation/validator.py` remains the strongest **foreign-object adapter boundary**, but now it stands out as mostly a
  `getattr`-only consumer because the code assumes ValidationError-like objects and normalizes them directly.
- `jsontream/__init__.py` adds a whole separate kind of boundary crossing: **data protocol detection** (`__iter__`,
  `__len__`, `__next__`) rather than app object collaboration.

### Core interpretation

`hasattr` in this codebase is generally used as the **gate** and `getattr` as the **payload reader**.

That means the repository’s dynamic behavior is mostly about:

- **soft interfaces between internal subsystems**,
- **runtime/API compatibility across Qt/PyInstaller/Python objects**,
- **duck-typed protocol support for heterogeneous objects**.

---

## High-level target map

## 1. `JsonTab` / tab-like hosts are the main dynamic boundary target

Expected concrete class most of the time:

- `documents.tab.JsonTab`

But many modules only require a subset of capabilities, such as:

- `push_insert_rows`
- `push_move_rows`
- `edit_name_or_value_from_enter`
- `commit_set_data`
- `_status_message_callback`
- `search_edit`
- `_apply_filter`
- `affix_mru`
- `_icon_provider`
- `file_path`
- `_font_pt`
- `_set_font_pt`
- `_user_sized_columns`
- `validationChanged` / `schemaChanged`
- `_last_move_placed`

This is the single most important cross-boundary object in the repository.

## 2. Model-like objects are the second internal protocol target

Expected concrete class most of the time:

- `tree.model.JsonTreeModel`

Capabilities probed dynamically:

- `get_item`
- `move_row`
- `root_item`
- `sort_keys`
- `show_root`

This boundary is concentrated in `model_actions.py`, which behaves like a compatibility/helper layer for headless or
reduced model implementations.

## 3. Runtime / Qt / Python implementation objects are major external targets

Common targets:

- `sys._MEIPASS`
- `QStyleHints.colorScheme`, `QStyleHints.setColorScheme`, `QStyleHints.colorSchemeChanged`
- `QPalette.ColorRole.Accent`
- `datetime.tzinfo.key`, `datetime.tzinfo.zone`
- `Traversable.__fspath__`
- `QByteArray.data`

These are all runtime-dependent capability probes.

## 4. Protocol objects and adapters form another cluster

Common targets:

- `AffixMRU`-like objects: `items`, `push`
- icon-provider-like objects: `for_key`
- font-aware targets: `apply_font_profile`, `setFont`, `font`
- mime-like objects: `text`
- iterator/generator-like objects: `__iter__`, `__len__`, `__next__`
- validation-error-like objects: `kind`, `validator`, `keyword`, `rule`, `context`, `schema_path`, `path`,
  `instance_path`, `message`

This is the broadest “duck typing” zone in the repo.

---

## Cross-boundary scenarios, reevaluated with both `getattr` and `hasattr`

## A. Runtime, packaging, and Qt compatibility

### Scenario A1 — Frozen-vs-source deployment layout

| Mechanism | Where                   | Target         | Expected class/object                                    | Purpose                                                       |
|-----------|-------------------------|----------------|----------------------------------------------------------|---------------------------------------------------------------|
| `getattr` | `main.py:17`            | `sys._MEIPASS` | Python `sys` module, optionally augmented by PyInstaller | Resolve the bundled application icon in frozen vs source runs |
| `getattr` | `themes/registry.py:52` | `sys._MEIPASS` | same                                                     | Find `themes/builtin` under the PyInstaller extraction tree   |

**Why dynamic:** `_MEIPASS` exists only in frozen deployments.

### Scenario A2 — Resource/path compatibility across import loaders

| Mechanism | Where                   | Target                   | Expected class/object                           | Purpose                                                                      |
|-----------|-------------------------|--------------------------|-------------------------------------------------|------------------------------------------------------------------------------|
| `getattr` | `themes/registry.py:64` | `traversable.__fspath__` | `importlib.resources` `Traversable`-like object | Convert packaged resources into a real filesystem `Path` only when supported |

**Why dynamic:** not every `Traversable` is path-backed.

### Scenario A3 — Qt color-scheme APIs vary by build/platform/version

| Mechanism | Where                            | Target                           | Expected class/object | Purpose                                                                      |
|-----------|----------------------------------|----------------------------------|-----------------------|------------------------------------------------------------------------------|
| `hasattr` | `themes/auto.py:11`              | `hints.colorScheme`              | `QStyleHints`         | Read system light/dark preference when available                             |
| `getattr` | `app/theme_controller.py:183`    | `style_hints.setColorScheme`     | `QStyleHints`         | Push the selected theme back into Qt’s app color-scheme state when possible  |
| `hasattr` | `app/theme_controller.py:86,372` | `style_hints.colorSchemeChanged` | `QStyleHints`         | Connect/disconnect follow-system synchronization only when the signal exists |
| `hasattr` | `app/theme_controller.py:174`    | `QPalette.ColorRole.Accent`      | Qt enum namespace     | Apply accent color only on Qt builds that expose that role                   |

**Cross-boundary picture:**

- `themes/auto.py` reads platform/system state from Qt
- `app/theme_controller.py` pushes app state back into Qt
- both rely on runtime feature detection instead of hard assumptions

### Scenario A4 — Timezone provider differences

| Mechanism | Where                  | Target                            | Expected class/object                                                           | Purpose                                                                              |
|-----------|------------------------|-----------------------------------|---------------------------------------------------------------------------------|--------------------------------------------------------------------------------------|
| `getattr` | `qt2py/__init__.py:11` | `dt.tzinfo.key`, `dt.tzinfo.zone` | `zoneinfo.ZoneInfo`, pytz-like tzinfo, or another aware `tzinfo` implementation | Preserve named timezone information when converting Python `datetime` to `QDateTime` |

### Scenario A5 — Qt binding differences for binary buffers

| Mechanism | Where                        | Target      | Expected class/object                                   | Purpose                                                           |
|-----------|------------------------------|-------------|---------------------------------------------------------|-------------------------------------------------------------------|
| `hasattr` | `qhexedit/chunks.py:109,275` | `_qba.data` | `QByteArray`-like object returned by `QIODevice.read()` | Use `.data()` when available, otherwise fall back to `bytes(...)` |

**Why dynamic:** PySide/Python conversion behavior can differ across bindings or versions.

---

## B. `JsonTab` discovery and capability consumption across UI helper modules

This is the largest internal cross-boundary cluster.

### Scenario B1 — Action modules discover a `JsonTab` by method capability

| Mechanism | Where                             | Target                                 | Expected class/object                                   | Purpose                                                                           |
|-----------|-----------------------------------|----------------------------------------|---------------------------------------------------------|-----------------------------------------------------------------------------------|
| `hasattr` | `tree_actions/paste.py:22`        | `parent.push_insert_rows`              | usually `JsonTab`                                       | Recognize a tab host that can route paste operations through undo-aware insertion |
| `hasattr` | `tree_actions/structure.py:25`    | `parent.push_insert_rows`              | usually `JsonTab`                                       | Same discovery pattern for structure actions                                      |
| `hasattr` | `tree_actions/dnd.py:12`          | `parent.push_move_rows`                | usually `JsonTab`                                       | Recognize a tab host that can perform undo-aware move operations                  |
| `hasattr` | `tree_actions/context_menu.py:58` | `cursor.edit_name_or_value_from_enter` | `JsonTab` or ancestor widget exposing the same behavior | Walk parent chain to find the document host                                       |
| `hasattr` | `tree_actions/context_menu.py:60` | `cursor.parent`                        | QObject/widget ancestor                                 | Continue the parent-chain walk safely                                             |

**Important reevaluation:** `hasattr` shows that these modules do not start from “we have a `JsonTab`”. They start from
a `QTreeView` or context widget and dynamically **discover** a tab-like host.

### Scenario B2 — Once found, action modules consume tab-owned services

| Mechanism | Where                                  | Target                              | Expected class/object        | Purpose                                                   |
|-----------|----------------------------------------|-------------------------------------|------------------------------|-----------------------------------------------------------|
| `getattr` | `tree_actions/structure.py:217,223`    | `tab._status_message_callback`      | `JsonTab`                    | Publish user feedback for partial/invalid move operations |
| `getattr` | `tree_actions/structure.py:337,424`    | `tab._last_move_placed`             | `JsonTab`                    | Restore selection after macro-composed multi-block moves  |
| `getattr` | `tree_actions/context_menu.py:88`      | `tab.edit_name_or_value_from_enter` | `JsonTab` or equivalent host | Trigger the same editor-opening path used by Enter        |
| `getattr` | `tree_actions/context_menu.py:134`     | `tab._status_message_callback`      | `JsonTab`                    | Show status messages                                      |
| `getattr` | `tree_actions/context_menu.py:143,167` | `tab.search_edit`                   | `JsonTab`                    | Read/clear the filter UI                                  |
| `getattr` | `tree_actions/context_menu.py:173`     | `tab._apply_filter`                 | `JsonTab`                    | Re-apply filtering after search text changes              |
| `getattr` | `tree_actions/dnd.py:89`               | `tab._status_message_callback`      | `JsonTab`                    | Announce drag-drop results                                |

### Scenario B3 — Context menu write path keeps a fallback host protocol

| Mechanism | Where                              | Target                | Expected class/object                                 | Purpose                                                                         |
|-----------|------------------------------------|-----------------------|-------------------------------------------------------|---------------------------------------------------------------------------------|
| `hasattr` | `tree_actions/context_menu.py:259` | `tab.commit_set_data` | expected `JsonTab`, or at least a commit-capable host | Decide whether to use the document mutation seam or direct `model.setData(...)` |

**Observation:** the method check is for `commit_set_data`, but the implementation actually calls
`tab.mutations.commit_set_data(...)`. That is still a tab boundary check, but it reveals a slightly looser/older
compatibility seam than the current call path.

### Scenario B4 — View-state helpers tolerate tab-like hosts and partial lifecycle state

| Mechanism | Where                       | Target                    | Expected class/object       | Purpose                                                 |
|-----------|-----------------------------|---------------------------|-----------------------------|---------------------------------------------------------|
| `getattr` | `state/view_state.py:72,94` | `tab.file_path`           | usually `JsonTab`           | Persist state only for bound files                      |
| `getattr` | `state/view_state.py:84`    | `tab._font_pt`            | `JsonTab`                   | Persist zoom/font state when available                  |
| `hasattr` | `state/view_state.py:116`   | `tab._set_font_pt`        | `JsonTab` or compatible tab | Restore font size only when the host exposes the setter |
| `hasattr` | `state/view_state.py:126`   | `tab._user_sized_columns` | `JsonTab` or compatible tab | Restore user-resized column tracking when supported     |

### Scenario B5 — `JsonTab` itself uses defensive access around internal/private collaborators

| Mechanism | Where                  | Target                            | Expected class/object                   | Purpose                                                     |
|-----------|------------------------|-----------------------------------|-----------------------------------------|-------------------------------------------------------------|
| `getattr` | `documents/tab.py:135` | `self.view`                       | `JsonTab` during initialization/runtime | Avoid event-filter assumptions before the view exists       |
| `getattr` | `documents/tab.py:485` | `self._font_pt`                   | `JsonTab`                               | Supply a safe point-size fallback                           |
| `getattr` | `documents/tab.py:615` | `self.type_delegate._interactive` | `JsonTypeDelegate`                      | Reopen the value editor only after user-driven type changes |

**Why this matters:** even the tab’s internal collaboration with delegates/lifecycle state is softened by dynamic reads.

---

## C. Delegate, editor, and controller protocol dispatch

### Scenario C1 — Delegates pull optional collaborators from the tab/edit context

| Mechanism | Where                       | Target                               | Expected class/object | Purpose                                                                  |
|-----------|-----------------------------|--------------------------------------|-----------------------|--------------------------------------------------------------------------|
| `getattr` | `documents/tab_setup.py:44` | `self._tab._status_message_callback` | `JsonTab`             | Let delegates report status without coupling themselves to the whole tab |
| `getattr` | `documents/tab_setup.py:53` | `self._tab._icon_provider`           | `JsonTab`             | Provide delegate icon lookup                                             |
| `getattr` | `documents/tab_setup.py:56` | `self._tab.affix_mru`                | `JsonTab`             | Provide number-affix MRU data to editors                                 |

### Scenario C2 — Value editor factory consumes collaborator protocols by shape

| Mechanism | Where                             | Target             | Expected class/object                                                                         | Purpose                                                             |
|-----------|-----------------------------------|--------------------|-----------------------------------------------------------------------------------------------|---------------------------------------------------------------------|
| `hasattr` | `delegates/editor_factory.py:195` | `mru.items`        | usually `state.affix_mru.AffixMRU`                                                            | Read MRU suggestions for affix editors                              |
| `hasattr` | `delegates/editor_factory.py:198` | `provider.for_key` | `themes.icon_provider.FileIconProvider`, `StubIconProvider`, or any icon-provider-like object | Retrieve logical icons such as affix prefix/suffix glyphs           |
| `hasattr` | `delegates/editor_factory.py:434` | `mru.push`         | usually `AffixMRU`                                                                            | Feed edited affixes back into MRU history after a successful commit |

### Scenario C3 — Type delegate treats the host view as only partially known

| Mechanism | Where                            | Target               | Expected class/object                                                   | Purpose                                                     |
|-----------|----------------------------------|----------------------|-------------------------------------------------------------------------|-------------------------------------------------------------|
| `hasattr` | `delegates/type_delegate.py:131` | `host_view.iconSize` | usually `QAbstractItemView`/`QTreeView` from the delegate option widget | Match the combobox icon size to the host view when possible |

### Scenario C4 — Font controller implements a capability-based subscriber protocol

| Mechanism | Where                        | Target                      | Expected class/object                      | Purpose                                                        |
|-----------|------------------------------|-----------------------------|--------------------------------------------|----------------------------------------------------------------|
| `getattr` | `app/font_controller.py:194` | `target.apply_font_profile` | `JsonTab` or any `FontProfileAware` object | Prefer rich, app-specific font application                     |
| `getattr` | `app/font_controller.py:202` | `target.setFont`            | generic `QWidget`-like object              | Fall back to standard widget font application                  |
| `getattr` | `app/font_controller.py:205` | `target.font`               | widget exposing `font()`                   | Preserve base font details when computing the replacement font |

**Reevaluated meaning:** this is one of the cleanest internal protocol boundaries in the codebase. The dynamic lookup is
not a hack; it is the interface design.

---

## D. Model polymorphism and headless compatibility

`model_actions.py` is the clearest `hasattr`-driven polymorphism layer in the repo.

### Scenario D1 — Model helpers accept “model-like” implementations

| Mechanism | Where                       | Target            | Expected class/object                                        | Purpose                                                          |
|-----------|-----------------------------|-------------------|--------------------------------------------------------------|------------------------------------------------------------------|
| `hasattr` | `model_actions.py:16,59,85` | `model.get_item`  | usually `JsonTreeModel`, but any compatible model is allowed | Access tree items only when the richer model API exists          |
| `hasattr` | `model_actions.py:115,144`  | `model.move_row`  | same                                                         | Use optimized same-parent move support when available            |
| `hasattr` | `model_actions.py:128,157`  | `model.root_item` | same                                                         | Detect whether a move would bubble above the logical root        |
| `hasattr` | `model_actions.py:173`      | `model.sort_keys` | same                                                         | Enable sort operation only for models that implement key sorting |
| `getattr` | `model_actions.py:175`      | `model.show_root` | same                                                         | Decide how an invalid selection maps to the visible root row     |

**Full-picture boundary:** `model_actions.py` treats the model as a protocol-defined collaborator, not a strict class
dependency.

---

## E. Heterogeneous data and stream protocols

### Scenario E1 — Streaming JSON encoder distinguishes containers from generators by protocol

| Mechanism | Where                                | Target         | Expected class/object            | Purpose                                                                               |
|-----------|--------------------------------------|----------------|----------------------------------|---------------------------------------------------------------------------------------|
| `hasattr` | `jsontream/__init__.py:55,68,88,151` | `obj.__iter__` | iterable / generator-like object | Detect whether the value is streamable                                                |
| `hasattr` | `jsontream/__init__.py:56,69,89,152` | `obj.__len__`  | sized iterable                   | Distinguish concrete/sized containers from one-shot generators                        |
| `hasattr` | `jsontream/__init__.py:60,73,94,157` | `obj.__next__` | iterator / generator             | Detect generator-like values that must be handled specially in streaming encode paths |

**Why this matters:** this is cross-boundary logic too, but the boundary is not between app modules — it is between the
encoder and arbitrary user data.

### Scenario E2 — Affix MRU bootstrapping walks mixed object graphs by shape

| Mechanism | Where                      | Target                           | Expected class/object            | Purpose                                             |
|-----------|----------------------------|----------------------------------|----------------------------------|-----------------------------------------------------|
| `hasattr` | `state/affix_mru.py:40`    | `node.value`                     | usually `tree.item.JsonTreeItem` | Detect tree-item wrappers that hold a typed payload |
| `getattr` | `state/affix_mru.py:40,41` | `node.value`                     | same                             | Read the wrapped `NumberAffix`                      |
| `hasattr` | `state/affix_mru.py:43`    | `node.child_items`               | usually `JsonTreeItem`           | Detect model-backed container nodes                 |
| `getattr` | `state/affix_mru.py:44`    | `node.child_items`               | same                             | Recurse into tree children                          |
| `getattr` | `state/affix_mru.py:12`    | `settings.NUMBER_AFFIX_MRU_SIZE` | `settings` module                | Read optional configuration with a default fallback |

Accepted root shapes:

- `NumberAffix`
- `JsonTreeItem`
- `dict`
- `list`

### Scenario E3 — Drag/drop accepts richer mime objects but degrades gracefully

| Mechanism | Where                    | Target      | Expected class/object                 | Purpose                                                                         |
|-----------|--------------------------|-------------|---------------------------------------|---------------------------------------------------------------------------------|
| `hasattr` | `tree_actions/dnd.py:65` | `mime.text` | `QMimeData` or compatible mime object | Allow text-backed fallback drops when the structured tree MIME format is absent |

### Scenario E4 — DnD view hook is optional and view-specific

| Mechanism | Where                     | Target                              | Expected class/object            | Purpose                                                                                                   |
|-----------|---------------------------|-------------------------------------|----------------------------------|-----------------------------------------------------------------------------------------------------------|
| `hasattr` | `tree_actions/dnd.py:119` | `view.mark_drag_handled_internally` | usually `tree.view.JsonTreeView` | Notify custom tree view that the internal move was already handled so Qt does not delete destination rows |

---

## F. Validation and schema reflection boundaries

### Scenario F1 — Validation errors are adapted from foreign object models

| Mechanism | Where                             | Target                                                 | Expected class/object                                                          | Purpose                                                   |
|-----------|-----------------------------------|--------------------------------------------------------|--------------------------------------------------------------------------------|-----------------------------------------------------------|
| `getattr` | `validation/validator.py:119`     | `err.kind`, `err.validator`, `err.keyword`, `err.rule` | mostly `jsonschema.exceptions.ValidationError` or ValidationError-like objects | Normalize error kind across engines/shapes                |
| `getattr` | `validation/validator.py:134`     | `err.validator`, `err.context`                         | same                                                                           | Detect combinator (`oneOf` / `anyOf`) errors              |
| `getattr` | `validation/validator.py:144`     | `err.schema_path`                                      | same                                                                           | Determine branch membership in combinator contexts        |
| `getattr` | `validation/validator.py:192,193` | `err.path`, `err.schema_path`                          | same                                                                           | Score specificity of nested errors                        |
| `getattr` | `validation/validator.py:231,232` | `err.path`, `err.schema_path`                          | same                                                                           | Rebuild absolute coordinates during combinator unwrapping |
| `getattr` | `validation/validator.py:242,244` | `err.instance_path`, `err.path`                        | same                                                                           | Normalize instance location                               |
| `getattr` | `validation/validator.py:246`     | `err.message`                                          | same                                                                           | Extract user-visible text                                 |
| `getattr` | `validation/validator.py:248`     | `err.schema_path`                                      | same                                                                           | Build app-level schema paths                              |

**Reevaluated meaning:** this is a pure adapter boundary. Unlike the `JsonTab` cases, the goal is not loose internal
coupling but robust normalization of third-party error shapes.

### Scenario F2 — Schema registry binding is late-bound through a module seam

| Mechanism | Where                            | Target                          | Expected class/object           | Purpose                                                                               |
|-----------|----------------------------------|---------------------------------|---------------------------------|---------------------------------------------------------------------------------------|
| `getattr` | `documents/tab_validation.py:37` | `documents.tab.schema_registry` | imported `documents.tab` module | Keep monkeypatch/test substitution compatible while defaulting to the shared registry |

### Scenario F3 — Validation dock uses bounded reflection over known signal/ref names

| Mechanism | Where                            | Target                                                                           | Expected class/object                        | Purpose                                                          |
|-----------|----------------------------------|----------------------------------------------------------------------------------|----------------------------------------------|------------------------------------------------------------------|
| `getattr` | `app/validation_dock.py:145`     | `self._tab.<sig_name>` where `sig_name ∈ {"validationChanged", "schemaChanged"}` | `JsonTab`                                    | Disconnect the old tab’s signals without duplicated code         |
| `getattr` | `app/validation_dock.py:146`     | `self._on_<derived_name>`                                                        | `ValidationDock`                             | Resolve the corresponding slot method                            |
| `getattr` | `app/validation_dock.py:189,226` | `ref.url` / `self._tab.schema_ref.url`                                           | usually `validation.schema_source.SchemaRef` | Support file-backed and URL-backed schema references defensively |

**Expected classes:**

- sender side: `documents.tab.JsonTab`
- receiver side: `app.validation_dock.ValidationDock`
- reference object: `validation.schema_source.SchemaRef`

---

## Where `hasattr` and `getattr` complement each other most clearly

## 1. `tree_actions/*` ↔ `JsonTab`

This is the clearest combined pattern.

- `hasattr` is used to **find** a compatible tab host:
    - `push_insert_rows`
    - `push_move_rows`
    - `edit_name_or_value_from_enter`
    - `parent`
    - `commit_set_data`
- `getattr` is then used to **consume** tab-owned services:
    - `_status_message_callback`
    - `search_edit`
    - `_apply_filter`
    - `_last_move_placed`
    - `edit_name_or_value_from_enter`

So `tree_actions/*` does not depend on “a concrete tab object handed in directly”; it dynamically discovers and then
uses a tab-like host.

## 2. Delegate/editor code ↔ collaborator protocols

- `documents/tab_setup.py` exposes collaborators from the tab via `getattr`
- `delegates/editor_factory.py` verifies collaborator methods via `hasattr`
- `app/font_controller.py` dispatches to subscribers via `getattr`

This is a coherent protocol-oriented design pattern, not isolated ad hoc checks.

## 3. Model helper layer ↔ model-like objects

- `model_actions.py` uses `hasattr` to decide whether the richer tree-model API exists
- then uses `getattr(model, "show_root", False)` as a soft value read

This is a second major soft-interface boundary beside `JsonTab`.

## 4. Qt/runtime compatibility

- `hasattr` checks whether Qt exposes a property/signal/enum member
- `getattr` then reads or calls the runtime-specific capability

This is especially visible in theme/color-scheme code.

---

## Targets expected to fall into each dynamic boundary

## Internal app objects

- `documents.tab.JsonTab`
- `documents.mutation_gateway.DocumentMutationGateway` indirectly via `tab.mutations...`
- `tree.model.JsonTreeModel`
- `tree.view.JsonTreeView`
- `tree.item.JsonTreeItem`
- `state.affix_mru.AffixMRU`
- `themes.icon_provider.FileIconProvider`
- `themes.icon_provider.StubIconProvider`
- `app.validation_dock.ValidationDock`

## Qt/runtime objects

- `QStyleHints`
- `QPalette.ColorRole`
- `QByteArray`-like read buffers
- `QMimeData`
- item-view widgets used as delegate hosts (`QTreeView` / `QAbstractItemView`-like)

## Third-party / foreign objects

- `jsonschema.exceptions.ValidationError` and ValidationError-like objects
- `importlib.resources` `Traversable` objects
- timezone implementations (`ZoneInfo`, pytz-like objects, other `tzinfo` providers)
- user data that is iterable/generator-like for `jsontream`

---

## Risk and maintenance notes, reevaluated

### Strong, intentional uses

These dynamic probes look deliberate and architecturally justified:

- Qt / PyInstaller / timezone / resource compatibility checks
- `app/font_controller.py` subscriber protocol dispatch
- `delegates/editor_factory.py` collaborator protocol checks
- `validation/validator.py` foreign-object normalization
- `model_actions.py` compatibility with model-like objects

### More fragile uses

These rely on private or convention-based contracts:

- `JsonTab` private collaborators such as `_status_message_callback`, `_icon_provider`, `_apply_filter`,
  `_last_move_placed`, `_font_pt`
- `JsonTypeDelegate._interactive`
- the context-menu `commit_set_data` capability check vs actual `tab.mutations.commit_set_data(...)` call path

These are not necessarily bugs, but they show that some internal boundaries are still **soft by convention** rather than
made explicit through protocols or adapters.

### What changed after adding `hasattr`

The earlier `getattr`-only conclusion (“`JsonTab` is the central dynamic target”) is still true, but incomplete.

The fuller conclusion is:

1. `JsonTab` is the main **capability hub**.
2. `hasattr` shows how modules **discover** that hub from generic Qt widgets.
3. `model_actions.py` is a second protocol-based hub around model capabilities.
4. Some dynamic behavior is not about UI boundaries at all, but about **data protocol detection** (`jsontream`) and *
   *third-party object adaptation** (`validation/validator.py`).

---

## Condensed inventory

| Mechanism               | Production Python expressions | Files |
|-------------------------|------------------------------:|------:|
| `getattr(...)`          |                            52 |    17 |
| `hasattr(...)`          |                            43 |    14 |
| Combined dynamic probes |                            95 |    23 |

## Highest-signal boundary clusters

| Boundary cluster                               | Main files                                                                                                                                                                                           |
|------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `JsonTab` capability discovery and consumption | `tree_actions/context_menu.py`, `tree_actions/structure.py`, `tree_actions/dnd.py`, `tree_actions/paste.py`, `state/view_state.py`, `documents/tab_setup.py`, `documents/tab.py`, `undo/commands.py` |
| Model-like protocol boundary                   | `model_actions.py`                                                                                                                                                                                   |
| Validation-error adapter boundary              | `validation/validator.py`                                                                                                                                                                            |
| Runtime/Qt compatibility boundary              | `app/theme_controller.py`, `themes/auto.py`, `themes/registry.py`, `main.py`, `qt2py/__init__.py`, `qhexedit/chunks.py`                                                                              |
| Data protocol boundary                         | `jsontream/__init__.py`, `state/affix_mru.py`                                                                                                                                                        |
| Delegate/controller protocol boundary          | `delegates/editor_factory.py`, `delegates/type_delegate.py`, `app/font_controller.py`                                                                                                                |

---

## Bottom line

If the repo is viewed through **both** `getattr` and `hasattr`, the most important architectural relationship is:

**The codebase is organized around soft capability boundaries, with `JsonTab` as the primary internal hub
and `model_actions.py` as a secondary model-protocol hub.**

`hasattr` answers **who can participate** in a boundary.
`getattr` answers **what is consumed once that boundary is crossed**.

That full picture shows three broad dynamic styles:

1. **internal soft interfaces** between UI/document/action modules,
2. **runtime compatibility probes** for Qt/PyInstaller/Python objects,
3. **duck-typed normalization** of foreign data and validation objects.

So dynamic attribute access here is not primarily metaprogramming for its own sake; it is the mechanism the repository
uses to keep subsystem seams flexible while still supporting undo-aware UI actions, headless helpers, runtime
portability, and third-party object adaptation.
