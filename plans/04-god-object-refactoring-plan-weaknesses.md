# Weaknesses in the God-Object Refactoring Plan

Review date: 2026-05-26

Reviewed plan files:

- `plans/00-refactoring-master-plan.md`
- `plans/01-valuedelegate-decoupling.md`
- `plans/02-tab-modularization.md`
- `plans/03-mainwindow-refactoring.md`
- Supporting analysis: `ai-memory/god_objects_analysis.md`

This review verified the plan against the current code in `delegates/value.py`, `delegates/name_delegate.py`, `delegates/type_delegate.py`, `documents/tab.py`, `documents/tab_setup.py`, `app/main_window.py`, and related helper modules.

## Overall finding

The plan identifies the right high-level problem: `ValueDelegate`, `JsonTab`, and `MainWindow` still carry too many responsibilities. However, the current plan is not yet implementation-ready. Its main weaknesses are incomplete coupling analysis, optimistic extraction boundaries, verification rules that do not match the current codebase, and missing compatibility strategy for widely-used public and private APIs.

---

## 1. Phase 1 treats `ValueDelegate` as the only delegate-to-tab coupling point

**Weakness:** The plan focuses on removing `_find_tab()` from `ValueDelegate`, but the same parent-crawling anti-pattern also exists in `NameDelegate` and `JsonTypeDelegate`.

**Evidence:**

- `delegates/value.py` defines `ValueDelegate._find_tab()` and calls `tab.commit_set_data(...)`.
- `delegates/name_delegate.py` defines module-level `_find_tab()` and `_commit()` and calls `tab.commit_set_data(...)`.
- `delegates/type_delegate.py` defines `JsonTypeDelegate._find_tab()` and calls `tab.commit_set_data(...)`.

**Argumentation:** Removing only `ValueDelegate._find_tab()` does not achieve the stated goal of unidirectional child-to-ancestor communication. Editing names and types will still depend on delegate parent traversal. The Phase 1 DoD even says `grep -rn "_find_tab" .` should return zero findings, but that is impossible if `NameDelegate` and `JsonTypeDelegate` are not included. The plan should define a shared delegate commit bridge or delegate base protocol and migrate all three edit delegates together.

---

## 2. Phase 1 ignores non-commit tab reads inside `ValueDelegate`

**Weakness:** The proposed signal bridge only replaces commit/status calls, but `ValueDelegate` still reads tab-owned state during editor creation and after successful edits.

**Evidence:**

- `ValueDelegate.createEditor()` uses `_find_tab(parent)` to read `tab.affix_mru` and `tab._icon_provider` for affix editors.
- `ValueDelegate.setModelData()` uses `_find_tab(editor)` after affix edits to push values into `tab.affix_mru`.

**Argumentation:** Even if `_commit()` and `_notify_status()` emit signals, the delegate remains coupled to `JsonTab` for affix MRU data and icon lookup. This means the claimed benefit — reusing `ValueDelegate` in standalone views or headless tests — is only partially achieved. The plan should introduce an explicit editor context/provider for MRU, icons, status, and commit behavior, or pass those collaborators directly into delegates at construction time.

---

## 3. The signal bridge does not preserve synchronous commit success semantics

**Weakness:** `ValueDelegate._commit()` currently returns `bool`, but Qt signal emission does not naturally return a slot result to the caller.

**Evidence:**

- `ValueDelegate._commit(...) -> bool` currently returns the result of `tab.commit_set_data(...)` or `model.setData(...)`.
- `ValueDelegate.setModelData()` uses the boolean result for affix edits before pushing to MRU.
- `JsonTab.commit_set_data(...) -> bool` is the gatekeeper for read-only state, role validity, column dispatch, duplicate-name rejection, type coercion, and undo command creation.

**Argumentation:** The plan says `commitRequested = Signal(QModelIndex, object, int)` and suggests connecting it directly to `tab.commit_set_data`. That loses the success/failure value. If the delegate cannot know whether the mutation succeeded, it may update MRU state after rejected edits or fail to report rejected commits accurately. A safer design would use an explicit transaction router object with a synchronous `commit(...) -> bool` method, or emit a request object/callback that can record acceptance.

---

## 4. The planned fallback path is underspecified and may be unreliable

**Weakness:** Phase 1 says `ValueDelegate` should fall back to `model.setData()` "if no slots are connected", but the plan does not define a reliable way to detect that condition in PySide.

**Evidence:**

- Current code has an unambiguous fallback: if `_find_tab(host)` returns `None`, it calls `model.setData(...)`.
- The proposed design depends on knowing whether a signal has connected receivers.

**Argumentation:** PySide signal receiver introspection is awkward and brittle compared with an explicit collaborator. If the delegate simply emits a signal and then also falls back, connected commits could be duplicated. If it emits only, standalone model editing may silently do nothing. The plan should specify exact fallback mechanics and tests for standalone delegate operation.

---

## 5. `JsonTypeDelegate._interactive` is a hidden cross-component contract not covered by the plan

**Weakness:** The plan does not account for the current behavior where `JsonTab` reads a private flag from `JsonTypeDelegate` to decide whether to reopen a value editor after a type change.

**Evidence:**

- `JsonTypeDelegate.setModelData()` sets `self._interactive = True` around user-driven type commits.
- `JsonTab._on_type_changed()` reads `getattr(self.type_delegate, "_interactive", False)` to decide whether to reopen the value editor.

**Argumentation:** This is another delegate-to-tab/tab-to-delegate coupling channel. Moving commit routing to signals without replacing this contract can break the type-editing UX or preserve a private backchannel that contradicts the plan's decoupling goal. The refactor should replace `_interactive` with an explicit signal payload, command context, or edit-session controller.

---

## 6. The plan calls extracted tab controllers "pure-Python", but they are Qt-bound

**Weakness:** Phase 2 describes `TabValidationController`, `TabHistoryController`, and `TabIOController` as pure-Python controllers, but at least two of them necessarily depend on Qt objects and lifecycles.

**Evidence:**

- Validation logic uses `QTimer`, Qt model signals, `Signal`, `QModelIndex`, and repaint-triggering `dataChanged` emissions.
- History logic uses `QUndoStack`, `QUndoCommand`, `QModelIndex`, selection models, view expansion state, and `QItemSelectionModel`.
- I/O state is tied to `dirtyChanged` signal behavior and `QUndoStack.setClean()`.

**Argumentation:** Treating these as pure-Python classes understates their lifecycle and ownership risks. They probably need to be `QObject`-based presenters/controllers or split into two layers: a pure domain service plus a Qt adapter. Without that distinction, the extraction can introduce timer leaks, dangling signal connections, or controllers that are still untestable without Qt.

---

## 7. Validation extraction lacks a schema-registry ownership and disconnect strategy

**Weakness:** Phase 2 says to move schema state and validation methods, but it does not define how schema registry ownership, release, reload signals, and close lifecycle should move.

**Evidence:**

- `JsonTab._swap_source()` releases the previous schema source and acquires the new source from `schema_registry`.
- `JsonTab.closeEvent()` releases the active schema source.
- `JsonTab.__init__()` connects `schema_registry.schemaReloaded` to `_on_registry_schema_reloaded`.
- `MainWindow._attach_schema_source()` also calls `schema_registry.acquire(source, tab)` before `tab.set_schema_from_source(source)`.

**Argumentation:** Registry ownership is subtle because the registry tracks bound tabs with weak references and reference counts. A validation controller needs a clear owner token, deterministic release method, and disconnect behavior when the tab closes. Otherwise ref-counting, file watching, reload propagation, or recent-schema updates can become incorrect. The plan should explicitly define whether the owner is the tab, the controller, or a separate token object.

---

## 8. History extraction does not account for the broad `JsonTab` API consumed by commands, actions, tests, and app code

**Weakness:** Phase 2 proposes moving `QUndoStack`, command routing, and view-state preservation into `TabHistoryController`, but many modules currently depend directly on `JsonTab` methods and attributes.

**Evidence:** Current external usages include:

- `app/history.py` reads `tab.undo_stack`, connects `canUndoChanged`/`canRedoChanged`, and calls `undo()`/`redo()`.
- `app/main_window.py` calls `tab.undo_stack.clear()`, `tab.undo_stack.setClean()`, and uses `tab._source_to_view(...)`.
- `tree_actions/paste.py`, `tree_actions/structure.py`, `tree_actions/dnd.py`, and `tree_actions/context_menu.py` call `tab.push_insert_rows(...)`, `tab.push_edit_value(...)`, `tab.push_move_rows_anchor(...)`, `tab.push_remove_rows(...)`, `tab.undo_stack.beginMacro(...)`, and private path helpers.
- `undo/commands.py` stores a `tab` reference and calls `tab.model`, `tab.view`, `tab._index_from_path(...)`, `tab._source_to_view(...)`, `tab._diff_apply(...)`, and `tab._emit_row_changed(...)`.
- Many tests directly assert against `tab.undo_stack`, `tab.commit_set_data(...)`, `tab._index_from_path(...)`, and `tab._source_to_view(...)`.

**Argumentation:** Moving the undo stack alone would break large parts of the application unless `JsonTab` remains a compatibility facade. The plan should either preserve `tab.undo_stack` and `tab.push_*` as delegating properties/methods or include a coordinated migration of tree actions, undo commands, app history, and tests. Without that, the extraction is much larger than the stated commit plan.

---

## 9. The plan does not address the `tree_actions` boundary, which is one of the strongest `JsonTab` coupling sources

**Weakness:** Phase 2 focuses on validation/history/I/O, but the action modules are tightly coupled to `JsonTab` private helpers and mutation APIs.

**Evidence:**

- `tree_actions/anchors.py` calls `tab._index_path(...)` and `tab._index_from_path(...)`.
- `tree_actions/paste.py` calls `tab.push_insert_rows(...)`, `tab.push_edit_value(...)`, `tab.undo_stack.beginMacro(...)`, and private path helpers.
- `tree_actions/structure.py` calls `tab.push_*`, `tab.undo_stack`, and private path helpers throughout movement, deletion, duplicate, and case-switch operations.

**Argumentation:** If `TabHistoryController` owns mutation commands, these action modules should probably depend on a mutation gateway rather than on `JsonTab`. Otherwise `JsonTab` remains the de facto god object API even if method bodies move elsewhere. The plan should introduce an explicit `TreeMutationController` or `DocumentCommandRouter` seam.

---

## 10. The `JsonTab` line-count target is unlikely to be reached by the proposed extractions alone

**Weakness:** Phase 2 claims `documents/tab.py` should fall below 600 LOC after extracting validation, history, and I/O, but a large amount of unrelated logic remains.

**Evidence:** `JsonTab` currently has about 1,397 lines and 93 methods. The proposed extractions cover only a subset of responsibilities. Remaining responsibilities include:

- Event filtering and keyboard navigation.
- Read-only mode toggling.
- Theme and font propagation.
- Search/filter management.
- Type-edit UX and editor reopening.
- Path/view mapping facade methods.
- Diff helper facade methods.
- Typed mutation public API wrappers.
- Tree action dispatch and convenience insert methods.
- Selection and expansion restoration.

**Argumentation:** The target may encourage moving code mechanically into controllers without reducing coupling. A better metric would be dependency direction, public API size, private cross-module access count, and testability of each extracted unit. If a hard LOC target remains, the plan needs additional phases for search/navigation, theme/font, tree actions, and command routing.

---

## 11. Phase 2 duplicates or bypasses helper modules that already exist

**Weakness:** The plan proposes new files such as `documents/tab_file.py`, but the codebase already contains extracted helpers for several tab concerns.

**Evidence:** Existing modules include:

- `documents/tab_io.py`
- `documents/tab_paths.py`
- `documents/tab_setup.py`
- `documents/tab_status.py`

**Argumentation:** The plan should build on these existing seams rather than creating parallel controllers with overlapping names and responsibilities. For example, `TabIOController` should probably wrap or absorb `documents/tab_io.py` instead of duplicating save/snapshot behavior. Otherwise the refactor may increase fragmentation and make ownership less clear.

---

## 12. Phase 3 assumes a `self.tabs` member that does not exist in the current `MainWindow`

**Weakness:** Commit 3.1 says to move `self.tabs`, but the current application uses the generated UI member `self.tabWidget`.

**Evidence:**

- `MainWindow._current_tab()` reads `self.tabWidget.currentWidget()`.
- Tab add/close/reopen logic calls `self.tabWidget.addTab(...)`, `removeTab(...)`, `widget(...)`, `count()`, and `setCurrentIndex(...)`.

**Argumentation:** A lifecycle controller should not "move" ownership of the generated `QTabWidget` out of `MainWindow`. It should receive the widget as a dependency and manage operations against it. This distinction matters because Qt parent/child ownership, Designer-generated attributes, and signal connections remain rooted in `MainWindow`.

---

## 13. Phase 3 risks duplicating existing `MainWindow` controllers and helper modules

**Weakness:** The plan proposes new managers without reconciling them with controllers/helpers that already exist.

**Evidence:** Existing app-level seams include:

- `app/font_controller.py`
- `app/theme_controller.py`
- `app/schema_tab_pool.py`
- `app/history.py`
- `app/main_window_actions.py`
- `app/recent_files.py`
- `app/validation_dock.py`
- `app/validation_dock_actions.py`

**Argumentation:** `MainWindow` has already been partially modularized. New classes such as `AppSettingsController`, `DockValidationPresenter`, and `MainActionStateController` should be designed as consolidation or continuation of the existing seams. Otherwise the application could end up with multiple thin managers that still reach back into `MainWindow` internals, preserving the god-object coupling while spreading it across more files.

---

## 14. The `MainWindow` line-count target is also optimistic and may be counterproductive

**Weakness:** Phase 3 sets a target of `app/main_window.py` below 400 LOC, but `MainWindow` currently has about 1,116 lines and 98 methods, and several visual-shell responsibilities must remain.

**Evidence:** Even after moving tab lifecycle, settings, and validation-dock handling, `MainWindow` still owns or coordinates:

- Drag-and-drop shell behavior.
- Window geometry and close-event persistence.
- Generated action/menu wiring.
- Status bar messaging.
- Theme/font controller adapters.
- File open/save/reload dialog entry points.
- Current-tab/current-view facade methods.
- Application-level action wrappers.

**Argumentation:** A hard LOC goal can drive excessive indirection. The plan should define which responsibilities legitimately remain in the shell and measure reduced coupling instead of only reduced file length.

---

## 15. Verification commands are incomplete, sometimes misleading, and not aligned with current tests

**Weakness:** The DoD commands do not fully cover the risks introduced by the refactor and in some cases would produce misleading results.

**Evidence:**

- `grep -rn "_find_tab" .` would also match the plan documents themselves unless documentation and cache directories are excluded.
- `pytest tests/ -k "lifecycle or tab"` will select a very broad set because many tests or paths contain `tab`, not only lifecycle tests.
- Phase 1 lacks focused tests for standalone delegate operation, signal fallback, affix MRU updates, type-editor auto-reopen, and name/type delegate decoupling.
- Phase 2 and 3 rely heavily on broad full-suite runs but do not add contract tests for the new controller APIs.

**Argumentation:** Full-suite testing is necessary but not sufficient. The plan needs targeted regression tests for each extracted seam plus static checks that exclude `.md`, `.pytest_cache`, `__pycache__`, and generated caches. Verification should prove both behavior and architectural direction.

---

## 16. The plan lacks a compatibility strategy for tests and external call sites using private `JsonTab` internals

**Weakness:** Many tests and helper modules access private `JsonTab` methods and attributes directly, but the plan does not specify whether those APIs remain as facades or get migrated.

**Evidence:** Tests and modules reference:

- `tab._mutation_debounce_timer`
- `tab.undo_stack`
- `tab._index_from_path(...)`
- `tab._source_to_view(...)`
- `tab._proxy_to_source(...)`
- `window._closed_tabs_stack`

**Argumentation:** Internal refactors can be safe if public compatibility facades remain during migration. Without an explicit compatibility plan, each extraction commit risks creating large unrelated test rewrites. The plan should identify stable facade properties/methods and mark which private test hooks will be migrated or retained temporarily.

---

## 17. The extraction order may create avoidable churn

**Weakness:** Phase 1 connects delegates directly back to `JsonTab.commit_set_data`, then Phase 2 later proposes moving command routing/history responsibilities out of `JsonTab`.

**Evidence:**

- Phase 1 Commit 1.2 connects delegate signals to `tab.commit_set_data`.
- Phase 2 Commit 2.2 moves command routing and `QUndoStack` into `TabHistoryController`.

**Argumentation:** This order can force the same signal connections to be rewritten shortly afterward. A lower-churn approach would first introduce a stable `DocumentCommandRouter`/`MutationGateway` facade, connect delegates and tree actions to that gateway, and only then move the underlying implementation from `JsonTab` into a controller.

---

## 18. The plan does not define ownership boundaries between UI shell, document tab, controllers, and services

**Weakness:** The plan names several controllers but does not define which layer owns which state, which APIs are stable, or how dependencies are injected.

**Evidence:** Current ownership is mixed:

- `MainWindow` owns tab lifecycle, schema dock UI, schema attach operations, status messages, and recent-file menus.
- `JsonTab` owns model/view, undo stack, validation state, schema registry bindings, dirty state, and tree mutation command APIs.
- Delegates own editor widgets but reach upward for commits, status, MRU, and icon context.

**Argumentation:** Without explicit ownership rules, extracted controllers can become mini-god objects or back-reference `MainWindow`/`JsonTab` heavily. The plan should document dependency direction, constructor dependencies, emitted signals, stable facade methods, and forbidden reverse dependencies for each controller before implementation starts.

---

## Suggested plan corrections

1. Add a pre-phase that defines stable interfaces:
   - `DocumentMutationGateway` or `DocumentCommandRouter`
   - `DelegateEditContext`
   - `ValidationSession`/`ValidationPresenter`
   - `TabLifecycleService`
2. Expand Phase 1 to cover `NameDelegate`, `JsonTypeDelegate`, `ValueDelegate`, and context-menu commit helpers together.
3. Preserve `JsonTab` compatibility facades during Phase 2: `undo_stack`, `commit_set_data`, `push_*`, path helpers, and view mapping helpers should initially delegate to extracted controllers.
4. Rework validation extraction around explicit schema-registry ownership and cleanup.
5. Rework history extraction around existing `undo/commands.py` dependencies, not just `QUndoStack` placement.
6. Update Phase 3 to consolidate existing app modules instead of creating parallel managers.
7. Replace hard LOC targets with measurable coupling targets, such as:
   - zero delegate parent-crawling in production code,
   - no `tree_actions` calls to `JsonTab` private helpers,
   - controllers have no back-reference except through documented protocols,
   - focused controller contract tests exist for every extracted seam.
8. Strengthen DoD commands with targeted tests and safer static checks, for example:

   ```bash
   grep -RIn "_find_tab" delegates tree_actions app documents \
     --include='*.py' --exclude-dir='__pycache__'
   pytest tests/test_type_editing.py tests/test_secret_editors.py tests/test_number_affix_delegate.py
   pytest tests/test_typed_undo_commands.py tests/test_undo_redo.py tests/test_drag_drop_matrix.py
   pytest tests/test_validation_autorescan.py tests/test_schema_registry_tab.py tests/test_validation_navigation.py
   pytest tests/test_tab_lifecycle.py tests/test_reload_from_disk.py tests/test_edit_limits_menu.py
   ```
