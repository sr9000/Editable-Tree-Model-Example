# Plan 3 — Cancel button for loading progress

**Goal:** Add a Cancel button to the loading progress widget from [`Plan 2`](02-big-file-loading-progress-bar.md) with no-side-effect semantics. Cancelling an initial open before its commit point adds no tab, pushes no recent-file entry, registers no schema/validation state, and leaves dirty state untouched. Cancelling a reload before its commit point leaves the existing tab data, dirty flag, undo stack, validation state, and view state unchanged.

The loading pipeline this plan extends is now **non-blocking and staged across event-loop turns**: file parsing runs in a [`ParseWorker`](../app/loading/worker.py:15) `QThread`, the item tree is built off to the side by [`ChunkedTreeBuilder`](../app/loading/builder.py:28) in `QTimer`-scheduled slices, and post-build work (tab binding, first presentation, schema discovery, validation, and the reload swap) is deferred onto later event-loop turns by [`Plan 2.5`](02.5-loading-progress-details-and-nonblocking-build.md) and [`Plan 2.6`](02.6-post-build-freeze-after-jsonmodel-finished.md). Those deferrals are the yielding boundaries cancellation hooks into.

**Prerequisite:** [`Plan 2.6`](02.6-post-build-freeze-after-jsonmodel-finished.md) must be complete (which itself requires [`Plan 2`](02-big-file-loading-progress-bar.md) and [`Plan 2.5`](02.5-loading-progress-details-and-nonblocking-build.md)). That gives this plan: coordinator ownership in [`LoadCoordinator`](../app/loading/coordinator.py:48), the delayed widget [`LoadingProgressDialog`](../app/loading/progress_dialog.py:16) (already constructed with a `cancellable` flag and a placeholder Cancel button), worker parse, chunked build, deferred post-build binding/presentation/validation, and reload build-then-swap via [`JsonTreeModel.replace_root_item()`](../tree/model.py:94).

See [`plans/index.md`](index.md) for the mandatory gate every commit must pass.

## Current loading control flow (what cancellation must respect)

- **Blocking wrappers pump the event loop.** [`LoadCoordinator.open_file()`](../app/loading/coordinator.py:214) and [`LoadCoordinator.reload_file()`](../app/loading/coordinator.py:221) call [`LoadCoordinator._run_blocking()`](../app/loading/coordinator.py:164), which spins [`QApplication.processEvents()`](../app/loading/coordinator.py:180) until the task lands in `_completed_task_results`. A Cancel click is therefore delivered and handled while the originating `_open_path`/`_reload_tab_from_path` call is still on the stack; cancellation must make `_run_blocking` return `False`.
- **Single active task guard.** [`LoadCoordinator._begin_task()`](../app/loading/coordinator.py:126) refuses a new load while `_current_task_id` is set, and [`LoadCoordinator._finish_progress()`](../app/loading/coordinator.py:114)/[`_error_progress()`](../app/loading/coordinator.py:120) clear it. Cancellation must clear `_current_task_id` so the next load can start.
- **Tasks keyed by id.** Each load is a [`_LoadTask`](../app/loading/coordinator.py:35) with a `task_id` (UUID). Parse results arrive via queued signals [`LoadCoordinator._parse_succeeded`](../app/loading/coordinator.py:63)/[`_parse_failed`](../app/loading/coordinator.py:64) into [`_on_parse_finished()`](../app/loading/coordinator.py:228)/[`_on_parse_failed()`](../app/loading/coordinator.py:249); build results arrive via [`ChunkedTreeBuilder.finished`](../app/loading/builder.py:43) into [`_on_build_finished()`](../app/loading/coordinator.py:264). Every handler already early-returns when `self._tasks.get(task_id)` is `None`, so removing a task from `_tasks` is the existing staleness mechanism.

## Commit points (post-2.5/2.6)

- **Initial open** commits at [`LoadCoordinator._bind_open()`](../app/loading/coordinator.py:277) when it calls [`MainWindow._add_tab()`](../app/main_window.py:298) → [`TabLifecyclePresenter.add_tab()`](../app/tab_lifecycle.py:68). Tab creation/insertion is the atomic commit. The deferred first-presentation step [`TabLifecyclePresenter._run_initial_presentation()`](../app/tab_lifecycle.py:118) and the coordinator-owned schema/validation in [`LoadCoordinator._finish_open_binding()`](../app/loading/coordinator.py:295) (which also calls [`push_recent()`](../app/recent_files.py:8)) run **after** the commit and complete without cancellation.
- **Reload** commits at [`LoadCoordinator._apply_reload()`](../app/loading/coordinator.py:310) when it emits [`STAGE_APPLYING_RELOAD`](../app/loading/progress.py:18) and calls [`JsonTreeModel.replace_root_item()`](../tree/model.py:94). The deferred [`LoadCoordinator._finish_reload_apply()`](../app/loading/coordinator.py:337) (validation, presentation refresh) runs after the commit.

## Cancellation semantics

- **Initial open:** If the token is set before the add-tab commit in [`LoadCoordinator._bind_open()`](../app/loading/coordinator.py:277), [`TabLifecyclePresenter.add_tab()`](../app/tab_lifecycle.py:68) is not called, [`push_recent()`](../app/recent_files.py:8) is not called, schema/validation state is not registered, dirty state is untouched, and the status bar shows `Open cancelled`.
- **Reload:** If the token is set before the [`STAGE_APPLYING_RELOAD`](../app/loading/progress.py:18) swap in [`LoadCoordinator._apply_reload()`](../app/loading/coordinator.py:310), old data, dirty flag, undo stack, validation state, and the in-memory view state captured by [`view_state.capture_runtime_state()`](../state/view_state.py:174) remain equal to the pre-reload snapshot.
- **Worker parse:** JSON/YAML parsing inside the [`ParseWorker`](../app/loading/worker.py:15) `QThread` cannot be interrupted. Cancel sets the token, hides the widget, stops [`_run_blocking()`](../app/loading/coordinator.py:164) from waiting, and discards the late [`_parse_succeeded`](../app/loading/coordinator.py:63)/[`_parse_failed`](../app/loading/coordinator.py:64) signal when it arrives.
- **Chunked build:** The builder checks the token between batches inside [`ChunkedTreeBuilder._do_work_slice()`](../app/loading/builder.py:95) and stops scheduling further slices, emitting a cancelled signal instead of [`finished`](../app/loading/builder.py:43) so no model reaches binding/validation.
- **Deferred post-build steps:** Because binding, first presentation, and validation are now deferred onto separate event-loop turns, the coordinator gets one last token check immediately before each commit point ([`_bind_open()`](../app/loading/coordinator.py:277) add-tab and [`_apply_reload()`](../app/loading/coordinator.py:310) swap). After the commit point the deferred work (`_finish_open_binding`, `_finish_reload_apply`) runs to completion so no half-bound tab or half-swapped model is ever left behind.
- **Commit point:** Once initial open calls [`MainWindow._add_tab()`](../app/main_window.py:298), or reload starts the [`replace_root_item()`](../tree/model.py:94) swap, that commit is non-cancellable and must finish or surface the existing error path.

Hard CPU/IO termination of an in-flight parser is not part of this plan. It requires a worker process or `QProcess` design in a separate future plan.

---

## Commits

### Commit 3.1 — Cancellation token primitive
- [ ] Completed

**Problem it solves:** Coordinator, widget, worker-result handling, and chunked builder need one thread-safe cancellation signal that is independent of Qt widget lifetime.

**Files it touches:**
- `app/loading/cancellation.py` — new `CancellationToken` with `cancel()`, `is_cancelled`, and `raise_if_cancelled()` plus `CancelledError`.
- `tests/test_loading_cancellation.py` — new tests for same-thread and cross-thread set/observe.

**Expected behavior:** Calling `cancel()` once makes all future `is_cancelled` reads return `True`. Repeated `cancel()` calls leave the token in the cancelled state. `raise_if_cancelled()` raises `CancelledError` only after cancellation.

**Acceptance criteria:**
- Cross-thread test starts one observer thread and one cancelling thread; observer sees cancellation without polling shared Qt widgets.
- Module exposes a plain Python API and does not require callers outside `app/loading` to import Qt synchronization classes.
- Mandatory gate passes.

### Commit 3.2 — Activate the Cancel button on the loading widget
- [ ] Completed

**Problem it solves:** [`LoadingProgressDialog`](../app/loading/progress_dialog.py:16) already accepts `cancellable=True` and renders a Cancel button placeholder, but the button is not wired to a token and the coordinator never constructs the widget as cancellable.

**Files it touches:**
- [`app/loading/progress_dialog.py`](../app/loading/progress_dialog.py:66) — connect the existing Cancel button's `clicked` signal to a coordinator-supplied callback (or a per-task `CancellationToken`), call `token.cancel()` once, disable the button after the first click, and set the stage label to `Cancelling…`. Keep the existing delayed-show and detail-refresh timers intact; the widget stays visible after the click until the coordinator calls [`LoadingProgressDialog.finish()`](../app/loading/progress_dialog.py:128) or [`error()`](../app/loading/progress_dialog.py:141).
- [`app/loading/coordinator.py`](../app/loading/coordinator.py:107) — construct the dialog with `cancellable=True` in [`LoadCoordinator._start_progress()`](../app/loading/coordinator.py:107) and hand it the active task's token.
- `tests/test_loading_progress_cancel_button.py` — new widget tests.

**Expected behavior:** The button is visible only when the widget is constructed with `cancellable=True`. Clicking it sets the token exactly once, disables the button, switches the stage label to `Cancelling…`, and leaves the widget visible until the coordinator acknowledges cancellation or completion.

**Acceptance criteria:**
- Test drives the button and asserts the token is cancelled.
- Test asserts a second click does not emit a second cancel action.
- Test asserts `cancellable=False` mode has no Cancel button (existing default path unchanged).
- Mandatory gate passes.

### Commit 3.3 — Discard late worker-parse results after cancel
- [ ] Completed

**Problem it solves:** A worker parse can finish after the user has cancelled. Its result must not create a tab, push recent files, start validation, or replace a reloading tab, and it must not pop a user-facing error dialog.

**Files it touches:**
- [`app/loading/coordinator.py`](../app/loading/coordinator.py:48) — give each [`_LoadTask`](../app/loading/coordinator.py:35) a `CancellationToken` and track a `cancelled` set. Add a coordinator `cancel_current()` (invoked by the widget callback) that: marks the task cancelled, calls [`_finish_progress()`](../app/loading/coordinator.py:114) (clearing `_current_task_id`), shows `Open cancelled`/`Reload cancelled`, and completes the task via [`_complete_task(task_id, False)`](../app/loading/coordinator.py:356) so [`_run_blocking()`](../app/loading/coordinator.py:164) returns `False`. In [`_on_parse_finished()`](../app/loading/coordinator.py:228) and [`_on_parse_failed()`](../app/loading/coordinator.py:249), drop signals for cancelled/absent task ids without building, without error dialogs, and without re-completing.
- `tests/test_loading_cancel_during_parse.py` — new tests for initial open and reload.

**Expected behavior:** Cancelling during parse returns the UI to the pre-load state and unblocks the originating `open_file`/`reload_file` call with `False`. When the worker later emits success or failure, the coordinator drops the signal and records no user-facing error for the cancelled task.

**Acceptance criteria:**
- Initial-open test cancels during a slow fake parser, then emits late success; tab count and recent list remain unchanged and `_current_task_id` is cleared.
- Reload test cancels during a slow fake parser, then emits late success; the pre-reload snapshot remains unchanged.
- Late failure after cancel does not show an error dialog.
- Mandatory gate passes.

### Commit 3.4 — Cooperative cancel during chunked initial-open build
- [ ] Completed

**Problem it solves:** After parsing succeeds, initial-open model building runs in self-scheduling [`QTimer`](../app/loading/builder.py:93) slices. It must stop between batches when the token is cancelled and must discard the half-built off-side tree without ever emitting [`finished`](../app/loading/builder.py:43).

**Files it touches:**
- [`app/loading/builder.py`](../app/loading/builder.py:95) — accept an optional `CancellationToken`. At the top of [`ChunkedTreeBuilder._do_work_slice()`](../app/loading/builder.py:95) check the token; if cancelled, stop scheduling further slices, drop the partial `_root_item`, and emit a new `cancelled` signal instead of [`finished`](../app/loading/builder.py:43). Because slices reschedule themselves through the event loop, the builder must not rely on exception propagation to the coordinator.
- [`app/loading/coordinator.py`](../app/loading/coordinator.py:236) — in [`_on_parse_finished()`](../app/loading/coordinator.py:228) pass the task token into [`ChunkedTreeBuilder`](../app/loading/builder.py:28) and connect `builder.cancelled` to a handler that discards build state and skips add-tab/recent/validation, completing the task as cancelled.
- `tests/test_loading_cancel_during_build.py` — new initial-open build-cancel test.

**Expected behavior:** Cancelling during build leaves the application as if the user never selected the file, except for the status bar message `Open cancelled`. No model is bound and no deferred presentation/validation is scheduled.

**Acceptance criteria:**
- Test asserts tab count unchanged, recent list unchanged, schema registry unchanged for that path, validation state not created, and no exception dialog shown.
- Test asserts the builder emits `cancelled` (never `finished`) and that the coordinator releases the builder and partial root.
- Mandatory gate passes.

### Commit 3.5 — Atomic cancel-safe reload
- [ ] Completed

**Problem it solves:** Reload no longer routes through [`DiffApplier.apply()`](../undo/diff.py:13); since [`Plan 2.5`](02.5-loading-progress-details-and-nonblocking-build.md) it builds a prebuilt model off-thread and commits via a single [`JsonTreeModel.replace_root_item()`](../tree/model.py:94) swap inside `beginResetModel()`/`endResetModel()`. Cancellation must be gated before that swap; the swap itself and the deferred [`_finish_reload_apply()`](../app/loading/coordinator.py:337) are non-cancellable.

**Files it touches:**
- [`app/loading/coordinator.py`](../app/loading/coordinator.py:310) — in [`_apply_reload()`](../app/loading/coordinator.py:310), check the token immediately before emitting [`STAGE_APPLYING_RELOAD`](../app/loading/progress.py:18); if cancelled, skip the [`replace_root_item()`](../tree/model.py:94) swap, leave the tab untouched, and complete the task as cancelled (`Reload cancelled`). The pre-reload snapshot already captured by [`view_state.capture_runtime_state()`](../state/view_state.py:174) is simply discarded on cancel.
- [`state/view_state.py`](../state/view_state.py:174) — reuse [`capture_runtime_state()`](../state/view_state.py:174)/[`restore_runtime_state()`](../state/view_state.py:185) to assert, in tests, that view state is identical before and after a cancelled reload.
- [`undo/diff.py`](../undo/diff.py:13) — no change; document that reload no longer calls [`DiffApplier`](../undo/diff.py:9) (interactive edits still do), so there is no mid-diff cancellation concern.
- `tests/test_loading_cancel_reload_atomic.py` — new reload cancellation tests.

**Expected behavior:** Cancelling before the reload swap leaves old tab data, dirty flag, undo stack count and clean index, validation state, expanded paths, selection, and scroll equal to the pre-reload snapshot. Completing reload without cancellation behaves like the [`Plan 2.5`](02.5-loading-progress-details-and-nonblocking-build.md)/[`Plan 2.6`](02.6-post-build-freeze-after-jsonmodel-finished.md) reload path.

**Acceptance criteria:**
- Test cancels at parse, build, and immediately-before-swap checkpoints; each preserves the full snapshot and leaves model object identity unchanged.
- Test completes reload without cancellation and asserts existing reload-from-disk expectations still pass.
- Test proves no mid-swap cancellation occurs (the token is not re-checked after `replace_root_item()` begins).
- Mandatory gate passes.

### Commit 3.6 — No-side-effect cancellation regression suite
- [ ] Completed

**Problem it solves:** Future refactors must not move side effects before the cancellation gate, and must not move a side effect ahead of a deferred post-build boundary in a way that makes it run for a cancelled task.

**Files it touches:**
- `tests/test_loading_cancel_invariants.py` — new focused regression module covering open-cancel, reload-cancel, late success discard, late failure discard, dirty-state preservation, recent-list preservation, validation/schema non-registration, and `_current_task_id` clearing so a subsequent load can start.
- Existing tests in [`tests/test_reload_from_disk.py`](../tests/test_reload_from_disk.py:1), [`tests/test_load_coordinator.py`](../tests/test_load_coordinator.py:1), and [`tests/test_smoke_mainwindow.py`](../tests/test_smoke_mainwindow.py:1) remain complementary.

**Expected behavior:** Every side effect listed in this plan occurs only after the coordinator has checked that the task is not cancelled and is not stale, including the deferred post-build steps owned by [`_finish_open_binding()`](../app/loading/coordinator.py:295) and [`_finish_reload_apply()`](../app/loading/coordinator.py:337).

**Acceptance criteria:**
- Regression suite includes one test for each cancellation invariant in the semantics section.
- A test proves a cancelled task releases the single-task guard (a second `open_file` starts successfully afterward).
- Suite passes with `QT_QPA_PLATFORM=offscreen`.
- Mandatory gate passes.

## Deferred out of scope — hard parser termination

Cooperative cancel does not stop CPU use while [`simplejson.load()`](../io_formats/load.py:64) or [`yaml.load_all()`](../io_formats/load.py:64) is executing inside the [`ParseWorker`](../app/loading/worker.py:15) thread. If product requirements later demand CPU termination within a bounded interval, create a separate plan for a `multiprocessing` or `QProcess` parser with IPC serialization, orphan-process tests, and parity tests for parsed results. Note that [`LoadCoordinator._run_blocking()`](../app/loading/coordinator.py:164) already enforces a `LOADING_HARD_TIMEOUT_SECONDS` deadline as a coarse backstop; that timeout is not a substitute for real cancellation.
