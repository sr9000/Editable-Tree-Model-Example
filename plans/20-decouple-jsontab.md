# Plan 20 — Decouple `JsonTab` from application logic

**Source report:** `reports/documents_module_design_report.md`
**Severity rating in report:** 3 / 10 (duct-taped monolith)
**Branch suggestion:** `decouple-jsontab`
**Last updated:** 2026-05-28

---

## 0. Operating rules (apply to every step)

These are the non-negotiables every step in this plan must obey. Any
step that cannot satisfy them is split further before it lands.

1. **Baby steps.** Every step is bounded by:
    * ≤ ~300 lines of diff (excluding pure moves / re-exports),
    * 1 conceptual change (rename, extract, redirect, delete),
    * 1 commit at the end of the step.
2. **Definition of Done (DoD) gate.** A step is *done* only when **all**
   the following pass on a clean checkout:
   ```bash
   make lint
   make check-no-reflection
   timeout 100 pytest -q
   ```
    * Lint failure → fix in the same step, do not commit.
    * Reflection check failure → fix in the same step.
    * Test failure → either fix in the same step or **revert** the step
      entirely and split it further. **No skips, no xfails** introduced
      to keep the gate green.
3. **Timeouts for potential hangs.** All test invocations wrap pytest
   with `timeout 100` (1min40s) and each test that exercises Qt event
   loops uses `qtbot.waitSignal(..., timeout=2000)` (already the suite
   convention). For new sub-process or socket-touching code added by a
   step, the step PR must add an explicit timeout. Background processes
   spawned by tests must be torn down in fixtures.
4. **Git hygiene.** After the DoD gate passes:
   ```bash
   git add -A
   git commit -m "decouple-jsontab: <step-id> <one-line summary>"
   ```
   No squashing across steps. Each step is independently bisectable.
5. **No new `getattr` / `hasattr`** outside the allowlist
   (`.githooks/pre-commit`). The new abstractions must be explicit
   `Protocol`s or concrete classes — never duck-typed via reflection.
6. **No semantic change in a structural step.** A move/rename step
   may not also change behaviour. A behaviour change step may not
   also rename. If a step needs both, split it.
7. **Rollback contract.** Each step records, in its commit message,
   the exact `git revert <sha>` instruction that returns the tree to
   the pre-step state without breaking later steps that didn't depend
   on it.

---

## 1. Why this plan exists

The report identifies four overlapping smells:

| Smell                                  | Evidence (counts in tree at plan time)                                  |
|----------------------------------------|-------------------------------------------------------------------------|
| `data_store` leaks across the app      | **212** hits across **17** non-test, non-`documents/` files             |
| `tab_protocols.py` mirrors god-object  | 8 protocols, all expose `data_store: Any` and underscore-prefixed hooks |
| `JsonTab` is a 407-line god router     | ~60 delegated methods on one class                                      |
| Qt types contaminate command/undo code | `QModelIndex` + `tab.data_store.view.setCurrentIndex(...)` in `undo/`   |

Hottest leaked attributes (callers outside `documents/` and `tests/`):

```
64 mutations     54 model    27 file_path    17 view
12 undo_stack     8 validation  8 schema_source  5 is_dirty
 3 save_format    3 is_read_only  2 search_edit   2 schema_ref
 2 last_move_placed  2 issue_index   1 _user_sized_columns
 1 _font_pt    1 affix_mru
```

The plan retires these accesses in roughly that order of volume, since
the biggest payoff per step is in the heaviest leaks (`mutations`,
`model`, `file_path`, `view`).

---

## 2. Target architecture (north star, not a step)

We are heading toward four narrow seams that everything outside
`documents/` is allowed to depend on:

1. **`Document`** — a stable façade exposing:
    * `file_path`, `display_name`, `is_dirty`, `is_read_only`,
      `save_format`, `schema_source`, `schema_ref`
    * signals: `dirtyChanged`, `schemaChanged`, `validationChanged`,
      `fileChanged`, `closing`
    * `save(path=None, fmt=None)`, `reload()`, `close()`
      No Qt widgets, no `model`, no `view`, no `undo_stack` exposed.
2. **`DocumentMutations`** — already partially present
   (`documents/mutation_gateway.py`). Becomes the only entry point for
   tree edits; accepts **paths** (`tuple[int, ...]`) and pure-Python
   payloads — not `QModelIndex`. Emits typed signals on success/failure.
3. **`DocumentView`** — a thin controller bound to one `JsonTreeView`,
   responsible for selection / expansion / scroll / filter. It is the
   only place allowed to call `setCurrentIndex`, `expand`, `scrollTo`.
   Undo commands talk to it through a `ViewportRequest` signal, never
   directly.
4. **`DocumentValidation`** — wraps `IssueIndex`, schema source/ref,
   and the revalidate trigger. Already mostly present in
   `tab_validation.py`; the step here is to surface it through
   `Document.validation` and stop reaching for `tab.data_store.validation`.

`JsonTab` becomes the QWidget assembly that owns these four objects
and wires Qt signals. Nothing else.

---

## 3. Phased step list

Each step has: **goal**, **scope**, **DoD-specific notes**, **rollback**.

### Phase A — Instrumentation & safety net (no behaviour change)

* **A1. Add a `Document` Protocol stub.**
  *Goal:* introduce `documents/document_protocol.py` with the narrow
  surface listed in §2.1. No implementation, no callers yet.
  *DoD:* lint + tests green; new file is imported by nothing.
  *Rollback:* `git revert` the single commit; nothing else to undo.

* **A2. ~~Add a deprecation shim recorder.~~ — DEFERRED.**
  Original plan was a `__getattr__` hook on `JsonTabData` logging
  external reads. Two reasons to skip:
  1. The reflection ban (`.githooks/pre-commit`) matches `__getattr__(`
     against its `\b(get|has)attr\(` regex, so the hook would need
     allowlisting purely for instrumentation — wrong trade-off.
  2. The §1 access matrix already enumerates every leaked attribute
     (`mutations` 64, `model` 54, `file_path` 27, …) which is the
     only data the audit was meant to produce. No additional
     information is needed to drive Phases B–F.
  Re-open A2 only if Phase B uncovers callers not captured by the
  static grep.

* **A3. Pin the test gate.**
  *Goal:* add a `make test` target wrapping
  `QT_QPA_PLATFORM=offscreen timeout 600 pytest -q --deselect <3 known
  failures>`. Closes one open tooling TODO in
  `ai-memory/todo-n-fixme.md`.
  *DoD:* `make test` exits 0 on a clean tree.
  *Rollback:* trivial — Makefile-only.

### Phase B — Stop leaking `mutations` (64 hits)

The mutation gateway already exists; consumers just need to dereference
it through a typed accessor instead of `tab.data_store.mutations.*`.

* **B1. Expose `Document.mutations` as a typed property.**
  *Goal:* add `mutations: DocumentMutationGateway` to the Protocol from
  A1 and make `JsonTab.mutations` (already present) declared with that
  type. No callers change yet.
  *DoD:* full gate.

* **B2. Redirect `tree_actions/` to `tab.mutations`.**
  *Goal:* replace every `tab.data_store.mutations` → `tab.mutations` in
  `tree_actions/{anchors,paste,structure,context_menu,dnd}.py`.
  Mechanical edit, no semantics change.
  *DoD:* full gate. Targeted runs first:
  `pytest -q tests/test_drag_drop_*.py tests/test_context_menu_*.py
   tests/test_paste_placement.py tests/test_anchor_move.py
   tests/test_tree_actions_*.py`.
  *Rollback:* revert single commit.

* **B3. Redirect `app/` and `undo/` to `tab.mutations`.**
  *Goal:* same mechanical swap in `app/main_window*.py`,
  `app/tab_lifecycle.py`, `undo/{commands,diff}.py`.
  *DoD:* full gate plus
  `pytest -q tests/test_undo_*.py tests/test_typed_undo_*.py
   tests/test_tab_lifecycle.py tests/test_smoke_mainwindow.py`.

* **B4. Forbid `data_store.mutations` going forward.**
  *Goal:* add a regex line to `.githooks/pre-commit` rejecting new
  `data_store.mutations` occurrences in non-test files.
  *DoD:* gate green; the regex matches zero files.

### Phase C — Stop leaking `file_path` / `is_dirty` / `is_read_only` /

`save_format` (38 hits combined)

These are already pure-data accessors on `JsonTabDataFacade`. The
change is to read them off `tab` directly.

* **C1. Add forwarding properties on `JsonTab`.**
  Properties already present? Audit and add missing ones
  (`file_path`, `is_dirty`, `is_read_only`, `save_format`,
  `display_name`).
  *DoD:* gate green.

* **C2. Migrate `app/main_window.py` + `app/main_window_actions.py`.**
  Replace `tab.data_store.{file_path,is_dirty,is_read_only,save_format}`
  with `tab.<attr>`. ~20 sites per file → split into two commits if a
  single diff exceeds 300 lines.
  *DoD:* full gate plus
  `pytest -q tests/test_smoke_mainwindow.py tests/test_tab_display_name.py
   tests/test_reload_from_disk.py tests/test_tab_io_controller.py`.

* **C3. Migrate `app/close_confirm.py`, `app/history.py`,
  `app/tab_lifecycle.py`, `app/schema_tab_pool.py`.**
  Same swap. One commit per file.
  *DoD:* full gate.

* **C4. Forbid `data_store.{file_path,is_dirty,is_read_only,save_format}`.**
  Extend the pre-commit regex from B4.

### Phase D — Stop leaking `view` (17 hits)

`view` access splits into two intents:

1. **Read-only selection / current index queries** — turn into helpers
   on a new `DocumentView` controller.
2. **Writes (setCurrentIndex / expand / scrollTo)** — go through a
   `ViewportRequest` signal so undo/commands never touch the QTreeView.

* **D1. Introduce `documents/view_controller.py::DocumentView`.**
  Owns the `JsonTreeView`, exposes:
  `current_path()`, `selected_paths()`, `expanded_paths()`,
  `request_select_paths(paths)`, `request_expand(path)`,
  `request_scroll_to(path)`, signal `viewportRequested`.
  Wired by `JsonTab.__init__`. No callers yet.
  *DoD:* gate green.

* **D2. Migrate read-only callers.**
  `app/main_window.py:_focused_view`, `app/main_window_actions.py`
  selection checks → `tab.view_controller.current_path()` etc.
  *DoD:* full gate plus
  `pytest -q tests/test_smoke_mainwindow.py tests/test_shortcuts_and_menu.py`.

* **D3. Migrate `undo/commands.py` and `undo/diff.py`.**
  Replace `self._tab.data_store.view.setCurrentIndex(...)` calls with
  `self._tab.view_controller.request_select_paths([path])`. The
  controller emits the signal; `JsonTab` connects it to the real
  `QTreeView` in `tab_setup`.
  *DoD:* full gate plus heavy run:
  `pytest -q tests/test_undo_*.py tests/test_typed_undo_*.py
   tests/test_keyboard_multimove*.py tests/test_drag_drop_*.py
   tests/test_anchor_move.py tests/test_move_preserves_expansion.py
   tests/test_phase_5_4_persisted_view_state.py`.
  This is the riskiest step in the plan — if any test flakes, **revert
  immediately** and split into D3a (read-side migration), D3b (signal
  wiring), D3c (call-site replacement).
  *Rollback:* revert the single commit; D1/D2 remain.

* **D4. Migrate remaining `app/validation_*.py` and
  `app/validation_dock.py` view touches.**
  Same pattern.
  *DoD:* full gate plus
  `pytest -q tests/test_validation_*.py tests/test_dock_validation_presenter.py`.

* **D5. Drop `view` from `JsonTabData`'s public surface.**
  Keep it as a private `_view` and remove from facade properties.
  Forbid `data_store.view` via pre-commit regex.

### Phase E — Stop leaking `model` (54 hits)

The biggest single attribute. Most external usage is structural reads
(`columnCount`, `index`, `parent`, `get_item`) and a few writes during
load/save. Split by call-site cluster.

* **E1. Audit & classify.** Produce `reports/model_access_audit.md`
  enumerating every call to `data_store.model.*` outside `documents/`
  with an intent label (`read-structural`, `read-data`, `mutate`,
  `signal-connect`). No code change.
  *DoD:* gate green (it's documentation only).

* **E2. Add `Document` read helpers** for the structural calls:
  `column_count()`, `root_path()`, `item_at(path)`, `iter_paths()`.
  Implemented on `JsonTab` delegating to the model. No callers yet.
  *DoD:* gate green.

* **E3. Migrate `state/view_state.py`** (currently the worst offender
  reaching into `_user_sized_columns`). Replace with explicit getters
  on `JsonTab` (`column_widths()`, `set_column_widths(widths)`),
  remove the underscore peeking.
  *DoD:* full gate plus
  `pytest -q tests/test_phase_5_4_persisted_view_state.py
   tests/test_tab_lifecycle.py`.

* **E4. Migrate `app/validation_panel_model.py`,
  `app/validation_presenter.py`, `app/validation_dock.py`.**
  Use the read helpers from E2.
  *DoD:* full gate + `tests/test_validation_*.py`.

* **E5. Migrate `undo/diff.py`, `undo/commands.py`.**
  Where they read the model, route through E2 helpers; where they
  mutate, they already go through the mutation gateway after Phase B.
  *DoD:* full gate + full undo/typed-undo + drag-drop suites.

* **E6. Migrate the residue** (`tree_actions/*`, `app/main_window.py`).
  *DoD:* full gate.

* **E7. Forbid `data_store.model`** via pre-commit regex; keep
  `data_store.model` available only inside `documents/` for now.

### Phase F — Stop leaking the long tail

(`undo_stack`, `validation`, `schema_source`, `schema_ref`,
`search_edit`, `affix_mru`, `_font_pt`, `last_move_placed`,
`issue_index`)

* **F1. `undo_stack` → `tab.history` controller.**
  Already partially present (`tab_history.py`); just expose `tab.history`
  with typed methods `clear()`, `set_clean()`, `is_clean()`,
  `index()`. Replace 12 call sites. Forbid `data_store.undo_stack`.
  *DoD:* full gate + `tests/test_tab_history_controller.py
   tests/test_undo_*.py`.

* **F2. `validation` → `tab.validation`.**
  Expose `DocumentValidation`. Replace 8 sites. Forbid
  `data_store.validation`.
  *DoD:* full gate + `tests/test_validation_*.py`.

* **F3. `schema_source` / `schema_ref` → `tab.schema_source` /
  `tab.schema_ref`.** Properties already exist on `JsonTab`. Mechanical
  swap (10 sites). Forbid via regex.

* **F4. `search_edit` → `tab.set_filter_text(str)` / `tab.filter_text`.**
  No widget escapes `documents/`. Forbid.

* **F5. `affix_mru`, `_font_pt`, `last_move_placed`, `issue_index`.**
  Single-shot migrations, one commit each, forbid each.

### Phase G — Burn `tab_protocols.py`

After Phases B–F the external surface is `tab.*` accessors with proper
types. Internal protocols can now be reduced to real interfaces.

* **G1. Replace `Any` with concrete types** in each protocol
  (`data_store: JsonTabData`, `undo_stack: QUndoStack`, list element
  types, etc.). Run mypy/pyright if configured; otherwise rely on the
  test gate.
  *DoD:* full gate.

* **G2. Inline each protocol into its sole consumer.**
  Most protocols are used by exactly one peer module
  (`tab_commands.py`, `tab_editing.py`, …). Replace `Protocol`
  parameters with the concrete `"JsonTab"` forward reference and a
  TYPE_CHECKING import. One commit per protocol (8 commits).
  *DoD:* gate after each.

* **G3. Delete `tab_protocols.py`.**
  Final commit when the file has no remaining importers.

### Phase H — De-Qt the command layer

* **H1. Add `paths` overloads to mutation gateway.**
  Every `push_*` method accepts either `QModelIndex` (current) or
  `tuple[int, ...]` (new). The new path is exercised by adapting
  exactly one caller (`tree_actions/structure.py::insert_row`).
  *DoD:* full gate.

* **H2. Migrate `tree_actions/` callers** to pass paths.
  One file per step (`structure.py`, `dnd.py`, `paste.py`,
  `context_menu.py`, `anchors.py`). After all five, drop the
  `QModelIndex` overload from public signatures (keep an internal
  `_from_index` adapter).
  *DoD:* full gate after each file.

* **H3. Migrate `undo/commands.py`** to operate purely on paths and
  pure-Python payloads. Selection restoration uses the
  `ViewportRequest` signal added in D3.
  *DoD:* full gate + the full undo/drag/keyboard suites listed in D3.

### Phase I — Decompose `JsonTabData`

Now that nothing external reaches into it, split it.

* **I1.** Extract `IoState` (file_path, save_format, dirty, read_only).
* **I2.** Extract `ViewState` (delegates, proxy, view ref).
* **I3.** Extract `EditingState` (model, mutations, undo_stack,
  affix_mru, move-view caches).
* **I4.** Extract `ValidationState` (validation, schema_*, issue_index).
* **I5.** Delete `JsonTabDataFacade`; `JsonTab` directly composes the
  four states.

Each substep is a pure move + re-export. DoD: full gate, single commit.

### Phase J — Closeout

* **J1.** Update `ai-memory/{repo-map.md, pros-n-cons.md, todo-n-fixme.md,
  history.md}` with the new architecture; cross-reference this plan.
* **J2.** Delete the audit hook from A2.
* **J3.** Tag `decouple-jsontab-complete` and merge to `master`.

---

## 4. Per-step DoD checklist (copy into each commit message body)

```
DoD:
- [ ] make lint
- [ ] make check-no-reflection
- [ ] make test          # QT_QPA_PLATFORM=offscreen timeout 600 pytest -q --deselect <known-fails>
- [ ] targeted subset:   pytest -q <files relevant to this step>
- [ ] grep guard:        no new "data_store.<retired-attr>" introduced
- [ ] timeouts:          any new subprocess/socket carries an explicit timeout
- [ ] rollback line:     git revert <this-sha>
```

A step's commit is rejected (locally, by a rebase before push) if any
box is unchecked.

---

## 5. Risk register

| Risk                                                       | Mitigation                                                                                                                                      |
|------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------|
| Undo command refactor (D3, H3) breaks ~200 selection tests | Land as smallest possible commits; revert-first policy; signal wiring before usage.                                                             |
| `make test` runs ~1000 tests and may exceed 10 min on CI   | `timeout 600` is local; CI may raise to 1200. Profile + parallelise (`-n auto`) only after the plan completes — splitting now would mask hangs. |
| Hidden duck-typing in tests breaks after protocol shrink   | Phase G runs *after* Phases B–F so the contract has settled; tests that reach into `data_store` keep working until Phase I.                     |
| Reflection allowlist drift                                 | Every step runs `make check-no-reflection`; new code is required to use explicit Protocols.                                                     |
| Plan stalls between phases                                 | Each phase is independently shippable; merging mid-plan to `master` is allowed at phase boundaries (A→J).                                       |

---

## 6. Out of scope (explicitly)

* Rewriting any test to use the new façade. Tests stay as they are; the
  point of the plan is that production code stops reaching into
  internals. Test reach-in is allowed by policy
  (`reports/documents_module_design_report.md` §4 "Testing Layer").
* Replacing Qt's `QUndoStack`. The history controller wraps it.
* Repackaging `documents/` into multiple Python packages. That can
  happen post-J if desired.
* The long-horizon wishlist items in `ai-memory/todo-n-fixme.md` §
  "Long-horizon wishlist".
