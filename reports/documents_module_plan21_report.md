# Report: `documents/` Module — Post Plan 21 Assessment

**Date:** 2026-05-30
**Branch evaluated:** `decouple-json-tab` @ HEAD
**Predecessor report:** `reports/jsontab_god_object_followup_report.md` (5/10)
**Plan executed (mostly):** `plans/21-promote-substates-to-controllers.md` (Phases K–P)
**New score:** **8 / 10** (controllers own behaviour; thin residual facade remains)

---

## TL;DR

Plan 21 has been substantially executed. The passive substates from Plan 20
were **promoted to active controllers**, the `tab_*.py` free-function modules
that took `tab` as their first argument were **dissolved into those
controllers**, `tab.data_store` was **deleted entirely** (including every test
reach-in), and the `Document` protocol is now the **real external return
type**. `JsonTab` shrank from 607 LOC / 117 members to **275 LOC / 58
members**.

What remains keeping this from a 9–10: `JsonTab` is still ~2x the Plan 21 size
target, behaviour has re-concentrated into a 708-LOC `EditingController`, and a
handful of `tab_*.py` modules (`tab_setup`, `tab_status`) still expose free
functions taking `tab`.

| Metric                                       | Plan 20 (5/10) | Plan 21 target | **Now**       | Verdict     |
|----------------------------------------------|----------------|----------------|---------------|-------------|
| `documents/tab.py` LOC                       | 607            | <= 120         | **275**       | Improved    |
| `JsonTab` methods + properties               | 117            | <= 20          | **58**        | Improved    |
| `tab.data_store.*` reads (anywhere)          | 247            | 0              | **0**         | Fixed       |
| `data_store` references in tests             | 61 files       | 0              | **0**         | Fixed       |
| `documents/tab_data.py`                       | exists         | deleted        | **deleted**   | Fixed       |
| `tab_*` free-function modules (tab-coupled)  | 8              | 0              | **2 partial** | Improved    |
| External imports of concrete `JsonTab`       | many           | 0              | **0**         | Fixed       |
| External imports of `Document`               | 0              | many           | **7**         | Fixed       |
| `getattr/hasattr/TYPE_CHECKING` in documents | present        | none new       | **0**         | Clean       |
| Test gate                                    | 1124 pass      | 1124+          | **1124 pass** | Held        |

---

## 1. What landed since the 5/10 report

### 1.1 Substates became controllers — done

`documents/states/` now holds real controllers, not passive containers:

| Module                  | Role                                                                | LOC |
|-------------------------|---------------------------------------------------------------------|-----|
| `editing_controller.py` | `push_*`, type-change, move-view-state, tree-actions, diff/insert    | 708 |
| `io_controller.py`      | `save` / `save_as` / `snapshot`, dirty tracking, `dirtyChanged`      | 91  |
| `view_state.py`         | UI widgets, view, proxy, delegates (still a passive `@dataclass`)    | 30  |
| `validation_state.py`   | back-compat alias -> `documents.tab_validation.TabValidationController`| 7   |
| `editing_state.py`      | back-compat alias -> `EditingController`                            | 7   |

The Plan 20 `tab_commands.py`, `tab_editing.py`, `tab_io.py`, `tab_paths.py`,
`tab_move_view_state.py`, and `tab_tree_actions.py` free-function modules are
**gone**; their logic is now methods on `EditingController` /
`IoController` / `ViewController`. `EditingController` alone exposes 34
members (`push_move_rows`, `push_rename`, `push_edit_value`,
`run_tree_action`, `capture_move_view_state`, `commit_set_data`, ...).

### 1.2 `tab.data_store` fully removed — done

`grep -r data_store` returns **0** matches across the entire repository,
including the 61 test files the predecessor report said pinned the
god-object shape. `documents/tab_data.py` and the `JsonTabData` class are
deleted. This was Plan 21's hardest, explicitly-deferred-from-Plan-20 step.

### 1.3 `Document` protocol is the real seam — done

`documents/document_protocol.py::Document` is a `@runtime_checkable Protocol`
with 7 external importers (`app/main_window.py`, `app/history.py`,
`app/schema_tab_pool.py`, `app/validation_dock.py`, `app/tab_lifecycle.py`,
`state/view_state.py`, `tree_actions/_tab_lookup.py`). No external module
imports the concrete `JsonTab` class any more — runtime `isinstance` checks go
through the lightweight `JsonTabWidgetMarker` ABC, and typing goes through
`Document`. `undo/commands.py` references `"JsonTab"` only as an unresolved
forward-reference string in annotations.

### 1.4 No reflection smells — clean

`getattr` / `hasattr` / `TYPE_CHECKING` count **0** across `documents/*.py`,
satisfying Plan 21 operating rule section 5.

---

## 2. What is still open

### 2.1 `JsonTab` is thinner but not "thin" (58 >> 20)

`JsonTab` is now a forwarding facade rather than a god-object, but it carries
**58 members vs the <= 20 target**. The bulk are property forwarders to
controllers (`io`, `view`, `model`, `mutations`, `undo_stack`, `appearance`,
`editability`, `search_edit`, `affix_mru`, `last_move_placed`, ...) plus a layer
of thin routing wrappers (`_on_type_changed`, `_reopen_value_editor`,
`edit_name_or_value_from_enter`, `_run_tree_action`, `_on_current_changed`).
These exist mostly for test ergonomics and shortcut wiring. The class no longer
*acts*, but it still *advertises* a wide surface.

### 2.2 Duplicate naming / back-compat aliases linger

Three accessor pairs expose the same controller under two names:

* `JsonTab.editing` **and** `JsonTab.editing_state`
* `JsonTab.validation` **and** `JsonTab.validation_state`
* `JsonTab.view_state` (passive dataclass) alongside `JsonTab.view_controller`

plus two alias modules (`states/editing_state.py`, `states/validation_state.py`)
that exist purely as `from ... import X as Y`. These are residue from the
migration and should collapse to one canonical name each.

### 2.3 Behaviour re-concentrated into `EditingController` (708 LOC)

Decoupling `JsonTab` moved — rather than divided — the editing complexity.
`editing_controller.py` is now the largest file in `documents/` at 708 LOC /
34 members, spanning command dispatch, type coercion, move/drag view-state
capture-and-restore, tree-action routing, and the diff/insert primitives. It is
a candidate for a further split (e.g. a dedicated `MoveViewState` helper and a
`DiffApplier` already partly exists) before it becomes the next god-object.

### 2.4 `tab_setup` / `tab_status` keep the "code chunking" shape

Two modules still expose free functions taking `tab` as the first argument:

```
documents/tab_setup.py   init_layout(tab), init_model(tab, ...), init_delegates_and_connections(tab), ...  (6 funcs, 212 LOC)
documents/tab_status.py  on_current_changed(tab, current, previous)
```

These are bootstrap/wiring helpers rather than behaviour, so the smell is mild,
but they are the last places where `tab` is threaded through module-level
functions instead of living on a controller.

---

## 3. Architectural picture today

```
+--------------------------------------------------------------+
|  external callers (app/, undo/, tree_actions/, state/)       |
|    - typing  ----> documents.document_protocol.Document      |
|    - runtime ----> documents.tab_marker.JsonTabWidgetMarker  |
|    - concrete JsonTab import: NONE                            |
+--------------------------------------------------------------+
                              |
                              v
+--------------------------------------------------------------+
|  documents/tab.py :: JsonTab(QWidget, JsonTabWidgetMarker)   |
|    275 LOC / 58 members -- forwarding facade                 |
|    - __init__ (delegates to tab_init.bootstrap)             |
|    - property forwarders -> controllers                     |
|    - thin routing wrappers (shortcuts / tests)              |
|    - Qt signals: dirtyChanged / schemaChanged / validation  |
+--------------------------------------------------------------+
   |            |              |                |            |
   v            v              v                v            v
IoController ViewController EditingController Validation  Appearance/
(91 LOC)    (278 LOC)      (708 LOC) [!]       Controller  Editability/
            +ViewState     +DiffApplier        (276 LOC)   Navigation
            (passive)                                      controllers
```

The dependency direction is correct: external code depends on the protocol,
`JsonTab` depends on its controllers, controllers own their data and behaviour.

---

## 4. Severity of each remaining smell

| Smell                                                    | Today                                        | Severity |
|----------------------------------------------------------|----------------------------------------------|----------|
| `data_store` leaks                                       | Eliminated (0 anywhere)                       | 0/10     |
| `tab_data.py` / `JsonTabData`                            | Deleted                                       | 0/10     |
| External depends on concrete `JsonTab`                  | Eliminated (protocol + marker only)           | 0/10     |
| `tab_*` free-function "code chunking"                    | Mostly gone; `tab_setup`/`tab_status` remain  | 2/10     |
| `JsonTab` member count (58 vs <= 20)                     | Thin facade, still wide                        | 3/10     |
| Duplicate aliases (`editing`/`editing_state`, ...)       | Present                                        | 2/10     |
| `EditingController` is a new 708-LOC concentration       | Real risk of next god-object                   | 5/10     |
| `Document` protocol not adopted                          | Adopted (7 importers)                          | 0/10     |

---

## 5. Recommended closeout (Plan 21 Phase Q + a Plan 22 sliver)

1. **Finish Plan 21 Phase Q** — the plan's own closeout is undone:
   `ai-memory/{repo-map,pros-n-cons,todo-n-fixme}.md` still describe the
   pre-Plan-21 layout, no closing report existed before this one, and the
   branch is still `decouple-json-tab` (not merged/tagged).
2. **Collapse the alias pairs** — pick one name for editing and validation
   accessors; delete `states/editing_state.py` and `states/validation_state.py`
   and the duplicate `JsonTab` properties.
3. **Trim `JsonTab` routing wrappers** — move the shortcut-only `_on_*` /
   `edit_name_or_value_from_enter` / `_run_tree_action` indirections onto the
   controllers and wire shortcuts directly, pushing toward the <= 20 target.
4. **Split `EditingController`** before it ossifies — extract the
   move/drag view-state machinery and the diff/insert primitives into their
   own collaborators so command dispatch and editing concerns separate.
5. **Relocate `tab_setup` / `tab_status` helpers** onto `IoController` /
   `ViewController` / `EditingController` to retire the last `tab`-first
   free functions.

---

## 6. Conclusion

The `documents/` module has crossed from "boundary refactor on a duct-taped
monolith" (5/10) to a **genuinely layered design** (8/10). The god-object is
dismantled, `data_store` is gone, the external surface is a stable protocol,
and the test gate held at 1124. The remaining work is incremental polish —
collapsing aliases, trimming the residual facade, and pre-emptively splitting
`EditingController` — plus formally closing out Plan 21 (docs, tag, merge).

The honest status line:

> **The internal monolith is dismantled. `JsonTab` is a 275-line / 58-member
> forwarding facade over five real controllers; `data_store` and `JsonTabData`
> are deleted; external callers depend only on the `Document` protocol and the
> `JsonTabWidgetMarker` ABC. The decomposition is real, but `JsonTab` is still
> ~2x its size target, `EditingController` has absorbed enough behaviour
> (708 LOC) to warrant its own split, and Plan 21's closeout (Phase Q) is not
> yet done.**
