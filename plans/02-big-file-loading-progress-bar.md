# Plan 2 — Loading progress widget shown after 5 seconds

**Goal:** When opening or reloading a file remains active for at least `5000` milliseconds, show a loading progress widget with stage text. Loads that finish before `5000` milliseconds show no widget. This plan adds the coordinator, delayed widget, worker parse, progress protocol, chunked model build, validation tracking, and reload build-then-swap behavior. It does not add a Cancel button; cancellation is [`Plan 3`](03-loading-cancel-button.md).

**Prerequisite:** [`Plan 1`](01-string-parsing-len-limits.md) must land first so per-node inference is capped before loading work is moved into longer-lived orchestration.

See [`plans/index.md`](index.md) for the mandatory gate every commit must pass.

## Current blocking flow

The review report identifies this synchronous GUI-thread chain:

[`MainWindow._open_path()`](../app/main_window.py:303) → [`load_file_with_format()`](../io_formats/load.py:64) → [`_add_tab()`](../app/main_window.py:297) → [`TabLifecyclePresenter.add_tab()`](../app/tab_lifecycle.py:64) → [`create_tab()`](../documents/composition/factory.py:16) → [`bootstrap()`](../documents/composition/init.py:34) → [`init_model()`](../documents/composition/setup.py:108) → recursive [`JsonTreeItem.__init__()`](../tree/item.py:37).

A delayed widget cannot appear while this chain blocks the GUI thread. This plan therefore moves file parsing to a worker thread and converts model/tree construction into GUI-thread chunks that yield between batches.

## Worker and build decisions

- **File parse:** Run [`load_file_with_format()`](../io_formats/load.py:64) in a `QThread` worker. The worker must create no Qt widgets and emit only plain Python parse results or exception data back to the GUI thread.
- **Model/tree build:** Build the item tree/model on the GUI thread in time-sliced batches. Do not bind a partial model to the view. Bind only after the complete tree/model exists.
- **Worker process:** Hard CPU termination of a wedged parser is out of scope for Plan 2. Plan 3 keeps cooperative cancellation with late-result discard; process termination remains a separate future plan.
- **Validation/schema:** Include initial schema discovery and first validation in the tracked loading task. The progress widget must not close before validation work finishes if validation runs synchronously as part of opening/reloading.

## Required progress stages

The coordinator must emit these stages in order when the corresponding work is present:

1. `reading/parsing file`
2. `decoding number affixes`
3. `building item tree`
4. `binding UI`
5. `discovering schema`
6. `validating document`
7. `complete`

Reload uses the same stages, replacing `binding UI` with `applying reload` at the atomic commit point.

---

## Commits

### Commit 2.1 — LoadCoordinator scaffold with unchanged behavior
- [ ] Completed

**Problem it solves:** Open and reload need one owner before worker parsing, progress, and cancellation can be added.

**Files it touches:**
- `app/loading/coordinator.py` — new `LoadCoordinator` class that delegates to the current synchronous open/reload behavior.
- [`app/main_window.py`](../app/main_window.py:303) — route `_open_path()` through the coordinator.
- [`app/main_window.py`](../app/main_window.py:362) — route `_reload_tab_from_path()` through the coordinator.
- Existing open/reload tests in [`tests/test_file_io_phase4.py`](../tests/test_file_io_phase4.py:1) and [`tests/test_reload_from_disk.py`](../tests/test_reload_from_disk.py:1).

**Expected behavior:** Opening and reloading produce the same tabs, recent-file updates, status messages, dirty state, validation behavior, and exceptions as before this commit.

**Acceptance criteria:**
- Tests assert coordinator methods are invoked for open and reload.
- Existing open/reload tests pass without changed assertions.
- Mandatory gate passes.

### Commit 2.2 — Shared delayed progress widget without Cancel
- [ ] Completed

**Problem it solves:** Loading needs a widget that appears only when a task is still active after `5000` milliseconds.

**Files it touches:**
- `app/loading/progress_dialog.py` — new delayed progress widget using single-shot `QTimer` and `LOADING_PROGRESS_DELAY_MS = 5000` from [`settings.py`](../settings.py). Constructor accepts `cancellable=False`; in this plan the Cancel button is absent.
- [`settings.py`](../settings.py) — add `LOADING_PROGRESS_DELAY_MS = 5000`.
- `tests/test_loading_progress_dialog.py` — new tests with controllable timer behavior.

**Expected behavior:** `start(task_id)` arms the timer. If `finish(task_id)` happens before the timer fires, the widget never becomes visible. If the timer fires while the task is active, the widget becomes visible and hides on finish or error.

**Acceptance criteria:**
- Test covers task duration `< 5000 ms`: widget is never shown.
- Test covers task duration `>= 5000 ms`: widget is shown once and hidden on finish.
- Test confirms no Cancel button exists when `cancellable=False`.
- Mandatory gate passes.

### Commit 2.3 — Run file parsing in a worker thread
- [ ] Completed

**Problem it solves:** The GUI event loop must continue processing while JSON/YAML parsing and affix decoding run.

**Files it touches:**
- `app/loading/worker.py` — new worker `QObject` with `finished(result)`, `failed(error_payload)`, and `stage(str)` signals. It calls [`load_file_with_format()`](../io_formats/load.py:64) and emits plain Python data.
- `app/loading/coordinator.py` — starts/stops the `QThread`, receives worker signals on the GUI thread, and resumes tab build only after successful parse.
- `tests/test_loading_worker_thread.py` — new test with a slow fake parser.

**Expected behavior:** During a slow fake parser, a zero-delay GUI timer fires at least twice before parsing finishes. Parser exceptions are delivered to the same user-facing error path used before this commit.

**Acceptance criteria:**
- Test proves the GUI event loop processes events during parsing.
- Successful parse opens/reloads the same data as the synchronous path.
- Failed parse shows the same error text category as the existing `QMessageBox.critical` path.
- Worker thread is quit and deleted after success or failure.
- Mandatory gate passes.

### Commit 2.4 — Progress reporting protocol
- [ ] Completed

**Problem it solves:** The coordinator, worker, builder, and widget need a small stage/tick contract without coupling worker code to widget classes.

**Files it touches:**
- `app/loading/progress.py` — new `ProgressEvent` dataclass with `task_id`, `stage`, `done`, and `total`, plus a `ProgressReporter` protocol with `stage(name)` and `tick(done, total)`.
- `app/loading/coordinator.py` — converts worker/builder signals into `ProgressEvent` values.
- `tests/test_loading_progress_events.py` — new test for stage order.

**Expected behavior:** Stage events are emitted on the GUI thread in the order listed in this plan. `tick(done, total)` uses integer counts with `0 <= done <= total`; when total is unknown, both values are `0`.

**Acceptance criteria:**
- Normal open test observes `reading/parsing file`, `decoding number affixes`, `building item tree`, `binding UI`, schema/validation stages when applicable, and `complete`.
- No widget class is imported by the worker.
- Mandatory gate passes.

### Commit 2.5 — Chunked cooperative model/tree build
- [ ] Completed

**Problem it solves:** After worker parse succeeds, recursive model construction still blocks the GUI thread. The build must yield between batches so the delayed widget can paint and Plan 3 can check cancellation between batches.

**Files it touches:**
- `app/loading/builder.py` — new chunked builder that constructs the item tree/model off to the side using an explicit work stack and yields control after each time slice.
- [`tree/item.py`](../tree/item.py:37) and [`tree/model.py`](../tree/model.py:25) — add a builder entry point only if the new builder cannot use existing constructors without binding partial state.
- `tests/test_chunked_model_build.py` — new fixture comparison against the synchronous build.

**Expected behavior:** The builder processes batches with a target time slice of `16` milliseconds and yields after no more than `50` milliseconds in tests. The view receives no model until the build result is complete.

**Acceptance criteria:**
- Fixture comparison proves root data, item types, names, and values match the synchronous build.
- Event-loop test observes timer callbacks during a large build.
- Test asserts no partial model is assigned to the view before completion.
- Mandatory gate passes.

### Commit 2.6 — Include schema discovery and validation in loading progress
- [ ] Completed

**Problem it solves:** Initial schema discovery and first validation can add visible work after model build. The loading widget must track that work instead of closing early and leaving a second GUI freeze.

**Files it touches:**
- `app/loading/coordinator.py` — emit `discovering schema` and `validating document` stages around the current schema/validation calls.
- [`documents/controllers/validation.py`](../documents/controllers/validation.py:145) — expose a coordinator-callable validation entry point if the current call path cannot be staged without duplication.
- [`validation/schema_source.py`](../validation/schema_source.py:89) — no behavior change unless a progress hook is needed for stage boundaries.
- `tests/test_loading_validation_progress.py` — new tests for stage presence and widget lifetime.

**Expected behavior:** The progress widget remains active until schema discovery and first validation complete. There is no second delayed loading widget after the first one hides.

**Acceptance criteria:**
- Test observes validation/schema stages for a tab with schema discovery enabled.
- Test observes no duplicate show/hide cycle when validation runs longer than `5000` milliseconds.
- Mandatory gate passes.

### Commit 2.7 — Wire delayed widget to real open/reload tasks
- [ ] Completed

**Problem it solves:** Worker parsing, progress events, chunked build, and validation stages must drive the delayed widget for actual open and reload operations.

**Files it touches:**
- `app/loading/coordinator.py` — creates one progress widget per active load task, forwards stage/tick updates, and closes it on success or error.
- `tests/test_loading_progress_end_to_end.py` — new tests with fast and slow fake loads.

**Expected behavior:** A fake load shorter than `5000` milliseconds shows no widget. A fake load longer than `5000` milliseconds shows one widget with changing stage text and hides it after completion/error.

**Acceptance criteria:**
- Slow-open test observes widget visible after the delay and hidden on completion.
- Fast-open test observes zero widget shows.
- Error test observes widget hidden and the existing error path used.
- Mandatory gate passes.

### Commit 2.8 — Reload build-then-swap without cancellation
- [ ] Completed

**Problem it solves:** Plan 3 requires reload to have a single commit point. This commit changes reload to build the replacement data/model off to the side and apply it only after the replacement is complete.

**Files it touches:**
- [`app/main_window.py`](../app/main_window.py:362) and `app/loading/coordinator.py` — route reload through worker parse, chunked build, validation staging, and one final `applying reload` commit.
- [`state/view_state.py`](../state/view_state.py:1) — capture and restore expanded paths, selection, and scroll position around the swap.
- [`undo/diff.py`](../undo/diff.py:13) — keep existing undo/redo diff behavior; reload must not call diff mutation until the atomic commit decision has been made.
- [`tests/test_reload_from_disk.py`](../tests/test_reload_from_disk.py:1) plus `tests/test_loading_reload_swap.py`.

**Expected behavior:** Slow reload shows loading progress. Until the `applying reload` stage starts, the old tab data, dirty flag, undo stack, validation state, and view state remain unchanged. Completed reload preserves the view state that the old reload path preserved.

**Acceptance criteria:**
- Test snapshots old data, dirty flag, undo stack count, validation state, expanded paths, selection, and scroll before reload; all remain unchanged before commit.
- Completed reload updates data and preserves view state according to existing reload tests.
- Mandatory gate passes.
