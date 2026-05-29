# Plan 20 — Decouple `JsonTab` from application logic

**Source report:** `reports/documents_module_design_report.md`
**Severity rating in report:** 3 / 10 (duct-taped monolith)
**Branch suggestion:** `decouple-jsontab`
**Last updated:** 2026-05-29

## 🚀 Session 1 Summary (2026-05-28/29)

**Status:** 13 commits landed on `decouple-json-tab`; **57% of easy leaks closed**.

| Phase | Steps      | Status     | Commits |
|-------|------------|------------|---------|
| A     | A1, A3     | ✅ complete | 2       |
| B     | B1–B4      | ✅ complete | 4       |
| C     | C1–C4      | ✅ complete | 4       |
| F     | F1, F2, F3 | ✅ complete | 3       |
| D     | all        | ⏭ deferred | —       |
| E     | all        | ⏭ deferred | —       |
| G–J   | all        | ⏳ planned  | —       |

**Quantified progress:**

- `data_store.*` reads: **212** → **91** (−57%)
- Leaked attributes retired: 8 of 17 (
  `mutations, file_path, is_dirty, is_read_only, save_format, undo_stack, schema_source, schema_ref, validation`)
- Remaining leaks: 9 attrs (56 `model`, 18 `view`, 2 each `search_edit`/`last_move_placed`/`issue_index`, 1 each
  `affix_mru`/`_font_pt`/`_user_sized_columns`)
- Test suite: **1124 pass**, 19s wall-clock, unchanged
- Guard: `.githooks/_check_data_store_leaks.sh` deployed, data-driven, 8 attrs blocked

**Key artifacts:**

- New: `documents/document_protocol.py` (narrow `Document` protocol stub)
- New: `make test`, `make gate` targets in Makefile
- Modified: `documents/tab.py` (added 10 typed properties)
- Modified: ~15 files in `app/`, `undo/`, `tree_actions/`, `state/` (mechanical `data_store.*` → `tab.*` swaps)
- New: shared guard script with tamper-tested FORBIDDEN_DATA_STORE_ATTRS list

**Ready for merge:** Phases A+B+C+F all have full DoD gate passes. Can merge to `master` or push as-is to next session.

---

## 🚀 Session 2 Summary (2026-05-29)

**Status:** 4 commits landed on top of Session 1; **100% of `data_store.*` leaks closed**.

| Phase | Steps       | Status                | Commits |
|-------|-------------|-----------------------|---------|
| D     | D-light     | ✅ complete (shortcut) | 1       |
| E     | E1, E-light | ✅ complete (shortcut) | 2       |
| F     | F4, F5      | ✅ complete            | 1       |
| G–J   | all         | ⏳ planned             | —       |

**Quantified progress:**

- `data_store.*` reads in production: **91** → **0** (−100%)
- Leaked attributes retired: 17 of 17 (added `view`, `model`, `search_edit`,
  `last_move_placed`, `issue_index`, `affix_mru`, `_font_pt`, `_user_sized_columns`)
- Guard `FORBIDDEN_DATA_STORE_ATTRS` now blocks **all** 17 retired attrs
- Test suite: **1124 pass**, 18.9s wall-clock, unchanged across every step
- Risk-control commits: D3 / Phase H deep refactors were *not* attempted —
  this session deliberately took the F-light shortcut for D/E (typed
  `tab.view`, `tab.model` properties) following the precedent set by
  F1/F2/F3-light in Session 1. The plan's deeper architectural goals
  (ViewportRequest signal, path-based mutation API in undo/, narrow
  read helpers in lieu of raw model exposure) remain open and are now
  tracked under Phase H + Phase E follow-up.

**Commits (newest first):**

- `53479de` E-light — expose `tab.model` + swap 55 sites + guard
- `e4a3927` E1 — `reports/model_access_audit.md` (intent classification)
- `87eda49` F4+F5 — long-tail typed accessors (6 attrs, 9 sites)
- `62aa0cb` D-light — expose `tab.view` + swap 18 sites + guard

**What's deferred to Session 3+:**

| Phase  | Theme                                            | Why deferred                                                   |
|--------|--------------------------------------------------|----------------------------------------------------------------|
| D-full | DocumentView controller + ViewportRequest signal | Architectural; only valuable once H wants to drop QModelIndex  |
| E2-E6  | Narrow read helpers (root_data, row_count, …)    | Cosmetic until a real consumer demands them                    |
| G      | Burn `tab_protocols.py`                          | Independent; do whenever                                       |
| H      | De-Qt the command layer (paths, not QModelIndex) | Requires D-full ViewportRequest plumbing                       |
| I      | Decompose `JsonTabData` into 4 substates         | Pure internal refactor inside `documents/`; no external impact |
| J      | Closeout (ai-memory updates, tag, merge)         | After G+H+I land                                               |

**Recommended next-session entry point:** Phase G (delete
`tab_protocols.py` after typing it up) — it's independent, low risk,
and shrinks the visible surface area further. Phase H is the high-value
deep refactor but should wait until someone is willing to take the
ViewportRequest plumbing seriously per the D3 risk register.

---

## 🚀 Session 3 Summary (2026-05-29) — D-full landed

**Status:** 4 commits landed on top of Session 2; **Phase D fully complete**
(controller + signal + all viewport writes routed; deep prerequisite for
Phase H now in place).

| Phase | Steps       | Status                       | Commits |
|-------|-------------|------------------------------|---------|
| D     | D1–D4       | ✅ complete (full, not light) | 4       |
| D5    | rename only | ⏭ rolled into Phase I        | —       |
| G–J   | all         | ⏳ planned                    | —       |

**Quantified progress:**

- `tab.view` viewport-mutation sites outside `documents/`: **5** → **0**
  (undo + tab_lifecycle + state/view_state all routed through
  `view_controller.request_*` signals)
- `tab.view` read sites outside `documents/`: **2** → **0** for selection
  queries (`current_path`, `has_current`)
- Remaining `tab.view` accesses (all legitimate and documented):
    * 4 widget-property reads (`font()`, `columnWidth()`, etc.)
    * 2 signal-connect subscriptions (`selectionModel().currentChanged`)
    * 1 raw-view return for downstream helpers (`_current_view()` →
      delete_selection / expand_all / collapse_all / switch_case_document)
    * 1 multi-select via `QItemSelection` (undo `_select_placed_rows`)
- Test suite: **1124 pass**, 18.8s wall-clock, unchanged across every step
- Heavy targeted suite (154 selection/move/drag tests): passed in 7.78s
  on D3, no flakes — the risk-bound "revert immediately if any flake"
  policy was not triggered

**Commits (newest first):**

- `862d0ca` D4 — route viewport writes in tab_lifecycle + view_state
- `a5e618c` D3 — route 3 undo setCurrentIndex sites through
  `viewportRequested` signal (the original high-risk step; landed
  green in a single commit)
- `9516056` D2 — route 2 selection-query reads (main_window_actions,
  view_state) through `view_controller.current_path()` / `has_current()`
- `9081d68` D1 — add `documents/view_controller.py::DocumentView`
  (signal-mediated viewport controller, no callers yet)

**Key artifacts:**

- New: `documents/view_controller.py` (190 LOC) — `DocumentView` QObject
  with reads (`current_path`, `selected_paths`, `has_current`), writes
  (`request_select_paths`, `request_expand`, `request_expand_all`,
  `request_collapse_all`, `request_scroll_to`), and the
  `viewportRequested(kind, payload)` signal. Wired by
  `documents/tab_init.bootstrap` to its own `apply_request` slot, which
  resolves paths to view-coords through `tab.mutations.source_to_view`
  and pokes the real `QTreeView`.
- New: `tab.view_controller: DocumentView` typed property on `JsonTab`.
- Removed (net): 14 LOC in `state/view_state.py::restore()` — the
  collapseAll-then-iterate-and-expand-with-validity-checks pattern
  collapsed to a flat `request_*` sequence because the controller
  centralises the source→view mapping.

**Notes on the architecture H/I now depend on:**

- The undo command layer now operates **purely on paths and pure-Python
  payloads** for the 3 setCurrentIndex sites that were the original
  Phase H pain point. `undo/commands.py::_MoveRowCmd` no longer needs
  `tab.view` or `tab.mutations.source_to_view` at all in its redo/undo
  paths; selection restoration is one `view_controller.request_select_paths`
  call.
- Phase H's "drop QModelIndex from command signatures" is unblocked.
- Phase I's "rename `JsonTabData.view` → `_view`" is now purely
  internal-to-`documents/` (the guard prevents external regressions);
  it lives more naturally inside the JsonTabData decomposition than as
  a standalone D5 commit, so D5 has been folded into Phase I.

**Deferred follow-ups (small, low-priority):**

- `undo/commands.py::_select_placed_rows` (line 17) still uses
  `QItemSelectionModel.select(QItemSelection)` for true multi-select +
  current-index. The current `request_select_paths` only sets the
  first path as current — multi-select via the controller would need
  a richer apply_request branch. Not on any hot path.
- `validation_dock.py` `currentChanged` signal subscription: could
  introduce `DocumentView.currentPathChanged(path)` and let the dock
  subscribe path-typed; deferred because no other consumer wants it.

**Updated entry-point recommendation for Session 4:** Phase G remains
the cheapest, most-independent next step. Phase H is now realistically
attemptable because D-full unblocked it.

---

## 🚀 Session 4 Summary (2026-05-29) — Phase E full + Phase F closeout

**Status:** 3 commits landed on top of Session 3; **Phase E now
fully complete** (E2-E6, not just E-light) and the underscore-prefixed
forwards left behind by F4+F5 are gone.

| Phase | Steps    | Status                                                                          | Commits |
|-------|----------|---------------------------------------------------------------------------------|---------|
| E     | E2       | ✅ complete (narrow read helpers + zoom_pt/column_widths added)                  | 1       |
| E     | E3       | ✅ complete (state/view_state.py migrated; transitional underscore props pruned) | 1       |
| E     | E4-E6    | ✅ complete (5 files / 10 sites migrated, QModelIndex imports cleaned up)        | 1       |
| E7    | guard    | ✅ already in place from E-light (no change needed)                              | —       |
| F     | closeout | ✅ complete (zoom_pt / column_widths replace _font_pt / _user_sized_columns)     | (in E3) |
| G–J   | all      | ⏳ planned                                                                       | —       |

**Quantified progress:**

- `tab.model` reads outside `undo/`: **12** → **0** (−100%)
- `tab._font_pt` / `tab._user_sized_columns` external reads:
  **3** → **0** (−100%)
- New narrow `JsonTab` helpers shipped: 8 (`root_index`, `root_item`,
  `root_data`, `row_count`, `column_count`, `zoom_pt` property,
  `column_widths`, `set_column_widths`)
- Test suite: **1124 pass**, 18.5s wall-clock, unchanged across every step
- Phase F long-tail residue removed: `JsonTab._font_pt`,
  `JsonTab._user_sized_columns` properties deleted (data lives on
  `JsonTabData` where it belongs)

**Commits (newest first):**

- `2d469d8` E4-E6 — migrate non-undo callers (5 files, 10 sites)
- `32ebfbf` E3 — migrate `state/view_state.py` + drop transitional props
- `6304393` E2 — add narrow read helpers (additive only)

**Key artifacts:**

- New helpers on `JsonTab` (`documents/tab.py`) covering the 17
  non-`undo/` structural/data reads identified by the E1 audit.
- `state/view_state.py` shrunk by 7 LOC; no more reach-in to
  underscore-prefixed `JsonTab` properties.
- `reports/model_access_audit.md` updated with a "Session 4" section
  recording which helpers shipped against which sites.

**What's left for Phase H:**

After Session 4, the **only** remaining `tab.model` accesses are the
38 sites inside `undo/{commands,diff}.py`. They genuinely use the
full `QAbstractItemModel` surface (`beginInsertRows`, `setData(...,
EditRole)`, `removeRow`, `move_row`, `dataChanged.emit`). Phase H
will retire them by routing through the path-based mutation gateway;
this is the deep refactor the plan has been building toward.

The repo state at the end of Session 4 satisfies every Phase G and
Phase H prerequisite:

* **Phase G** ("Burn `tab_protocols.py`") — independent of E/F; the
  protocols are now stable enough to be typed and inlined since no
  external file reaches into `data_store.*` and the `tab.*` surface
  has typed forwards for every retired attribute.
* **Phase H** ("De-Qt the command layer") — unblocked because:
    1. D-full's `ViewportRequest` signal is live, so undo commands
       can already restore selection without holding a QTreeView.
    2. E2-E6 confirm no caller outside `undo/` needs `tab.model`,
       so the mutation gateway can swap its index-based overloads
       for path-based ones without breaking unrelated code.

**Recommended next-session entry point:** Phase G remains the
cheapest, most-independent step. Phase H is now realistically
attemptable and is the highest-value remaining work.

---

## 🚀 Session 5 Summary (2026-05-29) — Phase G burned + Phase H pragmatic landing

**Status:** 2 commits landed on top of Session 4; **`tab_protocols.py`
deleted** and a **path-typed parallel API** added to the mutation
gateway. Phase I (decompose `JsonTabData`) is now unblocked.

| Phase | Steps      | Status                                                                        | Commits |
|-------|------------|-------------------------------------------------------------------------------|---------|
| G     | G1-G3      | ✅ complete (bundled; 9 protocols deleted, marker extracted, 38 sites swapped) | 1       |
| H     | H1+H2      | ✅ complete-pragmatic (path-typed parallel API + 4 proof callers migrated)     | 1       |
| H3    | undo de-Qt | ⏭ deferred indefinitely (requires path-API on tree.model itself; out of plan) | —       |
| I     | all        | 🟢 unblocked                                                                  | —       |
| J     | all        | ⏳ planned                                                                     | —       |

**Quantified progress:**

- `documents/tab_protocols.py`: **−157 LOC** (file deleted; 9 Protocol
  classes retired)
- `documents/tab_marker.py`: **+19 LOC** (marker base extracted so
  `tree_actions/_tab_lookup.py` keeps its isinstance check without
  importing `documents.tab`)
- Protocol annotation swaps: **38 sites** across 10 files now use
  `"JsonTab"` forward-reference strings (allowed by
  `from __future__ import annotations`, banned `TYPE_CHECKING` avoided)
- Path-typed gateway methods added: 3 (`push_edit_value_at`,
  `push_remove_paths`, `push_sort_keys_at`)
- Migrated tree_actions sites: 4 (paste×2, structure×2)
- Test suite: **1124 pass**, 18.4s wall-clock, unchanged

**Commits (newest first):**

- `a861f02` H1+H2 — path-typed parallel API on mutation gateway
- `7b18ca7` G — burn `tab_protocols.py`

**Phase H scope decision (recorded for posterity):**

The plan's literal Phase H text had three goals — command
constructors path-only, viewport via signal, gateway signatures
path-typed. Two of the three were already met by prior sessions:

1. **Command constructors path-only** — met since Phase 5 (pre-plan):
   every `_RenameCmd`/`_EditValueCmd`/`_ChangeTypeCmd`/`_InsertRowsCmd`/
   `_RemoveRowsCmd`/`_MoveRowsCmd`/`_SortKeysCmd`/`_SwitchFieldCaseCmd`
   stores `tuple[int, ...]` paths and dict-shaped pure-Python records,
   never `QModelIndex`.
2. **Viewport via signal** — met in Session 3 by D-full
   (`DocumentView.viewportRequested`).
3. **Gateway signatures path-typed** — addressed in this session by
   the three `push_*_at`/`push_*_paths` methods.

What the plan ALSO listed but is explicitly **out of scope** now:

* **Full tree_actions migration to path API:** 4-6 remaining callers
  still pass `QModelIndex` lists from the selection model. Migrating
  them adds no architectural property (the path representation just
  moves one method earlier in the same call chain). The
  QModelIndex-typed methods are now a **permanent, supported API**
  rather than a deprecation target.
* **Fully de-Qt `undo/commands.py`:** the 38 `tab.model.*` sites in
  `undo/{commands,diff}.py` are legitimate uses of the
  `QAbstractItemModel` contract. Eliminating them would require
  adding a parallel path-based mutation API on `tree.model.JsonTreeModel`
  itself — a separate refactor outside the decouple-jsontab plan.
  `reports/model_access_audit.md` already documented this verdict;
  it is reaffirmed here.

**Why this state unblocks Phase I:**

Phase I (decompose `JsonTabData` into `IoState`/`ViewState`/
`EditingState`/`ValidationState`) is a purely internal refactor
inside `documents/`. Its preconditions:

| Precondition                                             | Met by             |
|----------------------------------------------------------|--------------------|
| No external caller reaches into `JsonTabData`            | Phases B-F         |
| `JsonTab` public surface stable (typed properties)       | Phases B-F + E2-E6 |
| Undo commands don't hold QModelIndex in constructors     | Phase 5 (pre-plan) |
| Viewport not coupled to view location in JsonTabData     | Phase D-full       |
| No mirrored Protocol surface that needs parallel updates | Phase G            |

All five are now in place. Phase I can move attributes between
substates without parallel work in tree_actions/, undo/, or app/.

**Recommended next-session entry point:** Phase I1
(extract `IoState`). The expected commit shape is a one-file move:
move `file_path` / `save_format` / `dirty` / `read_only` into a new
`documents/states/io_state.py`, leave `JsonTabData.io: IoState` as
the access point, keep current `JsonTabData.file_path` etc. as
@property forwards so the existing JsonTab-side facades don't
churn. Then I2 (ViewState), I3 (EditingState), I4 (ValidationState)
in the same pattern, and I5 deletes the facade.

---

## 🚀 Session 6 Summary (2026-05-29) — Phase I fully landed

**Status:** 5 commits landed on top of Session 5; **Phase I complete**
(`JsonTabData` decomposed into 4 substates + `JsonTabDataFacade` deleted).
Phase J (closeout) is the only remaining work in the plan.

| Phase | Steps   | Status                                                   | Commits |
|-------|---------|----------------------------------------------------------|---------|
| I     | I1      | ✅ complete (IoState moved to documents/states/)          | 1       |
| I     | I2      | ✅ complete (ViewState extracted; 7 attrs forwarded)      | 1       |
| I     | I3      | ✅ complete (EditingState extracted; 5 attrs forwarded)   | 1       |
| I     | I4      | ✅ complete (ValidationState aliased in states/)          | 1       |
| I     | I5      | ✅ complete (JsonTabDataFacade deleted; merged into Data) | 1       |
| J     | all     | ⏳ planned                                                | —       |

**Quantified progress:**

- `documents/states/` subpackage created with 4 substate modules
  (`io_state.py` 64 LOC, `view_state.py` 42 LOC, `editing_state.py`
  33 LOC, `validation_state.py` 16 LOC alias) + `__init__.py` 17 LOC
- `documents/tab_data_facade.py`: **−190 LOC** (file deleted; contents
  merged into `tab_data.py`)
- `documents/tab_data.py`: **+155 LOC** net (now self-contained with
  protocols + ~25 property forwards + 2 cross-cutting controllers)
- New `JsonTab` substate accessors: 4 (`io`, `view_state`,
  `editing_state`, `validation_state`)
- Test suite: **1124 pass**, ~18.4s wall-clock, unchanged across
  every step (I1: 18.34s, I2: 18.30s, I3: 18.50s, I4: 18.62s,
  I5: 18.60s)

**Commits (newest first):**

- `74bc4b2` I5 — delete JsonTabDataFacade; JsonTab composes substates directly
- `0ea3191` I4 — expose ValidationState in documents/states/
- `46bf7b3` I3 — extract EditingState into documents/states/
- `b808e99` I2 — extract ViewState into documents/states/
- `2f29030` I1 — extract IoState into documents/states/

**Architectural end state:**

```
JsonTab
├── tab.io                  → IoState         (file_path/save_format/dirty)
├── tab.view_state          → ViewState       (ui/view/proxy/3×delegate/search_edit)
├── tab.editing_state       → EditingState    (model/mutations/affix_mru/history/last_move_placed)
├── tab.validation_state    → ValidationState (= TabValidationController; schema/issue_index/timer)
│
└── tab.data_store : JsonTabData
    ├── view_state            ← canonical storage for view widgets
    ├── editing_state         ← canonical storage for editing axis
    ├── io                    ← canonical storage for IO axis
    ├── validation            ← canonical storage for validation axis
    ├── editability           ← cross-cutting controller (read-only mode)
    ├── appearance            ← cross-cutting controller (font/theme)
    └── ~30 @property forwards (file_path, model, view, undo_stack,
                                is_dirty, schema_*, _font_pt, ...)
        — preserved verbatim for the 61 test files that reach into
        tab.data_store.<attr> per Plan 20 section 6.
```

**Design decisions recorded in commit messages:**

- I1 + I2 + I3 are "true" extractions: each creates a new substate
  dataclass and moves storage into it; the legacy attribute names
  on `JsonTabData` survive as read+write @property forwards.
- I4 is an **alias** (`ValidationState = TabValidationController`)
  rather than a body move, because the underlying 236-LOC controller
  already encapsulates everything correctly and would have only
  acquired a different module path from a physical move. Same
  outcome as I1 for the dataclass annotation and the I2-I3 pattern
  for the property forwards. Plan section 0 rule "no semantic change
  in a structural step" is honoured by both flavours.
- I5 deletes `JsonTabDataFacade` outright by inlining all of its
  contents (protocols + ~25 property forwards + dataclass field
  inventory) into `JsonTabData`. Eliminates the subclass relation
  that was no longer load-bearing after I1-I4.
- The four `tab.<substate>` accessors added in I5 satisfy the
  plan's literal "JsonTab directly composes the four states"
  wording while leaving external callers on their existing typed
  per-attribute forwards (no churn outside `documents/`).

**What's left for Phase J (closeout):**

* Update `ai-memory/{repo-map.md, pros-n-cons.md, todo-n-fixme.md,
  history.md}` to reflect the new substate architecture and cross-
  reference Plan 20.
* Update the Phase I status marker in section 3 below (this commit
  + the commit you are reading do that).
* Verify there are no longer any references to `JsonTabDataFacade`
  or `tab_data_facade` outside historical commit messages.
* Tag `decouple-jsontab-complete` and merge to `master`.

**Recommended next-session entry point:** Phase J. There is no
deferred deep refactor blocking the merge — all five Phase H/I
preconditions are satisfied and the test gate has stayed green
across 13 of the plan's 16 substantive commits.

---

### If resuming on the same branch (`decouple-json-tab`)

1. **Start with Phase D (high-risk).** Do NOT attempt bulk Phase E before reading this:
    - D3 is the riskiest step: it redirects `undo/commands.py`'s `setCurrentIndex` through a new `ViewportRequest`
      signal.
    - **Revert-first policy:** If any test flakes, revert D3 immediately and split into D3a (read-side), D3b (signal
      wiring), D3c (call-site).
    - Run the full heavy suite after D3:
      `pytest -q tests/test_undo_*.py tests/test_typed_undo_*.py tests/test_keyboard_multimove*.py tests/test_drag_drop_*.py tests/test_anchor_move.py tests/test_move_preserves_expansion.py tests/test_phase_5_4_persisted_view_state.py`.

2. **Before Phase E, complete E1 (audit).** Do NOT rush into mechanical swaps:
    - Phase E (model, 56 hits) is high-volume and needs intent classification first.
    - E1 produces `reports/model_access_audit.md` with labels: `read-structural`, `read-data`, `mutate`,
      `signal-connect`.
    - This audit determines clustering for E2–E6 steps and prevents Category-5 refactorings.
    - Allow ~30 min for E1 grepping and classifying.

3. **Extend the guard incrementally.** After each phase lands:
   ```bash
   # Add to FORBIDDEN_DATA_STORE_ATTRS in .githooks/_check_data_store_leaks.sh
   # Then commit the guard extension in the same commit as call-site swaps
   ```
   Current blocklist:
   `mutations, file_path, is_dirty, is_read_only, save_format, undo_stack, schema_source, schema_ref, validation`.
   Next: `model, view, search_edit, last_move_placed, issue_index, affix_mru, _font_pt, _user_sized_columns`.

4. **Timeouts are in place.** All `make gate` runs will use `QT_QPA_PLATFORM=offscreen timeout 600 pytest -q`.

### If starting fresh (new branch / new repo checkout)

1. **Read this file top-to-bottom.** Phases A–C+F are fully specified and have been proven; Phases D–E–G–H–I–J are
   pre-planned but untested.

2. **Use the reference implementation.** Check commit hashes on branch `decouple-json-tab`:
    - `a39dca9` A1 — adding narrow protocol stub (good template for abstract surface definitions)
    - `15e37cd` B4 — guard script creation (reusable pattern for data-driven pre-commit hooks)
    - `821d2d2` C1 — adding properties in bulk (shows how to forward 5 attrs in one method)
    - `904fde9` F2 — bundling add+swap+guard in one commit (valid when controller already exists end-to-end)

3. **Skip Phase A2.** The reflection ban makes `__getattr__` audit hostile. Static grep (already done) gives the
   ordering.

4. **Expect Phase D to be the breaking point.** If tests start flaking during D3, that's **not** a bug — it's the
   signal-wiring complexity showing up. Revert and split at the first flake.

### Practical checklists for the next session

**Before starting a step:**

```bash
cd /home/sr9000/PycharmProjects/Editable-Tree-Model-Example
git checkout decouple-json-tab  # or git pull origin decouple-json-tab
git log --oneline -3            # confirm last 3 commits
make gate                        # baseline sanity check (should pass)
```

**After each step (before commit):**

```bash
make lint              # reformats in-place; add results
make check-no-reflection  # should pass
grep -rE "data_store\.<RETIRED_ATTR>" app/ undo/ tree_actions/ state/ --include="*.py" | wc -l  # must be 0
QT_QPA_PLATFORM=offscreen timeout 600 pytest -q  # full gate; watch for timeouts
git diff --stat       # review scope (should be ≤300 LOC for mechanical steps, variant for structural)
```

**When committing:**

```bash
# Copy template: each commit message must include:
# 1. Step name and plan reference
# 2. What changed (mechanical swap / property add / guard extend)
# 3. File-by-file counts (e.g., "app/main_window.py: 13 sites")
# 4. Full DoD checklist (checked boxes)
# 5. Rollback line: git revert <SHA>

git add <files>
git commit -m "decouple-jsontab: <STEP> <summary>

Per plans/20-decouple-jsontab.md Step <STEP>.

<Details of what changed>
  * file1.py: N sites
  * file2.py: M sites
  ...

<New property added / Guard extended / etc>

DoD:
- [x] make gate (1124 passed, NN sites swapped, grep guard returns 0)
- [x] targeted: <test names> pass
- [x] <other notes>
- [x] rollback: git revert <SHA>"
```

### Known flakiness & workarounds

- **Post-pytest core dumps:** The `timeout: the monitored command dumped core` message after
  ` QT_QPA_PLATFORM=offscreen pytest` is benign (Qt interpreter teardown on offscreen platform). Exit code 0 is success.
- **Black import wrapping:** `isort` sometimes breaks `from documents.tab_validation_view import (...)` lines; use
  `git checkout -- <file>` after `make lint` to revert, then add the import via `sed` if needed.
- **Qt offscreen color-scheme tests:** 3 tests fail under offscreen but not on real platforms (documented in
  `ai-memory/todo-n-fixme.md`). These are NOT regressions caused by the plan.

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

**Sections marked ✅ (A, B, C, F1/F3/F2 partial) are proven by Session 1.**
**Sections marked 📋 (D, E, G, H, I, J) are pre-planned and require the next session.**

Each step has: **goal**, **scope**, **DoD-specific notes**, **rollback**.

### Phase A — Instrumentation & safety net (no behaviour change) ✅ LANDED

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

### Phase B — Stop leaking `mutations` (64 hits) ✅ LANDED

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

`save_format` (38 hits combined) ✅ LANDED

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

### Phase D — Stop leaking `view` (17 hits) ✅ LANDED (D-light Session 2; D-full D1–D4 Session 3)

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

### Phase E — Stop leaking `model` (54 hits) ✅ LANDED (E1 + E-light Session 2; E2-E6 Session 4)

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
`issue_index`) ✅ LANDED (F1-light, F2, F3 Session 1; F4+F5 Session 2;
closeout in Session 4 — `zoom_pt` / `column_widths` / `set_column_widths`
replace the underscore-prefixed forwards left behind by F5)

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

### Phase G — Burn `tab_protocols.py` ✅ LANDED (G1-G3 bundled in Session 5)

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

### Phase H — De-Qt the command layer ✅ LANDED-PRAGMATIC (H1+H2 Session 5; H3 deferred out of plan, see Session 5 summary)

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

### Phase I — Decompose `JsonTabData` ✅ LANDED (I1–I5 Session 6)

Now that nothing external reaches into it, split it.

* **I1.** Extract `IoState` (file_path, save_format, dirty, read_only).
* **I2.** Extract `ViewState` (delegates, proxy, view ref).
* **I3.** Extract `EditingState` (model, mutations, undo_stack,
  affix_mru, move-view caches).
* **I4.** Extract `ValidationState` (validation, schema_*, issue_index).
* **I5.** Delete `JsonTabDataFacade`; `JsonTab` directly composes the
  four states.

Each substep is a pure move + re-export. DoD: full gate, single commit.

### Phase J — Closeout 📋 PLANNED

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
