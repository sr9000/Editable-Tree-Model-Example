# Follow-up Report: `JsonTab` God Object — Post Plan 20

**Date:** 2026-05-29
**Branch evaluated:** `decouple-json-tab` @ HEAD
**Predecessor report:** `reports/documents_module_design_report.md` (3/10 rating)
**Plan executed:** `plans/20-decouple-jsontab.md` (Phases A–I complete)
**New score:** **5 / 10** (boundary sealed, monolith preserved)

---

## TL;DR

Plan 20 successfully **closed the external boundary leak** (the loudest smell
in the predecessor report) but, by design, **did not refactor the
`JsonTab` God Object itself**. Every retired `tab.data_store.<attr>` leak
was replaced with a typed `@property` forward on `JsonTab`, so the public
surface area **grew** rather than shrank.

| Metric                                          | Predecessor (3/10) | Now       | Δ        | Verdict     |
|-------------------------------------------------|--------------------|-----------|----------|-------------|
| External `data_store.*` reads                   | 212                | **0**     | −100%    | ✅ Fixed     |
| Forbidden-attr pre-commit guard                 | none               | 17 attrs  | new      | ✅ Fixed     |
| `tab_protocols.py` god-mirror                   | 8 protocols        | deleted   | gone     | ✅ Fixed     |
| `JsonTabDataFacade` subclass cycle              | yes                | deleted   | gone     | ✅ Fixed     |
| Viewport calls in undo commands                 | 3 sites            | 0 direct  | signal   | ✅ Fixed     |
| Path-typed mutation API                         | none               | 3 methods | new      | ✅ Started   |
| **`tab.py` LOC**                                | **407**            | **607**   | **+49%** | ❌ Regressed |
| **`JsonTab` methods + properties**              | **~60**            | **117**   | **+95%** | ❌ Regressed |
| Internal `data_store.*` reads (in `documents/`) | ~80                | **247**   | +3×      | ❌ Regressed |
| Test gate                                       | 1124 pass          | 1124 pass | stable   | ✅ Held      |

The repo is **strictly better at the boundary** and **slightly worse at the
core**. Plan 20 honoured operating rule §6 ("no semantic change in a
structural step") and policy §6 ("tests stay as they are") at the cost of
allowing the centre to grow.

---

## 1. What Plan 20 actually accomplished

### 1.1 External boundary (the original chief complaint) — **resolved**

The predecessor report's strongest evidence was:

> *"`tab.data_store` is pervasively leaked and mutated by files far
> removed from the `documents` internal logic, creating an incredibly
> tight coupling between application layers."*

Today, **zero** non-test files outside `documents/` read `tab.data_store.*`.
The pre-commit guard `.githooks/_check_data_store_leaks.sh` blocks regression
for 17 attributes: `mutations, file_path, is_dirty, is_read_only,
save_format, undo_stack, schema_source, schema_ref, validation, view, model,
search_edit, last_move_placed, issue_index, affix_mru, _font_pt,
_user_sized_columns`.

### 1.2 Viewport via signal — **resolved**

`undo/commands.py` no longer calls `setCurrentIndex` directly. Selection
restoration during redo/undo flows through
`DocumentView.viewportRequested(kind, payload)` (Plan 20 D-full). Commands
hold paths and pure-Python payloads, never `QModelIndex`.

### 1.3 `tab_protocols.py` god-mirror — **resolved**

The 9 `Protocol` classes (`TabCommandsProtocol`, `TabEditingProtocol`,
`TabBootstrapProtocol`, …) that masked the god-object's surface with
`data_store: Any` are gone (Phase G). Helper modules now annotate `tab:
"JsonTab"` directly via forward-reference strings allowed by
`from __future__ import annotations`.

### 1.4 Substate decomposition — **structurally complete, semantically inert**

`documents/states/` now hosts four substates:

| Substate          | Holds                                                            |
|-------------------|------------------------------------------------------------------|
| `IoState`         | `file_path`, `save_format`, `dirty` + `dirtyChanged` signal      |
| `ViewState`       | `ui`, `view`, `search_edit`, `proxy`, 3× delegate                |
| `EditingState`    | `model`, `mutations`, `affix_mru`, `history`, `last_move_placed` |
| `ValidationState` | (alias of `TabValidationController`) schema, issue index, timer  |

`JsonTabData` composes them and forwards ~30 properties for test back-compat.
`JsonTabDataFacade` was deleted (Phase I5).

**Caveat:** the substates are **passive containers**. No methods moved onto
them. Behaviour still lives on `JsonTab` and on the `tab_*.py` free-function
modules that take `tab` as their first argument.

---

## 2. What Plan 20 did NOT accomplish

### 2.1 `JsonTab` is still a God Object — and bigger than before

The predecessor report called `JsonTab` a "407-line god router" with
"over 60 delegated methods". After Plan 20:

```
$ wc -l documents/tab.py
607 documents/tab.py

$ grep -cE "^    def |^    @property" documents/tab.py
117
```

Inventory of those 117 members by category:

| Category                                 | Count   | Examples                                                   |
|------------------------------------------|---------|------------------------------------------------------------|
| Typed `@property` forwards (Plan 20 B-F) | **~30** | `file_path`, `view`, `model`, `undo_stack`, `_font_pt`     |
| Substate accessors (Plan 20 I5)          | 4       | `io`, `view_state`, `editing_state`, `validation_state`    |
| Narrow read helpers (Plan 20 E2)         | 8       | `root_index`, `root_data`, `row_count`, `column_widths`    |
| `push_*` command dispatchers             | 10      | `push_rename`, `push_move_rows`, `push_insert_rows`        |
| Insert-sibling shortcuts                 | 3       | `insert_sibling_before/after`, `insert_child`              |
| Appearance/zoom routing                  | 14      | `zoom_in/out/reset`, `set_theme`, `apply_font_profile`     |
| Editing routing                          | 4       | `_on_type_changed`, `edit_name_or_value_from_enter`        |
| Move-view caches                         | 5       | `_capture_move_view_state`, `_apply_move_view_state`       |
| Path helpers                             | 5       | `_index_path`, `_index_from_path`, `_qualified_name`       |
| Diff/insert primitives                   | 3       | `_diff_apply`, `_emit_row_changed`, `_insert_typed_item`   |
| Host/status                              | 3       | `refresh_actions`, `show_status`, `show_permanent_message` |
| File IO                                  | 3       | `save`, `save_as`, `_snapshot`                             |
| Lifecycle                                | 3       | `__init__`, `eventFilter`, `closeEvent`                    |
| Validation routing                       | 2       | `goto_validation_issue`, `_on_validation_changed`          |

A class that simultaneously manages file IO, undo history, viewport,
delegates, fonts, filter, validation badges, type coercion and clipboard
hooks **does not satisfy SRP** — exactly the complaint the predecessor
report opened with. Plan 20 made the centre *more* fanned-out, not less.

### 2.2 The `tab_*.py` free-function modules are still tab-coupled

Eight modules expose top-level functions taking `tab: "JsonTab"` as their
first argument:

```
documents/tab_commands.py        11 functions  (push_rename, push_move_rows, …)
documents/tab_editing.py          4 functions  (on_type_changed, …)
documents/tab_setup.py            6 functions  (init_layout, init_model, …)
documents/tab_tree_actions.py     4 functions  (run_tree_action, do_insert_child, …)
documents/tab_move_view_state.py  8 functions  (capture_move_view_state, …)
documents/tab_paths.py            5 functions  (index_path, index_from_path, …)
documents/tab_status.py           3 functions  (on_current_changed, …)
documents/tab_io.py               3 functions  (save, save_as, snapshot)
```

These are the predecessor report's "Code Chunking anti-pattern": they look
like extracted modules but each function dereferences `tab.data_store.*`
internally (247 reads remain inside `documents/`). None of them are
testable without spinning up a full `JsonTab` widget.

### 2.3 The `Document` Protocol is a stub that nothing returns

`documents/document_protocol.py` was introduced in Plan 20 A1 as the
"narrow surface" external callers should depend on. It is imported
nowhere; `app/main_window.py:_current_tab()` still returns concrete
`JsonTab`. The 117-method surface remains visible to every external
caller — they just don't reach into it through `data_store` any more.

### 2.4 Tests still pin the god-object shape

61 test files reach into `tab.data_store.<attr>` (27 distinct attributes).
Plan 20 §6 explicitly forbade migrating them. The ~30 property forwards
on `JsonTabData` exist solely to keep these tests green. Any plan that
deletes those forwards (and thus deletes `JsonTabData` outright) **must
first migrate the tests** — a body of work comparable to Plan 20 itself.

### 2.5 Internal `data_store.*` reads grew from ~80 to 247

Plan 20 retired external reads but added many internal ones because each
`tab.X` typed property is implemented as `return self.data_store.X`. The
substate decomposition added another indirection layer (`data_store.X` →
`data_store.view_state.X` etc.). The number of dot-walks is up; the
*direction* of dependency is unchanged.

---

## 3. Architectural picture today

```
              ┌���─────────────────────────────────────────────────────┐
              │  external callers (app/, undo/, tree_actions/, …)    │
              │       ────► only typed JsonTab.* properties           │
              │             [enforced by pre-commit guard ✅]         │
              └──────────────────────────────────────────────────────┘
                                       │
                                       ▼
              ┌──────────────────────────────────────────────────────┐
              │  documents/tab.py :: JsonTab QWidget                 │
              │  ────────────────────────────────────────────────    │
              │  117 methods + properties                            │
              │    • ~30 typed @property forwards (Plan 20 B–F)      │
              │    • 4 substate accessors    (Plan 20 I5)            │
              │    • 10 push_* dispatchers   (forward to tab_commands)│
              │    • 14 appearance/zoom      (forward to _appearance) │
              │    • 24 misc methods         (helpers, routing)      │
              │                                                      │
              │  ▼ everything fans out into:                         │
              │  documents/tab_data.py :: JsonTabData                │
              │    • holds 4 substates + 2 controllers + host        │
              │    • ~30 @property forwards (for tests)              │
              └──────────────────────────────────────────────────────┘
                  │              │              │              │
                  ▼              ▼              ▼              ▼
               IoState     ViewState    EditingState  ValidationState
              (passive)   (passive)     (passive)     (= alias of
                                                       TabValidationCtl)
```

The substates are storage; the methods that *act* on that storage still
live on JsonTab or on `tab_*` free functions that reach back into JsonTab.

---

## 4. Severity of each remaining smell

| Smell from predecessor report                                  | Today                                                                   | Severity |
|----------------------------------------------------------------|-------------------------------------------------------------------------|----------|
| `data_store` leaks across the app                              | Fixed (212 → 0)                                                         | 0/10     |
| `tab_protocols.py` mirrors god-object                          | Fixed (deleted)                                                         | 0/10     |
| `JsonTab` is a 407-line god router                             | **Worse** (607 LOC / 117 methods)                                       | **7/10** |
| Qt types contaminate command/undo code                         | Partial (path API + ViewportRequest)                                    | 4/10     |
| Code Chunking anti-pattern (free funcs in `tab_*.py`)          | Unchanged                                                               | 6/10     |
| Tests pin god-object shape                                     | Unchanged (61 files reach `data_store`)                                 | 5/10     |
| Private member exposure (underscore methods called externally) | Reduced but present (path helpers, `_proxy_to_source` still public-ish) | 3/10     |
| `Document` Protocol is the advertised return type              | Not done — stub orphaned                                                | 6/10     |

---

## 5. What honest decoupling would require (Plan 21)

The remediation steps the predecessor report listed are still mostly open:

1. **Promote substates from passive containers to controllers.**
   Move `push_*` (currently `documents/tab_commands.py` free functions)
   onto `EditingState`. Move `zoom_*` / `set_theme` / `set_*_font_*`
   onto `JsonTabAppearanceController` (already a class, just unused as a
   target). Move `_apply_filter` onto `ViewState`. Move `save` / `save_as`
   / `_snapshot` onto `IoState`.

2. **Make `Document` (the protocol in `documents/document_protocol.py`)
   the actual return type.**  Migrate `app/main_window.py:_current_tab()`
   and friends to return the protocol, not the concrete `JsonTab` widget.

3. **Migrate tests off `tab.data_store.*`.**  This is the policy reversal
   Plan 20 §6 refused. Without it, `JsonTabData` and its ~30 forward
   properties cannot be deleted. Estimate: ~400 LOC across 61 test files,
   most mechanical (`tab.data_store.view` → `tab.view`).

4. **Convert `tab_*.py` free functions to methods on their owning
   substate/controller.**  E.g. `tab_paths.index_path(tab, idx)` becomes
   `editing_state.path_for(idx)`. The "Code Chunking" smell goes away
   when the modules cease to take `tab` as their first arg.

5. **Shrink `JsonTab` to a 50-line QWidget** that owns four substates and
   wires signals. No `push_*`, no `zoom_*`, no `save`, no `apply_filter`.

This is roughly the same size as Plan 20 itself (~25 commits).

---

## 6. Conclusion

Plan 20 was a successful **boundary refactor**. It was advertised as
"decouple `JsonTab` from application logic" and it delivered exactly that
— the *application* no longer depends on `JsonTab` internals. But the
phrase "decouple `JsonTab`" reads, on a first parse, as "make `JsonTab`
small and focused", and that interpretation is **not** what landed.

The honest status line is:

> **The external boundary is sealed. The internal monolith is preserved
> by design to keep 1124 tests untouched.  `JsonTab` is now a 607-line,
> 117-method facade with every leaked attribute exposed as a typed
> property, and the predecessor report's `Code Chunking` and `SRP
> violations` remain open.**

The score moves from **3/10 (duct-taped monolith)** to **5/10 (boundary
refactor on top of duct-taped monolith)**. A further pass — Plan 21,
roughly the size of Plan 20 — would be required to actually reach
"true decoupling".

See `plans/21-promote-substates-to-controllers.md` for the proposed
follow-up.
