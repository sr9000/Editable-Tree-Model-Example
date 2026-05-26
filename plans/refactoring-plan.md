# FINAL PLAN — Decoupling and Splitting the God Objects

Status: ratified (supersedes plans 00–05)
Targets: `delegates/value.py`, `delegates/name_delegate.py`, `delegates/type_delegate.py`,
`documents/tab.py`, `app/main_window.py`, and their immediate collaborators.

This plan synthesises the original three-phase roadmap (plans 00–03) with every
weakness raised in the independent review (plan 04) and the concessions/adjustments
documented in the defence (plan 05). It is the single source of truth for the
refactor; earlier plan files remain only as historical context.

---

## 0. Guiding Principles

1. **Stable façades first, internals later.** Any move of code out of a god
   object must be preceded by a stable interface on that god object. External
   call sites (tests, `tree_actions/`, `undo/`, `app/`) continue to see the same
   public API while the implementation migrates behind it. This eliminates the
   churn the reviewer flagged in Issue 17.
2. **Unidirectional dependencies.** Layers:
   `UI shell  →  Presenters / Edit Contexts  →  Document/Model  →  IO / Schema / Pure helpers`.
   No upward imports. Lower layers communicate up only through Qt signals or
   injected protocols.
3. **Dependency injection, not parent crawling.** Delegates, controllers, and
   presenters receive their collaborators in their constructor (or via setters
   called from the wiring module). The runtime widget tree is never walked to
   discover behaviour.
4. **Qt-aware controllers are QObject subclasses.** Anything that owns a
   `QTimer`, `QUndoStack`, or Qt connection inherits from `QObject` with a
   parent set, so Qt’s ownership graph drives deterministic cleanup
   (addresses review Issue 6).
5. **Measure coupling, not lines.** LOC targets are abandoned. The acceptance
   metrics are: zero parent crawling in delegates, zero direct private-attribute
   access from `tree_actions/` to `JsonTab`, and explicit contract tests per
   extracted seam (addresses review Issues 10 and 14).
6. **Test-suite green at every commit.** Each commit is atomic, runs `pytest`
   with a targeted subset plus the full suite, and uses precise grep checks
   that exclude `.md`, `__pycache__`, and `.pytest_cache`.

---

## 1. Ownership Map (Target State)

| Layer                       | Class / module                                   | Owns                                                                                       | Must NOT own                                |
|-----------------------------|--------------------------------------------------|--------------------------------------------------------------------------------------------|---------------------------------------------|
| UI shell                    | `MainWindow`                                     | window geometry, generated menu/action wiring, DnD, status bar, dialog entry points        | tab lifecycle data, schema state, settings  |
| UI shell                    | `ValidationDock`                                 | dock widget visuals                                                                        | schema attach logic                          |
| Presenter                   | `TabLifecyclePresenter` (`app/tab_lifecycle.py`) | the `_closed_tabs_stack`, add/close/reopen flows, dirty-close prompt                       | the `QTabWidget` itself (injected)          |
| Presenter                   | `DockValidationPresenter` (`app/validation_presenter.py`) | schema-attach dialog flow, registry reload reactions, issue→view navigation         | dock widget construction                    |
| Presenter                   | `AppSettingsPresenter` (`app/app_settings.py`)   | edit-limit thresholds, secret-prefix list, QSettings IO                                    | menu wiring                                  |
| Edit context (presenter)    | `DelegateEditContext` (`delegates/edit_context.py`) | sync `commit(index,value,role) -> EditResult`, status sink, affix MRU, icon provider     | nothing Qt-tree-related                      |
| Document                    | `JsonTab`                                        | view+model composition, public façade (`undo_stack`, `commit_set_data`, `push_*`, paths)   | direct timer/undo/IO implementation         |
| Document controller         | `TabValidationController` (`documents/tab_validation.py`, `QObject`) | schema ref/instance, debounce timer, issue index, registry binding & release  | schema persistence                           |
| Document controller         | `TabHistoryController` (`documents/tab_history.py`, `QObject`) | `QUndoStack`, command→view-state map, expansion capture                       | mutation method bodies                       |
| Document controller         | `TabIOController` (`documents/tab_io_controller.py`, `QObject`) | file_path, save_format, dirty flag, save/load orchestration via `documents/tab_io.py` | atomic IO primitives                         |
| Mutation seam               | `DocumentMutationGateway` (`documents/mutation_gateway.py`) | `commit_set_data`, `push_insert_rows`, `push_edit_value`, `push_remove_rows`, `push_move_rows_anchor`, `begin_macro/end_macro` | view state, schema state |
| IO / pure                   | `documents/tab_io.py`, `documents/tab_paths.py`, `documents/tab_status.py`, `documents/tab_setup.py` | unchanged primitives                                                | Qt presentation                             |

**Reverse-dependency policy:**

- Controllers may not import `JsonTab`.
- Presenters may not import `MainWindow`.
- `delegates/*` may not import from `documents/` or `app/`.
- Test-only access continues through `JsonTab` façade methods/properties.

---

## 2. Pre-Phase — Define Interfaces (Phase 0)

Goal: land the seams before any code moves, so subsequent extractions are
internal swaps.

### Commit 0.1 — `delegates/edit_context.py`

Add a protocol module:

```python
# delegates/edit_context.py
from dataclasses import dataclass
from typing import Protocol, Optional, Callable
from PySide6.QtCore import QModelIndex

@dataclass(frozen=True)
class EditResult:
    accepted: bool
    reopen_value_editor: bool = False  # replaces JsonTypeDelegate._interactive contract

class DelegateEditContext(Protocol):
    def commit(self, index: QModelIndex, value, role: int) -> EditResult: ...
    def notify_status(self, message: str, timeout_ms: int = 0) -> None: ...
    def icon_provider(self): ...           # may return None
    def affix_mru(self): ...               # returns the MRU container or None
    def confirm_large_text_edit(self, parent) -> bool: ...
    def confirm_large_binary_edit(self, parent) -> bool: ...
```

Plus a `DefaultEditContext` that wraps a bare `QAbstractItemModel`:
`commit` forwards to `model.setData`, `notify_status` is a no-op, MRU and icon
provider are `None`, and the confirm helpers fall back to `QMessageBox`. This
gives delegates a reliable standalone fallback (resolves review Issue 4) and
removes any signal-receiver introspection.

**DoD**

- `python -m py_compile delegates/edit_context.py`
- new test `tests/test_delegate_edit_context.py::test_default_context_setdata`
  exercises `DefaultEditContext.commit` against a `QStandardItemModel`.

### Commit 0.2 — `documents/mutation_gateway.py` façade

Create `DocumentMutationGateway` as a thin **forwarding façade** over the
current `JsonTab` mutation API. `JsonTab` gets a `self.mutations` attribute of
this type, exposing exactly:

`commit_set_data`, `push_insert_rows`, `push_edit_value`,
`push_remove_rows`, `push_move_rows_anchor`, `begin_macro`, `end_macro`,
`index_path`, `index_from_path`, `source_to_view`.

For this commit each method simply calls the existing `JsonTab` implementation.
The point is to publish the seam so the rest of the codebase can migrate to
`tab.mutations.*` before Phase 2 moves the implementation.

**DoD**

- `pytest tests/` green.
- `grep -RIn "tab\.mutations" documents app tree_actions undo --include='*.py'`
  shows at least one import in `documents/tab.py`.

### Commit 0.3 — Migrate `tree_actions/`, `undo/commands.py`, `app/history.py` to the gateway

Mechanical search-and-replace from `tab.push_*`, `tab.commit_set_data`,
`tab._index_from_path`, `tab._source_to_view`, `tab.undo_stack.beginMacro` to
their `tab.mutations.*` and `tab.history.*` (the latter introduced in 0.4)
equivalents. Existing `JsonTab` methods stay as deprecated shims that delegate
to the gateway, so tests do not yet need rewriting (Issue 16).

**DoD**

- `grep -RIn "tab\._index_from_path\|tab\._source_to_view\|tab\.push_\|tab\.commit_set_data" tree_actions undo app --include='*.py' --exclude-dir=__pycache__`
  returns zero hits in production code (tests excluded).
- Full `pytest tests/` green.

### Commit 0.4 — Publish history seam on `JsonTab`

Add `JsonTab.history` returning an object with `undo_stack`, `apply_expanded_relative_paths`,
`iter_expanded_relative_paths`, `register_view_state(cmd_id, state)`. Backed by
existing private fields. Like 0.2 this is a pure façade commit.

**DoD**

- New unit test asserts `tab.history.undo_stack is tab.undo_stack`.
- Full suite green.

After Phase 0, **no behaviour has changed**, but every subsequent extraction is
a private implementation swap behind a stable seam.

---

## 3. Phase 1 — Decouple All Editing Delegates Together

Resolves review Issues 1, 2, 3, 4, 5.

### Commit 1.1 — Inject `DelegateEditContext` into the three delegates

Modify constructors of `ValueDelegate`, `NameDelegate`, and `JsonTypeDelegate`
to accept `edit_context: DelegateEditContext` (keyword-only, default `None`).
When `None`, the delegate lazily constructs a `DefaultEditContext` bound to the
model at first use. Internal `_commit`, `_notify_status`, MRU reads, and icon
lookups are rewritten to call the context.

`JsonTypeDelegate` returns its post-commit auto-reopen intent through the
`EditResult.reopen_value_editor` field, replacing the `_interactive` private
flag (Issue 5).

**DoD**

- `python -m py_compile delegates/*.py`
- New tests `tests/test_delegate_edit_context.py`:
  - `test_value_delegate_uses_context_commit`
  - `test_name_delegate_uses_context_commit`
  - `test_type_delegate_reopen_via_edit_result`
- Full suite green.

### Commit 1.2 — Wire delegates from `documents/tab_setup.py`

`init_delegates_and_connections` builds a single `JsonTabEditContext`
implementing `DelegateEditContext` and passes it to each delegate. The
implementation routes:

- `commit` → `tab.mutations.commit_set_data`
- `notify_status` → `tab._status_message_callback` if set, else discarded
- `affix_mru` → `tab.affix_mru`
- `icon_provider` → `tab._icon_provider`
- `confirm_*` → existing helpers, now parameterised by `parent: QWidget`

The legacy `_find_tab`-style helpers are deleted from all three delegate
modules in this same commit.

**DoD**

- `grep -RIn "_find_tab" delegates tree_actions app documents --include='*.py' --exclude-dir=__pycache__`
  returns **zero** hits.
- Targeted: `pytest tests/test_type_editing.py tests/test_secret_editors.py tests/test_number_affix_delegate.py`.
- Full suite green.

### Commit 1.3 — Headless delegate test

Add `tests/test_delegate_standalone.py` instantiating `ValueDelegate` with a
`DefaultEditContext` over a `QStandardItemModel` and confirming an end-to-end
edit roundtrip with no `JsonTab` in scope. This is the architectural assertion
that Phase 1 has actually delivered its stated benefit (Issue 2).

**DoD**

- New test passes.
- Full suite green.

---

## 4. Phase 2 — Split `JsonTab` Behind the Façade

Each commit moves implementation **behind** the seam published in Phase 0;
the public `JsonTab` API does not change.

### Commit 2.1 — `TabValidationController(QObject)`

File: `documents/tab_validation.py`.

Migrate from `JsonTab`:

- `_schema_ref`, `_schema`, `_issue_index`, `_auto_rescan`,
  `_mutation_debounce_timer`.
- Methods `revalidate`, `set_schema`, `clear_schema`,
  `_on_registry_schema_reloaded`, `_init_validation_state`.
- Schema registry acquisition/release: `controller.acquire(source)` and
  `controller.release()`, owning the binding token. `JsonTab.closeEvent`
  calls `self.validation.release()`. The controller also disconnects all
  signal connections it created (`schema_registry.schemaReloaded` etc.) on
  `release()` (resolves Issue 7).

Controller is a `QObject` parented to `JsonTab`; the `QTimer` is parented to
the controller (resolves Issue 6).

`JsonTab` retains the following compatibility properties, each implemented as
delegating accessors (resolves Issue 16):

```python
@property
def _mutation_debounce_timer(self):  # deprecated, kept for tests
    return self.validation.debounce_timer
```

Emit `validation.finished` signal; `JsonTab` connects it to a repaint slot.

**DoD**

- `pytest tests/test_validation_autorescan.py tests/test_schema_registry_tab.py tests/test_validation_navigation.py`.
- Full suite green.
- Contract test `tests/test_tab_validation_controller.py`:
  - acquire then release ⇒ `schema_registry.bound_tabs` does not retain the tab.
  - `release()` stops the debounce timer.

### Commit 2.2 — `TabHistoryController(QObject)`

File: `documents/tab_history.py`.

Owns `QUndoStack`, `_move_view_state_by_cmd_id`,
`apply_expanded_relative_paths`, `iter_expanded_relative_paths`,
`_on_undo_index_changed`, `_on_clean_changed`.

`JsonTab.undo_stack` becomes `@property` returning
`self._history.undo_stack`. `JsonTab.history` (introduced in 0.4) now points
to the real controller. The mutation gateway’s `push_*` methods route through
`self._history.push(...)`. `undo/commands.py` continues to receive `tab` (the
façade) so external storage of `tab` references remains valid (Issue 8).

**DoD**

- `pytest tests/test_typed_undo_commands.py tests/test_undo_redo.py tests/test_drag_drop_matrix.py`.
- Full suite green.
- Contract test asserts `tab.undo_stack is tab.history.undo_stack`.

### Commit 2.3 — `TabIOController(QObject)`

File: `documents/tab_io_controller.py` (chosen to avoid colliding with the
already-existing `documents/tab_io.py`, addressing Issue 11).

Owns `file_path`, `save_format`, `_dirty`, `dirtyChanged` signal forwarding,
and orchestrates calls into the existing `documents/tab_io.py` functions. Does
not duplicate atomic IO primitives.

`JsonTab` keeps `file_path`, `save_format`, and `dirty` as forwarding
properties.

**DoD**

- `pytest tests/test_reload_from_disk.py tests/test_tab_lifecycle.py`.
- Full suite green.

### Commit 2.4 — Realise `DocumentMutationGateway`

Replace the forwarding shim from 0.2 with a real implementation that lives in
`documents/mutation_gateway.py` and depends only on the model, view, and the
history controller. `JsonTab.commit_set_data` and `JsonTab.push_*` become
thin one-line delegations.

**DoD**

- `grep -RIn "self\.undo_stack\.beginMacro" documents --include='*.py'`
  returns hits only inside `documents/mutation_gateway.py` and
  `documents/tab_history.py`.
- Full suite green.

### Commit 2.5 — Deprecation cleanup (optional, gated)

Add `DeprecationWarning` to the `tab._index_from_path`, `tab._source_to_view`,
and similar private shims. Do **not** remove them — tests still use them. A
follow-up plan can sweep tests once interfaces are settled.

**DoD**

- Full suite green; warnings filter configured in `pytest.ini` so they do not
  fail the run.

---

## 5. Phase 3 — Slim Down `MainWindow`

Resolves Issues 12, 13, 14. `MainWindow` retains ownership of `self.tabWidget`
(the Designer-generated `QTabWidget`); presenters receive it via constructor
injection.

### Commit 3.1 — `TabLifecyclePresenter`

File: `app/tab_lifecycle.py`. Constructor:
`TabLifecyclePresenter(tab_widget: QTabWidget, parent: MainWindow)`.

Moves:

- `_closed_tabs_stack`, related limits.
- `_add_tab`, `_on_tab_changed`, `close_tab`, `_reopen_tab`, dirty-close prompt
  helpers.

`MainWindow` keeps `_closed_tabs_stack` as a deprecated property returning
`self._tab_lifecycle.closed_tabs_stack` (Issue 16) so existing tests work.

**DoD**

- `pytest tests/test_tab_lifecycle.py`.
- Full suite green.

### Commit 3.2 — `AppSettingsPresenter`

File: `app/app_settings.py`. Wraps QSettings IO, edit-limit menu, secret-prefix
dialog. Reuses existing `dialogs/secret_prefixes_dlg.py`.

**DoD**

- `pytest tests/test_edit_limits_menu.py`.
- Full suite green.

### Commit 3.3 — `DockValidationPresenter`

File: `app/validation_presenter.py`. Consolidates and **wraps** the existing
`app/validation_dock_actions.py`, `app/schema_tab_pool.py`, and the
attach-schema flow currently inside `MainWindow._attach_schema_source`.
The dock widget itself remains in `app/validation_dock.py`.

Registry acquisition for new tabs is delegated to the tab’s own
`TabValidationController.acquire(source)`; the presenter only initiates the
flow. This keeps schema-source ownership on the document side as defined in
the ownership map (Issue 7).

**DoD**

- `pytest tests/test_schema_registry_tab.py tests/test_validation_navigation.py`.
- Full suite green.

### Commit 3.4 — Reconcile with existing app controllers

No new theme/font/recent-files controllers are created. The plan formally
documents (in `ai-memory/repo-map.md`) that `app/theme_controller.py`,
`app/font_controller.py`, `app/recent_files.py`, `app/history.py`, and
`app/main_window_actions.py` remain authoritative. `MainWindow` simply
constructs and wires them; any earlier wording about replacing them is
discarded (Issue 13).

**DoD**

- `grep -RIn "class .*Controller\|class .*Presenter" app --include='*.py'`
  lists only the agreed presenters; no duplicates.

---

## 6. Acceptance Metrics (Replace LOC Targets)

Run at the end of Phase 3:

1. **Delegate parent crawling is gone**

   ```bash
   grep -RIn "_find_tab" delegates tree_actions app documents --include='*.py' --exclude-dir=__pycache__
   ```

   must return zero results.

2. **No private tab access from tree actions / undo**

   ```bash
   grep -RIn "tab\._\(index_from_path\|source_to_view\|proxy_to_source\|diff_apply\|emit_row_changed\)" \
        tree_actions undo --include='*.py' --exclude-dir=__pycache__
   ```

   must return zero results.

3. **No upward imports**

   ```bash
   grep -RIn "from app\." documents delegates --include='*.py' --exclude-dir=__pycache__
   grep -RIn "from documents\." delegates --include='*.py' --exclude-dir=__pycache__
   grep -RIn "import main_window\|from app.main_window" documents delegates --include='*.py'
   ```

   must return zero results.

4. **Contract tests exist per seam** — at least one targeted test file for each:
   `tests/test_delegate_edit_context.py`,
   `tests/test_delegate_standalone.py`,
   `tests/test_tab_validation_controller.py`,
   `tests/test_tab_history_controller.py`,
   `tests/test_tab_io_controller.py`,
   `tests/test_tab_lifecycle.py` (existing, may be extended),
   `tests/test_app_settings_presenter.py`,
   `tests/test_dock_validation_presenter.py`.

5. **Targeted regression run is green**

   ```bash
   pytest \
     tests/test_type_editing.py tests/test_secret_editors.py tests/test_number_affix_delegate.py \
     tests/test_typed_undo_commands.py tests/test_undo_redo.py tests/test_drag_drop_matrix.py \
     tests/test_validation_autorescan.py tests/test_schema_registry_tab.py tests/test_validation_navigation.py \
     tests/test_tab_lifecycle.py tests/test_reload_from_disk.py tests/test_edit_limits_menu.py
   pytest
   ```

6. **No regressions in QObject lifetimes** — `tests/test_tab_validation_controller.py`
   includes an explicit `gc.collect()`/`sys.getrefcount`-style assertion that a
   closed tab is collectable and its timer is stopped.

---

## 7. Commit Order Summary

| # | Commit | Risk |
|---|--------|------|
| 0.1 | Add `DelegateEditContext` + `DefaultEditContext`              | none (additive) |
| 0.2 | Add `DocumentMutationGateway` façade on `JsonTab`             | none (forwarding) |
| 0.3 | Migrate `tree_actions/`, `undo/`, `app/history.py` call sites | low |
| 0.4 | Add `JsonTab.history` façade                                  | none |
| 1.1 | Inject edit context into all three delegates                  | medium |
| 1.2 | Wire context from `tab_setup.py`; delete `_find_tab`          | medium |
| 1.3 | Add headless delegate test                                    | none |
| 2.1 | Extract `TabValidationController`                             | medium |
| 2.2 | Extract `TabHistoryController`                                | medium-high |
| 2.3 | Extract `TabIOController`                                     | medium |
| 2.4 | Move mutation gateway implementation off `JsonTab`            | medium |
| 2.5 | Add deprecation warnings on private shims                     | none |
| 3.1 | Extract `TabLifecyclePresenter`                               | medium |
| 3.2 | Extract `AppSettingsPresenter`                                | low |
| 3.3 | Extract `DockValidationPresenter`                             | medium |
| 3.4 | Document final ownership map; no new managers                 | none |

Every commit ends with a green `pytest` run. Any commit that cannot be made
green is split further or reverted before proceeding.

---

## 8. What This Plan Explicitly Rejects

- **Signal-receiver-count fallbacks.** Replaced by `DefaultEditContext`.
- **Hard LOC targets** (600 LOC for `JsonTab`, 400 LOC for `MainWindow`).
  Replaced by the coupling and contract-test metrics above.
- **Moving `self.tabWidget` out of `MainWindow`.** Designer-generated members
  stay where Qt expects them; presenters receive references.
- **Calling extracted controllers "pure Python".** They are `QObject`
  subclasses with explicit parent ownership.
- **Renaming `_interactive` to another private flag.** The auto-reopen
  intent travels through `EditResult.reopen_value_editor`.
- **Creating new theme/font/recent-files controllers.** The existing ones in
  `app/` are authoritative.
- **Removing private `JsonTab` shims in the same commits that move logic.**
  Shims stay (with `DeprecationWarning`) so tests survive the migration; a
  future plan can sweep them once the surface is stable.

---

## 9. Out of Scope (Follow-up Plans)

- Sweeping tests off the deprecated private `JsonTab` shims.
- Splitting search/filter and theme/font propagation out of `JsonTab`.
- Reworking `tree_actions/` to consume an abstract document interface rather
  than `JsonTab` directly.
- Packaging/distribution changes.

Each of the above should be its own plan once the metrics in §6 are achieved.
