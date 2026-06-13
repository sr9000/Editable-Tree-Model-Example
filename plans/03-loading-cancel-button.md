# Plan 3 — Cancel button for loading progress

**Goal:** Add a Cancel button to the loading progress widget from [`Plan 2`](02-big-file-loading-progress-bar.md) with no-side-effect semantics. Cancelling an initial open before commit adds no tab, pushes no recent-file entry, registers no schema/validation state, and leaves dirty state untouched. Cancelling a reload before commit leaves the existing tab data, dirty flag, undo stack, validation state, and view state unchanged.

**Prerequisite:** [`Plan 2`](02-big-file-loading-progress-bar.md) must be complete, including coordinator ownership, delayed widget, worker parse, chunked build, schema/validation progress, and reload build-then-swap.

See [`plans/index.md`](index.md) for the mandatory gate every commit must pass.

## Cancellation semantics

- **Initial open:** If the cancellation token is set before the add-tab commit, [`TabLifecyclePresenter.add_tab()`](../app/tab_lifecycle.py:64) is not called, [`push_recent()`](../app/main_window.py:316) is not called, schema/validation state is not registered, and the status bar shows `Open cancelled`.
- **Reload:** If the cancellation token is set before the `applying reload` commit stage, old data, dirty flag, undo stack, validation state, expanded paths, selection, and scroll position remain equal to the pre-reload snapshot.
- **Worker parse:** JSON/YAML parsing inside a `QThread` cannot be interrupted. Cancel sets the token, hides the widget, stops the coordinator from waiting for that task, and discards the worker result or error when it arrives later.
- **Chunked build:** The builder checks the token between batches and raises the cancellation sentinel before binding UI state or registering validation.
- **Commit point:** Once initial open starts adding a tab, or reload starts the final swap/apply step, that commit is non-cancellable and must finish or surface the existing error path.

Hard CPU/IO termination of an in-flight parser is not part of this plan. It requires a worker process or `QProcess` design in a separate future plan.

---

## Commits

### Commit 3.1 — Cancellation token primitive
- [ ] Completed

**Problem it solves:** Coordinator, widget, worker-result handling, and chunked builder need one thread-safe cancellation signal.

**Files it touches:**
- `app/loading/cancellation.py` — new `CancellationToken` with `cancel()`, `is_cancelled`, and `raise_if_cancelled()` plus `CancelledError`.
- `tests/test_loading_cancellation.py` — new tests for same-thread and cross-thread set/observe.

**Expected behavior:** Calling `cancel()` once makes all future `is_cancelled` reads return `True`. Repeated `cancel()` calls leave the token in the cancelled state. `raise_if_cancelled()` raises `CancelledError` only after cancellation.

**Acceptance criteria:**
- Cross-thread test starts one observer thread and one cancelling thread; observer sees cancellation without polling shared Qt widgets.
- Module exposes a plain Python API and does not require callers outside `app/loading` to import Qt synchronization classes.
- Mandatory gate passes.

### Commit 3.2 — Add Cancel button to the loading widget
- [ ] Completed

**Problem it solves:** Users need a visible control to request cancellation for a load task that has exceeded the 5-second display delay.

**Files it touches:**
- `app/loading/progress_dialog.py` — enable `cancellable=True`, render a Cancel button, call `token.cancel()` on click, disable the button after the first click, and update the stage label to `Cancelling…`.
- `tests/test_loading_progress_cancel_button.py` — new widget tests.

**Expected behavior:** The button is visible only when the widget is constructed with `cancellable=True`. Clicking it sets the token exactly once, disables the button, and leaves the widget visible until the coordinator acknowledges cancellation or completion.

**Acceptance criteria:**
- Test drives the button and asserts the token is cancelled.
- Test asserts a second click does not emit a second cancel action.
- Test asserts `cancellable=False` mode has no Cancel button.
- Mandatory gate passes.

### Commit 3.3 — Discard late worker-parse results after cancel
- [ ] Completed

**Problem it solves:** A worker parse can finish after the user has cancelled. Its result must not create a tab, push recent files, start validation, or replace a reloading tab.

**Files it touches:**
- `app/loading/coordinator.py` — assign each task a task id/generation id, mark cancelled tasks, hide the widget on cancel acknowledgement, and ignore `finished`/`failed` signals whose task id is cancelled or stale.
- `tests/test_loading_cancel_during_parse.py` — new tests for initial open and reload.

**Expected behavior:** Cancelling during parse returns the UI to the pre-load state. When the worker later emits success or failure, the coordinator drops the signal and records no user-facing error for the cancelled task.

**Acceptance criteria:**
- Initial-open test cancels during a slow fake parser, then emits late success; tab count and recent list remain unchanged.
- Reload test cancels during a slow fake parser, then emits late success; old tab snapshot remains unchanged.
- Late failure after cancel does not show an error dialog.
- Mandatory gate passes.

### Commit 3.4 — Cooperative cancel during chunked initial-open build
- [ ] Completed

**Problem it solves:** After parsing succeeds, initial-open model building must stop between batches when the token is cancelled and must discard the half-built off-side tree.

**Files it touches:**
- `app/loading/builder.py` — check `token.raise_if_cancelled()` between batches.
- `app/loading/coordinator.py` — handle `CancelledError` from the builder by discarding build state and skipping add-tab/recent/validation commit steps.
- `tests/test_loading_cancel_during_build.py` — new initial-open build-cancel test.

**Expected behavior:** Cancelling during build leaves the application as if the user never selected the file, except for the status bar message `Open cancelled`.

**Acceptance criteria:**
- Test asserts tab count unchanged, recent list unchanged, schema registry unchanged for that path, validation state not created, and no exception dialog shown.
- Test asserts any temporary builder state is released by the coordinator.
- Mandatory gate passes.

### Commit 3.5 — Atomic cancel-safe reload
- [ ] Completed

**Problem it solves:** Reload cancellation must not interrupt [`DiffApplier.apply()`](../undo/diff.py:13) or any in-place mutation. Cancellation is allowed only before the final reload commit point.

**Files it touches:**
- `app/loading/coordinator.py` — check the token immediately before `applying reload`; skip the commit if cancelled.
- [`state/view_state.py`](../state/view_state.py:1) — use the capture/restore helpers from Plan 2 to compare view state before and after cancelled reload.
- [`undo/diff.py`](../undo/diff.py:13) — no mid-diff cancellation; add a narrow assertion/helper only if tests need to prove diff/apply is called after the cancellation gate.
- `tests/test_loading_cancel_reload_atomic.py` — new reload cancellation tests.

**Expected behavior:** Cancelling before `applying reload` leaves old tab data, dirty flag, undo stack count and clean index, validation state, expanded paths, selection, and scroll equal to the pre-reload snapshot. Completing reload without cancellation behaves like Plan 2 reload.

**Acceptance criteria:**
- Test cancels at parse, build, and immediately-before-commit checkpoints; each preserves the full snapshot.
- Test completes reload without cancellation and asserts existing reload expectations still pass.
- Mandatory gate passes.

### Commit 3.6 — No-side-effect cancellation regression suite
- [ ] Completed

**Problem it solves:** Future refactors must not move side effects before the cancellation gate.

**Files it touches:**
- `tests/test_loading_cancel_invariants.py` — new focused regression module covering open-cancel, reload-cancel, late success discard, late failure discard, dirty-state preservation, recent-list preservation, and validation/schema non-registration.
- Existing tests in [`tests/test_reload_from_disk.py`](../tests/test_reload_from_disk.py:1) and [`tests/test_smoke_mainwindow.py`](../tests/test_smoke_mainwindow.py:1) remain complementary.

**Expected behavior:** Every side effect listed in this plan occurs only after the coordinator has checked that the task is not cancelled and is not stale.

**Acceptance criteria:**
- Regression suite includes one test for each cancellation invariant in the semantics section.
- Suite passes with `QT_QPA_PLATFORM=offscreen`.
- Mandatory gate passes.

## Deferred out of scope — hard parser termination

Cooperative cancel does not stop CPU use while [`simplejson.load()`](../io_formats/load.py:64) or [`yaml.load_all()`](../io_formats/load.py:64) is executing inside the worker thread. If product requirements later demand CPU termination within a bounded interval, create a separate plan for a `multiprocessing` or `QProcess` parser with IPC serialization, orphan-process tests, and parity tests for parsed results.
