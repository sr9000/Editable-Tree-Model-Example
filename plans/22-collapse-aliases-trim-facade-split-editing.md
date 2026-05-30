# Plan 22 — Collapse aliases, trim the residual facade, split `EditingController`

**Source report:** `reports/documents_module_plan21_report.md` (8/10)
**Predecessor plan:** `plans/21-promote-substates-to-controllers.md` (Phases K–P, done)
**Branch suggestion:** `polish-documents`
**Targets:**
* `JsonTab` ≤ ~40 members (from 58), no duplicate accessor names.
* `documents/states/editing_controller.py` ≤ ~250 LOC (from 708), behaviour
  divided across focused collaborators.
* End-to-end gate green at every commit boundary.

---

## 0. Operating rules (carried over from Plans 20–21)

Unchanged from Plan 21 §0. Restated for self-containment:

1. **Baby steps.** ≤ ~300 LOC diff, 1 conceptual change, 1 commit per step.
2. **DoD gate.** `make lint && make check-no-reflection && make test`.
   Failure → fix in the same step or revert. No skips, no xfails.
3. **Timeouts.** `timeout 100 pytest -q`; `qtbot.waitSignal(..., timeout=2000)`.
4. **Git hygiene.** One commit per step; message names its `git revert <sha>`.
5. **No new `getattr` / `hasattr` / `TYPE_CHECKING`** outside the allowlist.
6. **No semantic change in a structural step.** Move/rename ≠ behaviour.
7. **Rollback contract.** Every step's commit message names its revert line.
8. **Test reach-in migrates in the same commit** that retires the member it
   touches (carried over from Plan 21 §0.8).

---

## 1. Why this plan exists

The Plan 21 assessment (8/10) left three named follow-ups:

> *collapsing aliases, trimming the residual facade, and pre-emptively
> splitting `EditingController`.*

Concretely, the audit found:

* **Duplicate accessor names.** `JsonTab.editing_state` and
  `JsonTab.validation_state` are pure aliases of `JsonTab.editing` /
  `JsonTab.validation`; the alias modules `documents/states/editing_state.py`
  and `documents/states/validation_state.py` exist only as
  `from … import X as Y`. Neither alias property has any external caller
  (verified: `grep '.editing_state'` / `.validation_state'` outside
  `documents/tab.py` → 0 hits).
* **Residual facade.** `JsonTab` carries 58 members, many thin routing
  wrappers (`_on_type_changed`, `_reopen_value_editor`, `_run_tree_action`,
  `_open_active_type_combo_popup`, `_snapshot`, `_set_dirty`,
  `_on_clean_changed`, `_size_hint_for_item`, `_on_current_changed`) that
  only forward to a controller.
* **`EditingController` is the next god-object.** At 708 LOC / 34 members it
  bundles five distinct responsibilities (command dispatch, inline-editor
  control, move/drag view-state, tree-action routing, diff/insert
  primitives).

This plan does not touch the external boundary (sealed by Plan 20) nor the
controller-promotion (done by Plan 21). It is pure internal hygiene.

---

## 2. Scope guard (what stays put)

* `JsonTab.view_state` **stays** — it is the passive widget/delegate
  container (`documents/states/view_state.py`), not an alias of
  `view_controller`. The report's "three alias pairs" framing over-counted;
  only **two** real aliases exist.
* `JsonTab.edit_name_or_value_from_enter` **stays reachable** — it is part of
  the `Document` protocol and is called by `tree_actions/context_menu.py`.
  It may forward to `EditingController`, but the name must remain on `JsonTab`.
* The `Document` protocol surface only changes where a member is *renamed*
  or *removed*; every change to `JsonTab`'s public surface is mirrored in
  `documents/document_protocol.py` in the same commit.
* `QUndoStack`, the mutation gateway, and `tree_actions/` wiring are out of
  scope (same as Plan 21 §6).

---

## 3. Phase R — Collapse the back-compat aliases

Smallest, lowest-risk work first.

* **R1. Delete `JsonTab.editing_state`.**
  Remove the property (no external callers). Confirm `grep -rn '\.editing_state\b'`
  returns only unrelated `QAbstractItemView.State.EditingState` hits.
  *DoD:* gate green; property gone.

* **R2. Delete the `documents/states/editing_state.py` alias module.**
  Repoint any importer to `documents.states.editing_controller.EditingController`.
  (Current importers: none outside the module itself — verify with
  `grep -rn 'states.editing_state'`.)
  *DoD:* gate green; file deleted; `grep` returns 0 importers.

* **R3. Delete `JsonTab.validation_state`.**
  Remove the property (no external callers).
  *DoD:* gate green; property gone.

* **R4. Retire the `documents/states/validation_state.py` alias module.**
  `documents/tab_init.py` imports `ValidationState` from it (line 10) and
  instantiates it (line 93). Swap both to
  `from documents.tab_validation import TabValidationController` and
  `tab._validation = TabValidationController(...)`. Delete the alias module.
  *DoD:* gate green; file deleted; `grep -rn 'states.validation_state'` → 0.

* **R5. Update `Document` protocol + report note.**
  The protocol never exposed the `*_state` aliases, so no protocol change is
  needed — confirm with `grep -n '_state' documents/document_protocol.py`.
  Add a one-line CHANGELOG/commit note recording the alias removal.
  *DoD:* gate green.

**Phase R outcome:** `JsonTab` loses 2 members (58 → 56); 2 modules deleted;
`documents/states/` holds only real controllers + `view_state` container.

---

## 4. Phase S — Trim the residual facade on `JsonTab`

Each step removes a thin wrapper by moving its only call-site onto the owning
controller (or wiring the signal/shortcut directly). Wrappers still reachable
from tests are migrated in the same commit (rule §8).

* **S1. Inline-edit wrappers → `EditingController`.**
  `_on_type_changed`, `_reopen_value_editor`, `_open_active_type_combo_popup`
  are one-liners forwarding to `self.editing.*`. Re-point their *internal*
  callers (signal connections set up in `documents/tab_setup.py` /
  `tab_init.py`, and `delegates/type_delegate.py`'s slot reference) to the
  controller method, then delete the `JsonTab` wrappers.
  Keep `edit_name_or_value_from_enter` on `JsonTab` (Document API) but make it
  a direct forwarder (already is).
  Migrate tests reaching `tab._reopen_value_editor` / `tab._on_type_changed`
  to `tab.editing.*` in the same commit.
  *DoD:* gate green; 3 wrappers gone; `grep` for them in tests → 0.

* **S2. Tree-action wrapper → controller.**
  `_run_tree_action` forwards to `self.editing.run_tree_action`. Re-point the
  shortcut/menu wiring to call `tab.editing.run_tree_action(...)` and delete
  the `JsonTab` wrapper.
  *DoD:* gate green; wrapper gone.

* **S3. IO wrappers → `IoController`.**
  `_snapshot`, `_set_dirty`, `_on_clean_changed` forward to `self.io.*`.
  Re-point internal callers (undo commands reach `tab._snapshot()`? verify —
  if so route via `tab.io.snapshot()`), migrate tests, delete wrappers.
  Keep `save` / `save_as` / `display_name` on `JsonTab` (Document API).
  *DoD:* gate green; 3 wrappers gone.

* **S4. Status/size wrappers → controllers.**
  `_size_hint_for_item` forwards to `documents.tab_status.size_hint_for_item`;
  `_on_current_changed` forwards to `documents.tab_status.on_current_changed`.
  Connect the `currentChanged` signal directly to a controller/`tab_status`
  callable in `tab_setup`, and call `size_hint_for_item` at its single
  delegate call-site. Delete both wrappers.
  *DoD:* gate green; 2 wrappers gone.

* **S5. Re-audit `JsonTab` member count.**
  `grep -cE "^    def |^    @property" documents/tab.py` must be ≤ 40.
  If above, list the remaining wrappers and either justify (Document API /
  Qt override / `__init__`) or schedule another S-step.
  *DoD:* gate green; member count documented in commit body.

**Phase S outcome:** ~9 wrappers removed (56 → ~45–47), leaving property
forwarders (Document surface), Qt overrides (`eventFilter`, `closeEvent`,
`__init__`), and the genuinely-public API.

---

## 5. Phase T — Split `EditingController` pre-emptively

`EditingController` becomes a thin **coordinator** that constructs and owns
four focused collaborators. The public method names callers already use
(`push_*`, `run_tree_action`, `on_type_changed`, `apply_move_view_state`,
`diff_apply`, …) stay on `EditingController` as one-line delegations so the
`Document` protocol and `tab.editing.*` call-sites are unchanged. Behaviour
moves; the surface does not.

Proposed collaborators (each in `documents/states/editing/`):

| Collaborator              | Absorbs (current line ranges)                                   | ~LOC |
|---------------------------|-----------------------------------------------------------------|------|
| `CommandDispatcher`       | `make_label`, all 10 `push_*` (L93–411)                         | ~320 |
| `InlineEditController`    | `on_type_changed`, `reopen_value_editor`, `edit_name_or_value_from_enter`, `open_active_type_combo_popup` (L413–492) | ~80 |
| `MoveViewState`           | `collect_expanded_paths`, `capture_move_view_state`, `sort_move_paths`, `_apply_relative_expansion_mapping`, `_restore_selection_paths`, `restore_selection_at_paths`, `apply_move_view_state`, `on_undo_index_changed` (L494–653) | ~160 |
| `EditingController` (core)| ctor + `run_tree_action`, `do_insert_*`, diff/insert delegation (L655–705) + the four collaborators | ~150 |

* **T1. Create the `documents/states/editing/` package** with an empty
  `__init__.py` and move the `TreeAction` enum + `_ACTIONS` table into
  `editing/tree_actions.py` (pure data, no behaviour). Re-export `TreeAction`
  from `editing_controller` for back-compat (`from .editing.tree_actions import TreeAction`).
  *DoD:* gate green; `from documents.states.editing_controller import TreeAction`
  still resolves.

* **T2. Extract `MoveViewState`** (the lowest-coupling cluster — it only reads
  `tab.view`, `tab.model`, `tab.view_controller`). Move the 8 methods verbatim
  into `editing/move_view_state.py`; `EditingController` holds a
  `self._move = MoveViewState(tab, history_provider)` and forwards
  `capture_move_view_state` / `apply_move_view_state` / `restore_selection_at_paths`
  / `on_undo_index_changed`. The `_move_view_state_by_cmd_id` dict access
  (currently `tab.editing.history._move_view_state_by_cmd_id`) is passed in
  rather than reached through `tab`.
  *DoD:* gate green; the heavy move/drag suites
  (`tests/test_keyboard_multimove.py`, `tests/test_multi_action_semantics.py`)
  pass; `editing_controller.py` shrinks ~160 LOC.

* **T3. Extract `InlineEditController`** (`on_type_changed`,
  `reopen_value_editor`, `edit_name_or_value_from_enter`,
  `open_active_type_combo_popup`). `EditingController` forwards.
  *DoD:* gate green; `tests/test_type_editing.py`,
  `tests/test_secret_editors.py` pass; ~80 LOC moved.

* **T4. Extract `CommandDispatcher`** (`make_label` + all 10 `push_*`). This
  is the largest move. `EditingController.push_X(...)` becomes
  `return self._commands.push_X(...)`. The dispatcher needs `tab` (for
  `editability`, `model`, `undo_stack`, `view_controller`, `show_status`) and
  the `MoveViewState` instance (for `push_move_rows_anchor`'s
  `capture_move_view_state` call) — inject both at construction.
  Split into one commit per logical sub-group if the diff exceeds ~300 LOC:
  T4a move/rename/value/type; T4b insert/remove/sort/switch-case.
  *DoD:* gate green after each sub-commit; undo/redo suites
  (`tests/test_undo_redo_scenario.py`, `tests/test_typed_undo_perf.py`) pass.

* **T5. Slim the `EditingController` core.** What remains: ctor wiring the four
  collaborators, `run_tree_action`, `do_insert_sibling_before/after`,
  `do_insert_child`, and the diff/insert delegation (`diff_applier`,
  `diff_apply`, `emit_row_changed`, `insert_typed_item`, `commit_set_data`).
  Optionally move the diff/insert quintet behind the existing `DiffApplier`
  property only (it already wraps `self._diff_applier`) — keep as-is if the
  delegation is trivial.
  *DoD:* gate green; `wc -l editing_controller.py` ≤ ~250.

* **T6. Collaborator construction via a small context.** To avoid each
  collaborator re-deriving peers from `tab`, pass a tiny frozen
  `EditingContext` dataclass (holds `tab`, `move_view_state`,
  `history_provider`) — mirrors Plan 21's risk-register mitigation. No cyclic
  imports (collaborators live in separate files).
  *DoD:* gate green; no `getattr`/`hasattr` introduced.

**Phase T outcome:** `editing_controller.py` 708 → ~250 LOC; four single-
responsibility collaborators; `tab.editing.*` and `Document` surface unchanged.

---

## 6. Phase U — Closeout

* **U1. Update `ai-memory/{repo-map,pros-n-cons,todo-n-fixme}.md}`** to reflect
  the collapsed aliases, the slimmer facade, and the `editing/` package.
* **U2. Write the closing report**
  (`reports/documents_module_plan22_report.md`) with before/after metrics and
  an updated score.
* **U3. Merge `polish-documents` → `master`; tag `documents-polish-complete`.**

---

## 7. Per-step DoD checklist (copy into each commit body)

```
DoD:
- [ ] make lint
- [ ] make check-no-reflection
- [ ] make test                 # 1124+ pass; tests migrated in same commit
- [ ] targeted subset:          pytest -q <files relevant to this step>
- [ ] grep guard:               retired member has 0 references outside this
                                commit's deletions
- [ ] JsonTab members:          grep -cE "^    def |^    @property" documents/tab.py  (must not grow)
- [ ] editing_controller LOC:   wc -l documents/states/editing_controller.py (Phase T: trending down)
- [ ] rollback:                 git revert <this-sha>
```

---

## 8. Risk register

| Risk                                                                              | Mitigation                                                                                                                       |
|-----------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------|
| Collaborators need peer access (e.g. `CommandDispatcher` → `MoveViewState`)        | Inject peers via the `EditingContext` dataclass at construction; never reach through `tab.editing._move`.                        |
| `_move_view_state_by_cmd_id` lives on `history`; moving methods loses the path     | Pass a `history_provider` callable/ref into `MoveViewState`; keep the dict on `TabHistoryController` unchanged.                  |
| Signal/slot re-wiring in `tab_setup`/`tab_init` breaks lazy connections            | Each S-step re-wires *and* deletes the wrapper in one commit; smoke test (`tests/test_smoke_mainwindow.py`) is in the subset.    |
| `delegates/type_delegate.py` references `JsonTab._on_type_changed` by name (slot)  | S1 updates the connection target and the delegate's doc-comment; the `interactive` backchannel is unchanged.                     |
| `TreeAction` import path changes break `documents/tab.py` re-export                | T1 re-exports `TreeAction` from `editing_controller`; `grep` confirms `from documents.states.editing_controller import TreeAction` still resolves. |
| Phase T diff too large in one commit                                               | Split T4 into T4a/T4b (≤300 LOC each); each is independently gated.                                                              |
| Test reach-in for retired wrappers (`_reopen_value_editor`, `_snapshot`, …)         | Migrate in the same commit (rule §8); subset includes the 8 test files identified in the audit.                                 |

---

## 9. Quantitative success criteria

Done when **all** hold simultaneously:

| Metric                                            | Today (8/10) | Target  |
|---------------------------------------------------|--------------|---------|
| `JsonTab` methods + properties                    | 58           | ≤ 40    |
| Duplicate accessor names on `JsonTab`             | 2            | 0       |
| Alias modules in `documents/states/`              | 2            | 0       |
| `wc -l documents/states/editing_controller.py`    | 708          | ≤ 250   |
| `EditingController` responsibilities (clusters)   | 5 in 1 file  | 1 + 3 collaborators |
| `Document` protocol surface                       | stable       | stable (no external regression) |
| Test suite                                        | 1124 ✅       | 1124+ ✅ |
| New `getattr`/`hasattr`/`TYPE_CHECKING`           | 0            | 0       |

If any metric refuses to converge, split the offending phase or document it
as "deferred to Plan 23" — same escape hatch Plans 20–21 used.

---

## 10. Recommended entry point

**Start with Phase R** (alias collapse): zero external callers, two property
deletions and two module deletions, each independently revertible. It clears
the cheapest debt and warms up the gate before the facade trim (S) and the
larger controller split (T). Tackle **Phase T2 (`MoveViewState`)** first
within Phase T — it is the lowest-coupling cluster and proves the
collaborator-extraction pattern before the big `CommandDispatcher` move (T4).

---

## 11. Sequencing & cost

| Phase     | Commits (est.) | Risk   | Comment                                            |
|-----------|----------------|--------|----------------------------------------------------|
| R         | 4–5            | Low    | Alias deletions; no external callers.              |
| S         | 5              | Low    | Wrapper removals; mechanical re-wiring.            |
| T         | 6–7            | Medium | Controller split; T4 may split into T4a/T4b.       |
| U         | 3              | Low    | Docs + report + tag/merge.                          |
| **Total** | **~18–20**     | —      | Smaller than Plan 21; no test-data migration wave. |
