# Plan 4 — Informative progress widget for slow tab close

**Goal:** When closing a tab remains active longer than `1500` milliseconds, show a non-cancellable progress widget so the user sees that close/teardown is still running. Closing must complete once started; this plan does not add cancellation to tab close.

This plan can run independently of loading cancellation. It **reuses the existing shared progress widget** [`LoadingProgressDialog`](../app/loading/progress_dialog.py:16) in `app/loading/progress_dialog.py`, which already shipped with [`Plan 2`](02-big-file-loading-progress-bar.md)/[`Plan 2.5`](02.5-loading-progress-details-and-nonblocking-build.md)/[`Plan 2.6`](02.6-post-build-freeze-after-jsonmodel-finished.md). That widget already supports a `cancellable=False` mode with no Cancel button, a constructor `delay_ms` override, [`set_stage()`](../app/loading/progress_dialog.py:107) for stage text, throttled [`set_detail()`](../app/loading/progress_dialog.py:123) for a processed-count line, and [`start()`](../app/loading/progress_dialog.py:90)/[`finish()`](../app/loading/progress_dialog.py:128)/[`error()`](../app/loading/progress_dialog.py:141) lifecycle methods. Plan 4 therefore does not create the widget; it reuses it with a close-specific delay.

See [`plans/index.md`](index.md) for the mandatory gate every commit must pass.

## Current close path

[`TabLifecyclePresenter.close_tab()`](../app/tab_lifecycle.py:178) currently performs these phases on the GUI thread:

1. Confirm close (`win._confirm_close(widget)`).
2. Build reopen snapshot via `widget.root_data()`.
3. Unregister the tab from `_schema_tab_pool` (`win._schema_tab_pool.unregister(widget)`).
4. Save view state with [`view_state.save(widget)`](../state/view_state.py:1).
5. Remove the tab with `removeTab(index)`.
6. Schedule widget deletion with `widget.deleteLater()` and process deferred deletion later.

The review report identifies candidate freeze sources: deep `root_data()` traversal, view-state serialization of many expanded paths, and destruction of a large item/widget tree. Commit 4.1 measures each phase before implementation changes target the dominant cost.

## Close-progress constraints

- The widget is informational only and has no Cancel button (constructed with `cancellable=False`).
- The delayed display threshold is `CLOSE_PROGRESS_DELAY_MS = 1500`.
- If the measured dominant phase can yield, the implementation must yield between batches so the delayed timer can fire and the widget can repaint. Follow the same self-scheduling `QTimer.singleShot` slice pattern used by [`ChunkedTreeBuilder._do_work_slice()`](../app/loading/builder.py:95) (there is no shared chunking module yet).
- If the measured dominant phase is a single atomic Qt operation that cannot yield, the implementation must show the widget before entering that phase once elapsed close time has reached `1500` milliseconds, call `QCoreApplication.processEvents()` once to paint it, then complete the atomic phase. (This one-shot pump mirrors the precedent in [`LoadCoordinator._run_blocking()`](../app/loading/coordinator.py:180).)
- Normal-size tab close must keep existing reopen-closed-tab behavior.

---

## Commits

### Commit 4.1 — Measure and report close-time phases
- [x] Completed

**Problem it solves:** Implementation must target the phase that actually causes close-time freezes.

**Files it touches:**
- `tests/perf/test_close_phase_timing.py` — new perf/repro test that builds a large tab and times snapshot, schema unregister, view-state save, tab removal, `deleteLater`, and forced deferred deletion.
- `reports/close-phase-timing-<YYYY-MM-DD>.md` — new report with one timing row per phase and a summary naming the dominant phase.
- [`app/tab_lifecycle.py`](../app/tab_lifecycle.py:178) — add per-phase timing hooks guarded by a test/debug flag if tests cannot attribute phases externally.

**Expected behavior:** The report identifies the dominant phase by elapsed milliseconds and records whether the phase can be chunked/yielded or must be treated as atomic.

**Acceptance criteria:**
- Report contains timings for all six close phases listed above.
- Report names the dominant phase and the chosen implementation path: chunk/yield or atomic pre-show.
- Mandatory gate passes.

### Commit 4.2 — Reuse the shared delayed widget for close with a close delay
- [x] Completed

**Problem it solves:** Tab close needs delayed show/hide behavior; the shared widget already exists, so close must reuse it rather than duplicate timer logic, and a close-specific delay constant must exist.

**Files it touches:**
- [`settings.py`](../settings.py:88) — add `CLOSE_PROGRESS_DELAY_MS = 1500` near `LOADING_PROGRESS_DELAY_MS` (it does not exist yet).
- [`app/loading/progress_dialog.py`](../app/loading/progress_dialog.py:32) — confirm the existing `cancellable=False` + `delay_ms` constructor path supports close usage as-is; only extend it if close needs a distinct title/label. No new widget class is introduced.
- `tests/test_close_progress_dialog.py` — new tests that instantiate [`LoadingProgressDialog`](../app/loading/progress_dialog.py:16) with `cancellable=False, delay_ms=CLOSE_PROGRESS_DELAY_MS` and a controllable timer.

**Expected behavior:** The reused widget starts hidden, appears only after the configured close delay while the close task is active, displays close-stage text via [`set_stage()`](../app/loading/progress_dialog.py:107), and hides on completion or error.

**Acceptance criteria:**
- Fast-close test completes before `1500` milliseconds and observes zero widget shows.
- Slow-close test advances beyond `1500` milliseconds and observes one show followed by one hide.
- Test confirms non-cancellable close mode has no Cancel button.
- Mandatory gate passes.

### Commit 4.3 — Wrap close phases with progress ownership
- [x] Completed

**Problem it solves:** Close needs a task owner that starts the delayed widget, emits phase text, and guarantees dismissal when close finishes or errors.

**Files it touches:**
- [`app/tab_lifecycle.py`](../app/tab_lifecycle.py:178) — wrap the measured close phases in a close-progress context that emits `snapshot`, `unregistering schema`, `saving view state`, `removing tab`, and `destroying tab` stages via [`set_stage()`](../app/loading/progress_dialog.py:107), optionally using [`set_detail()`](../app/loading/progress_dialog.py:123) for a processed-item count during the dominant phase.
- `tests/test_tab_close_progress.py` — new tests for normal close, slow fake close, and error during close.

**Expected behavior:** A slow fake close shows stage text after `1500` milliseconds. A normal close finishes with no widget. An exception during close hides the widget and restores the cursor before the exception follows the existing error path.

**Acceptance criteria:**
- Test drives a slow close hook and observes widget visible with the expected stage label.
- Test drives a normal close and observes zero widget shows.
- Error test observes widget hidden and busy cursor restored.
- Mandatory gate passes.

### Commit 4.4 — Make the measured dominant phase repaint-capable
- [x] Completed

**Problem it solves:** Showing a widget is not enough if the dominant close phase blocks painting. The dominant phase from Commit 4.1 must either yield between batches or use the atomic pre-show fallback defined in this plan.

**Files it touches:**
- [`app/tab_lifecycle.py`](../app/tab_lifecycle.py:178) — implement the chosen path for the dominant phase recorded in `reports/close-phase-timing-<YYYY-MM-DD>.md`.
- `app/loading/chunking.py` — new shared batch/yield helper **only if** the chosen close path and a future refactor of the builder both want to share the self-scheduling slice pattern; otherwise follow [`ChunkedTreeBuilder._do_work_slice()`](../app/loading/builder.py:95) inline. (The Plan 2 builder does not currently use a shared chunking module.)
- [`state/view_state.py`](../state/view_state.py:1) — update only if the measured fix changes reopen snapshot or view-state capture behavior.
- `tests/test_tab_close_progress_responsive.py` — new test that verifies paint/event processing during large-tab close.

**Expected behavior:** During a large-tab close, the progress widget receives paint events after it becomes visible. Close completes and normal-size reopen snapshots remain unchanged.

**Acceptance criteria:**
- Responsiveness test observes at least one paint/event callback while close is in progress.
- Close completion removes the tab and releases the widget.
- Reopen-closed-tab tests pass for normal-size tabs.
- If the report chooses file-path-only reopen snapshots above a measured size threshold, a test asserts that threshold and documents the visible user behavior in this plan before implementation continues.
- Mandatory gate passes.

### Commit 4.5 — Error-safe dismissal and close regression coverage
- [x] Completed

**Problem it solves:** Progress UI must not leave orphan widgets, a busy cursor, or changed reopen behavior after successful or failed close attempts.

**Files it touches:**
- [`app/tab_lifecycle.py`](../app/tab_lifecycle.py:178) — ensure close-progress cleanup runs in a `finally`-equivalent path for success and error.
- `tests/test_tab_close_progress.py` — extend the module to cover normal close, slow close, error during close, reopen snapshot preservation, and repeated close/open cycles.
- Existing reopen tests — keep current assertions for normal-size tabs.

**Expected behavior:** After any close outcome, no close progress widget remains visible, the busy cursor is restored, and normal-size reopen snapshot behavior matches the pre-plan behavior.

**Acceptance criteria:**
- Tests cover success, slow success, error, and repeated close/open cycles.
- Existing reopen tests pass unchanged for normal-size tabs.
- Mandatory gate passes.
