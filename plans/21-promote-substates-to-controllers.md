# Plan 21 — Promote substates to controllers; shrink `JsonTab` to a QWidget

**Source report:** `reports/jsontab_god_object_followup_report.md`
**Severity rating in report:** 5 / 10 (boundary refactor on top of duct-taped monolith)
**Predecessor plan:** `plans/20-decouple-jsontab.md` (Phases A–I complete)
**Branch suggestion:** `promote-substates`
**Target:** `JsonTab` ≤ ~120 LOC / ≤ ~20 members, end-to-end gate green.

---

## 0. Operating rules (carried over from Plan 20 §0)

Plan 20's operating rules apply unchanged. Restated for self-containment:

1. **Baby steps.**  ≤ ~300 LOC diff, 1 conceptual change, 1 commit per step.
2. **DoD gate.**  `make lint && make check-no-reflection && make test`.
   Failure → fix in the same step or revert.  **No skips, no xfails.**
3. **Timeouts.**  `timeout 100 pytest -q`; `qtbot.waitSignal(..., timeout=2000)`.
4. **Git hygiene.**  One commit per step, message format identical to Plan 20.
5. **No new `getattr` / `hasattr` / `TYPE_CHECKING`** outside the allowlist.
6. **No semantic change in a structural step.**  Move/rename ≠ behaviour.
7. **Rollback contract.**  Every step's commit message names its
   `git revert <sha>` line.

**New rule introduced by Plan 21:**

8. **Test reach-in is allowed to break, but only in batches that the
   same commit migrates.**  Plan 20 §6 forbade test edits to keep tests
   stable across the long refactor. Plan 21 cannot finish without
   deleting `tab.data_store.*` access; the policy is therefore relaxed
   to *"every step that retires a `data_store.<attr>` property must
   migrate every test reaching that attr in the same commit"*. The
   gate is still green at every commit boundary.

---

## 1. Why this plan exists

Plan 20 closed every external `data_store.*` leak (212 → 0) but the
`JsonTab` god-router grew from 407 LOC / ~60 methods to 607 LOC / 117
methods because every retired leak was replaced with a typed `@property`
forward on `JsonTab`. The substates added in Phase I are passive
containers — behaviour still lives on `JsonTab` or on `tab_*.py` free
functions that take `tab` as their first arg.

Plan 21's goal is to **actually decouple** by:

* promoting substates to **active controllers** that own both data and
  behaviour;
* moving `tab_*.py` free-function modules into methods on those
  controllers;
* deleting the typed `@property` forwards from `JsonTab` once the only
  remaining callers are tests, which are migrated in the same commit;
* shrinking `JsonTab` to a thin QWidget that owns 4 controllers and
  wires signals (target ≤ 120 LOC / ≤ 20 members).

---

## 2. Target architecture

```
┌──────────────────────────────────────────────────────────────┐
│  external callers (app/, undo/, tree_actions/, …)            │
│    ────► depend ONLY on documents.document_protocol.Document │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│  documents/tab.py :: JsonTab(QWidget, Document)              │
│    ≤ ~120 LOC, ≤ ~20 members                                 │
│    • __init__ / closeEvent / eventFilter                     │
│    • io / view / editing / validation         (4 controllers)│
│    • dirtyChanged / schemaChanged / …         (Qt signals)   │
│    • save / save_as / display_name            (Document API) │
└──────────────────────────────────────────────────────────────┘
   │              │                  │                  │
   ▼              ▼                  ▼                  ▼
IoController  ViewController   EditingController  ValidationController
(was         (was             (was               (was
 IoState +    ViewState +      EditingState +     ValidationState +
 tab_io.py +  tab_paths.py +   tab_commands.py +  tab_validation_view.py)
 save funcs)  apply_filter)    tab_editing.py +
                               tab_move_view_state.py +
                               tab_tree_actions.py)
```

Each controller owns: its substate fields (Plan 20 Phase I),
the helper functions that used to live in `tab_*.py` modules, and
publishes its own typed signals.  `JsonTabAppearanceController`
already exists as a class — it absorbs the `zoom_*` / `set_*_font_*`
routing methods currently on `JsonTab`.

---

## 3. Phased step list

Each step has: **goal**, **scope**, **DoD notes**, **rollback**.

### Phase K — Document protocol becomes the external return type

The `Document` protocol exists (`documents/document_protocol.py`) but
nothing returns it. Make it the real seam so external callers can be
typed against `Document` rather than the concrete `JsonTab` widget.

* **K1. Flesh out `Document` to match the current external surface.**
  Audit every `tab.X` method/property called from `app/`, `undo/`,
  `tree_actions/`, `state/`. Declare each on the `Document` protocol
  (with Qt signals as `ClassVar[Signal]`). No callers change yet.
  *DoD:* gate green.

* **K2. Type `app/main_window.py` tab-lookup helpers as `Document`.**
  `_current_tab() -> Document | None` (was `JsonTab | None`). Mechanical.
  *DoD:* gate green.

* **K3. Type the rest** (`app/main_window_actions.py`, `app/history.py`,
  `app/tab_lifecycle.py`, `app/validation_dock.py`, `state/view_state.py`,
  `tree_actions/_tab_lookup.py`). One commit per file or per cluster.
  *DoD:* gate green after each.

* **K4. Forbid `JsonTab` as an import target outside `documents/`** via
  pre-commit regex (parallel to the existing `_check_data_store_leaks.sh`).
  *DoD:* the regex matches zero files.

### Phase L — Promote `IoController`

`IoState` + `tab_io.py` (save/save_as/snapshot) merge into a single
controller that owns IO behaviour.

* **L1. Rename `IoState` → `IoController`; move `save` / `save_as` /
  `_snapshot` onto it.**  `JsonTab.save` / `.save_as` become one-liners
  forwarding to `self.io.save()` / `.save_as()` (and they already do —
  this step just makes the receiver canonical). Delete `tab_io.py`.
  *DoD:* gate green; `documents/tab_io.py` is gone; `JsonTab` shrinks
  by ~6 LOC.

* **L2. Migrate test reach-in for `tab.data_store.io`.**  All test
  references become `tab.io`. The `data_store.io` @property forward
  on `JsonTabData` is deleted.
  *DoD:* gate green; grep returns 0 for `data_store.io`.

* **L3. Drop `JsonTab.file_path / .save_format / .is_dirty` properties.**
  Callers (now typed against `Document`) reach them via `tab.io.file_path`
  etc. Tests migrated together. Update the `Document` protocol to
  expose them via `io` only.
  *DoD:* gate green; the 3 properties are gone from `JsonTab`.

### Phase M — Promote `ViewController`

`ViewState` + `tab_paths.py` + `_apply_filter` + the path helpers on
`JsonTab` collapse into one controller.  `DocumentView` (the existing
viewport controller from Plan 20 D1) merges in.

* **M1. Merge `DocumentView` into `ViewController`.**  Single class
  owning ui/view/proxy/search_edit/delegates *and* selection/expand/scroll
  *and* path helpers (`index_path`, `index_from_path`). Delete
  `documents/tab_paths.py`. Move `_apply_filter` / `apply_filter` /
  `set_filter_text` onto the controller.
  *DoD:* gate green; `tab_paths.py` is gone.

* **M2. Migrate test reach-in** for `tab.data_store.view*`, `proxy`,
  `search_edit`, `ui`, `*_delegate`.  ~30 sites across ~20 test files.
  *DoD:* gate green; grep returns 0 for the migrated attrs.

* **M3. Drop the corresponding `JsonTab` properties**
  (`view`, `view_controller`, `search_edit`, `_proxy_to_source`,
  `_source_to_view`, `_apply_filter`, `apply_filter`, `column_widths`,
  `set_column_widths`, `_index_path`, `_index_from_path`,
  `_qualified_name`, `_severity_provider`). External access goes
  through `tab.view.X`.
  *DoD:* gate green; `JsonTab` shrinks by ~30 LOC.

### Phase N — Promote `EditingController`

The biggest step. Merges `EditingState` + `tab_commands.py` (10 push_*
functions) + `tab_editing.py` + `tab_move_view_state.py` +
`tab_tree_actions.py` into one controller.

* **N1. Rename `EditingState` → `EditingController` and migrate the
  `push_*` helpers from `tab_commands.py`.**  They become methods on the
  controller.  `JsonTab.push_X(...)` becomes `self.editing.push_X(...)`
  forwarders for one step (delete the file after N6).
  *DoD:* gate green.

* **N2. Migrate the `tab_editing.py` helpers** (`on_type_changed`,
  `reopen_value_editor`, `edit_name_or_value_from_enter`,
  `open_active_type_combo_popup`) onto `EditingController`. Delete
  the file.
  *DoD:* gate green.

* **N3. Migrate the `tab_move_view_state.py` helpers** onto the
  controller. Delete the file.
  *DoD:* gate green; the heavy move/drag test suite must pass.

* **N4. Migrate the `tab_tree_actions.py` helpers** onto the controller.
  Delete the file.
  *DoD:* gate green.

* **N5. Migrate the diff/insert primitives**
  (`_diff_apply`, `_emit_row_changed`, `_insert_typed_item`,
  `commit_set_data`) onto `EditingController`. Delete the
  `DiffApplier` wrapper if it becomes trivial.
  *DoD:* gate green.

* **N6. Drop the corresponding `JsonTab` properties / forwarders.**
  At minimum: `model`, `mutations`, `undo_stack`, `affix_mru`,
  `last_move_placed`, `issue_index`, the 10 `push_*`, the 3
  `insert_sibling_*`, the 5 move-view helpers. External callers use
  `tab.editing.X` (via the `Document` protocol).
  *DoD:* gate green; `JsonTab` shrinks by ~80 LOC. Tests migrated.

### Phase O — Promote `ValidationController` & absorb appearance/editability

* **O1. Rename `TabValidationController` → `ValidationController`;**
  merge `tab_validation_view.py` (goto-issue navigation) into it. Delete
  the file.  `ValidationState` alias is retired in the same commit.
  *DoD:* gate green.

* **O2. Migrate `JsonTab.validation / .schema_source / .schema_ref /
  .issue_index / .goto_validation_issue / ._severity_provider /
  ._on_validation_changed`** to use `tab.validation.X`. Drop the
  `JsonTab` properties. Tests migrated.
  *DoD:* gate green.

* **O3. Absorb appearance routing.**  The 14 `zoom_* / set_*_font_* /
  set_theme / apply_font_profile / resize_key_columns /
  _scale_columns_for_font / _set_font_pt / _sync_icon_size_with_font /
  _on_model_reset` methods on `JsonTab` move to
  `JsonTabAppearanceController` (which already exists).
  Expose as `tab.appearance`.
  *DoD:* gate green; `JsonTab` shrinks by ~14 LOC.

* **O4. Absorb editability.**  `set_read_only` / `is_read_only` move to
  `JsonTabEditabilityController` (already exists); exposed as
  `tab.editability`.
  *DoD:* gate green.

### Phase P — Delete `JsonTabData`

After K-O the only remaining residents of `JsonTabData` are the four
controllers and two cross-cutting controllers. Move them onto `JsonTab`
directly and delete `JsonTabData`.

* **P1. Move the 6 controller references from `JsonTabData` to `JsonTab`
  attributes.**  `tab.data_store.io` → `tab.io` (etc.).  `JsonTabData`
  loses its fields and becomes empty.
  *DoD:* gate green.

* **P2. Migrate all remaining test reach-in** for `tab.data_store.*`.
  After K-O most of these are already gone; this step closes the long
  tail (`tab.data_store.editability`, `.appearance`, `._host`, …).
  *DoD:* gate green; `grep -r 'data_store' tests/` returns 0.

* **P3. Delete `documents/tab_data.py`** and the `tab.data_store`
  attribute itself. The pre-commit guard collapses to a single rule:
  "`data_store` is forbidden anywhere".
  *DoD:* gate green; `documents/tab_data.py` is gone; ~250 LOC deleted.

### Phase Q — Closeout

* **Q1. Update `ai-memory/{repo-map.md, pros-n-cons.md, todo-n-fixme.md}`.**
* **Q2. Write the closing report** (`reports/jsontab_god_object_closed.md`)
  with before/after metrics.
* **Q3. Tag `decouple-jsontab-truly-complete`; merge to `master`.**

---

## 4. Per-step DoD checklist (copy into each commit body)

```
DoD:
- [ ] make lint
- [ ] make check-no-reflection
- [ ] make test               # 1124+ pass; tests in same commit if attr retired
- [ ] targeted subset:        pytest -q <files relevant to this step>
- [ ] grep guard:             zero `tab.data_store.<retired-attr>` outside this
                              commit's deletions
- [ ] JsonTab LOC trending:   wc -l documents/tab.py (must not grow)
- [ ] rollback:               git revert <this-sha>
```

---

## 5. Risk register

| Risk                                                                                                                   | Mitigation                                                                                                                                                                  |
|------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Test migration breaks ~200 tests per phase                                                                             | Migrate tests in the *same* commit that retires the property; never leave a step with the guard regex matching the retired attr in tests.                                   |
| Controller methods need access to peer controllers (e.g. EditingController needs ViewController for selection restore) | Pass a tiny `DocumentContext` dataclass at construction time (holds weak refs to peer controllers).  No cyclic imports because controllers live in separate files.          |
| `DiffApplier` is genuinely shared between several mutation paths                                                       | Keep it as a standalone class but make it a property of `EditingController`; do not inline.                                                                                 |
| Plan stalls between phases                                                                                             | Each phase boundary is independently mergeable to `master` (same as Plan 20).                                                                                               |
| `Document` protocol needs Qt signals as class members                                                                  | Use `ClassVar[Signal]` annotations; the gate already accepts this pattern (`documents/view_controller.py::DocumentView.viewportRequested`).                                 |
| 61 test files reach into `data_store` — daunting blanket grep                                                          | Phase K's typing-only steps allow tests to keep working; actual retirement is staged per-attr (L2, M2, N6, O2, P2) so each test-edit batch is bounded.                      |
| Helper module deletion (`tab_io.py`, `tab_paths.py`, …) breaks `from documents.X import Y` in other files              | Each deletion step ends with a `grep -rE "from documents\.<deleted_module>"` confirming no remaining importers.  Add a back-compat shim only if a deep dependency surfaces. |

---

## 6. Out of scope (explicitly)

* **Replacing Qt's `QUndoStack`.**  `EditingController` will continue to
  wrap it via `TabHistoryController`.
* **Repackaging `documents/` into multiple Python packages.**  Possible
  follow-up, not in Plan 21.
* **Reworking `tree/model.py` to expose a path-based mutation API.**
  That is the open `H3` follow-up flagged in Plan 20; Plan 21 lets
  `EditingController` keep talking `QAbstractItemModel` internally.
* **Rewriting `tree_actions/`.**  These already go through the
  mutation gateway after Plan 20 Phase B; Plan 21 only updates their
  type annotations (Phase K).

---

## 7. Quantitative success criteria

The plan is "done" when **all** of these hold simultaneously:

| Metric                              | Today  | Target  |
|-------------------------------------|--------|---------|
| `wc -l documents/tab.py`            | 607    | ≤ 120   |
| `JsonTab` methods + properties      | 117    | ≤ 20    |
| `tab_*.py` free-function modules    | 8      | 0       |
| `tab.data_store.*` reads (anywhere) | 247    | 0       |
| External imports of `JsonTab`       | many   | 0       |
| External imports of `Document`      | 0      | many    |
| Test suite                          | 1124 ✅ | 1124+ ✅ |
| `documents/tab_data.py`             | exists | deleted |

If any single metric refuses to converge, the corresponding phase is
split or its scope is documented as "deferred to Plan 22" — same
escape hatch Plan 20 used for D3 and H3.

---

## 8. Estimated cost & sequencing

| Phase     | Commits (est.) | Risk level | Comment                                                                |
|-----------|----------------|------------|------------------------------------------------------------------------|
| K         | 4–6            | Low        | Mechanical typing swaps; no behaviour change.                          |
| L         | 3              | Low        | `IoState` is the smallest substate.                                    |
| M         | 3              | Medium     | `ViewState` touches the QTreeView wiring; rely on existing tests.      |
| N         | 6              | **High**   | The big one; ~80 LOC lost from `JsonTab`, deep test migration.         |
| O         | 4              | Medium     | Validation + appearance + editability are already partially extracted. |
| P         | 3              | Medium     | `data_store` deletion; last test-migration wave.                       |
| Q         | 3              | Low        | Docs + tag + merge.                                                    |
| **Total** | **~26**        | —          | Comparable to Plan 20 (~22 substantive commits).                       |

Estimated wall-clock: 5–7 focused sessions, same cadence as Plan 20.

---

## 9. Relationship to Plan 20

Plan 20 was a **boundary refactor** (external decoupling). Plan 21 is
an **internal refactor** (god-object decomposition). Together they
implement all six remediation steps from the original
`reports/documents_module_design_report.md`:

| Predecessor recommendation                         | Plan 20    | Plan 21   |
|----------------------------------------------------|------------|-----------|
| 1. Remove `tab_protocols.py`                       | ✅ Phase G  | —         |
| 2. Untangle Domain from UI                         | ⚠️ partial | ✅ Phase N |
| 3. Decompose `JsonTabData`                         | ✅ Phase I  | ✅ Phase P |
| 4. Discrete TDD path (Phases 1–4 in report)        | ✅ A–H      | ✅ K–O     |
| 5. Command independence (no `tab.data_store.view`) | ✅ D-full   | ✅ Phase M |
| 6. Isolate Feature Layers (Document protocol)      | ⚠️ stub    | ✅ Phase K |

Phase J of Plan 20 (closeout: ai-memory, tag, merge) is rolled into
Plan 21's Phase Q so the two plans land as one final architectural
milestone.

---

## 10. Recommended entry point

**Start with Phase K1 (flesh out `Document` protocol)** — it is pure
documentation/typing, has no behaviour risk, and produces the type
target every subsequent phase will check against. K1 can be completed
in a single sitting and gives the reviewer a clear picture of the
external surface area before any retirement begins.

Then **Phase L** (smallest substate) as a low-risk proof of the
controller-promotion pattern before tackling the big one (Phase N).
