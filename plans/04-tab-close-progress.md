# Plan 4 — Informative progress widget for slow tab close

**Goal:** When closing a tab remains active longer than `1500` milliseconds, show a non-cancellable progress widget so the user sees that close/teardown is still running. Closing must complete once started; this plan does not add cancellation to tab close.

This plan can run independently of loading cancellation. It must reuse `app/loading/progress_dialog.py` if [`Plan 2`](02-big-file-loading-progress-bar.md) has already created it. If Plan 2 has not run, Commit 4.2 creates the shared non-cancellable widget in that same module so Plan 2 can reuse it later.

See [`plans/index.md`](index.md) for the mandatory gate every commit must pass.

## Current close path

[`TabLifecyclePresenter.close_tab()`](../app/tab_lifecycle.py:138) currently performs these phases on the GUI thread:

1. Confirm close.
2. Build reopen snapshot via `widget.root_data()`.
3. Unregister the tab from `_schema_tab_pool`.
4. Save view state with `view_state.save(widget)`.
5. Remove the tab with `removeTab(index)`.
6. Schedule widget deletion with `widget.deleteLater()` and process deferred deletion later.

The review report identifies candidate freeze sources: deep `root_data()` traversal, view-state serialization of many expanded paths, and destruction of a large item/widget tree. Commit 4.1 measures each phase before implementation changes target the dominant cost.

## Close-progress constraints

- The widget is informational only and has no Cancel button.
- The delayed display threshold is `CLOSE_PROGRESS_DELAY_MS = 1500`.
- If the measured dominant phase can yield, the implementation must yield between batches so the delayed timer can fire and the widget can repaint.
- If the measured dominant phase is a single atomic Qt operation that cannot yield, the implementation must show the widget before entering that phase once elapsed close time has reached `1500` milliseconds, call `QCoreApplication.processEvents()` once to paint it, then complete the atomic phase.
- Normal-size tab close must keep existing reopen-closed-tab behavior.

---

## Commits

### Commit 4.1 — Measure and report close-time phases
- [ ] Completed

**Problem it solves:** Implementation must target the phase that actually causes close-time freezes.

**Files it touches:**
- `tests/perf/test_close_phase_timing.py` — new perf/repro test that builds a large tab and times snapshot, schema unregister, view-state save, tab removal, `deleteLater`, and forced deferred deletion.
- `reports/close-phase-timing-<YYYY-MM-DD>.md` — new report with one timing row per phase and a summary naming the dominant phase.
- [`app/tab_lifecycle.py`](../app/tab_lifecycle.py:138) — add per-phase timing hooks guarded by a test/debug flag if tests cannot attribute phases externally.

**Expected behavior:** The report identifies the dominant phase by elapsed milliseconds and records whether the phase can be chunked/yielded or must be treated as atomic.

**Acceptance criteria:**
- Report contains timings for all six close phases listed above.
- Report names the dominant phase and the chosen implementation path: chunk/yield or atomic pre-show.
- Mandatory gate passes.

### Commit 4.2 — Shared non-cancellable delayed progress widget
- [ ] Completed

**Problem it solves:** Tab close and loading need one implementation of delayed show/hide behavior instead of duplicate timer logic.

**Files it touches:**
- `app/loading/progress_dialog.py` — create or extend the shared progress widget with `cancellable=False` support and no Cancel button in that mode.
- [`settings.py`](../settings.py) — add `CLOSE_PROGRESS_DELAY_MS = 1500` if it does not exist.
- `tests/test_close_progress_dialog.py` — new tests with controllable timer behavior.

**Expected behavior:** The widget starts hidden, appears only after the configured close delay while the close task is active, displays close-stage text, and hides on completion or error.

**Acceptance criteria:**
- Fast-close test completes before `1500` milliseconds and observes zero widget shows.
- Slow-close test advances beyond `1500` milliseconds and observes one show followed by one hide.
- Test confirms non-cancellable close mode has no Cancel button.
- Mandatory gate passes.

### Commit 4.3 — Wrap close phases with progress ownership
- [ ] Completed

**Problem it solves:** Close needs a task owner that starts the delayed widget, emits phase text, and guarantees dismissal when close finishes or errors.

**Files it touches:**
- [`app/tab_lifecycle.py`](../app/tab_lifecycle.py:138) — wrap the measured close phases in a close-progress context that emits `snapshot`, `unregistering schema`, `saving view state`, `removing tab`, and `destroying tab` stages.
- `tests/test_tab_close_progress.py` — new tests for normal close, slow fake close, and error during close.

**Expected behavior:** A slow fake close shows stage text after `1500` milliseconds. A normal close finishes with no widget. An exception during close hides the widget and restores the cursor before the exception follows the existing error path.

**Acceptance criteria:**
- Test drives a slow close hook and observes widget visible with the expected stage label.
- Test drives a normal close and observes zero widget shows.
- Error test observes widget hidden and busy cursor restored.
- Mandatory gate passes.

### Commit 4.4 — Make the measured dominant phase repaint-capable
- [ ] Completed

**Problem it solves:** Showing a widget is not enough if the dominant close phase blocks painting. The dominant phase from Commit 4.1 must either yield between batches or use the atomic pre-show fallback defined in this plan.

**Files it touches:**
- [`app/tab_lifecycle.py`](../app/tab_lifecycle.py:138) — implement the chosen path for the dominant phase recorded in `reports/close-phase-timing-<YYYY-MM-DD>.md`.
- `app/loading/chunking.py` — new shared batch/yield helper if both close and Plan 2 model build need the same event-loop-yield pattern.
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
- [ ] Completed

**Problem it solves:** Progress UI must not leave orphan widgets, a busy cursor, or changed reopen behavior after successful or failed close attempts.

**Files it touches:**
- [`app/tab_lifecycle.py`](../app/tab_lifecycle.py:138) — ensure close-progress cleanup runs in a `finally`-equivalent path for success and error.
- `tests/test_tab_close_progress.py` — extend the module to cover normal close, slow close, error during close, reopen snapshot preservation, and repeated close/open cycles.
- Existing reopen tests — keep current assertions for normal-size tabs.

**Expected behavior:** After any close outcome, no close progress widget remains visible, the busy cursor is restored, and normal-size reopen snapshot behavior matches the pre-plan behavior.

**Acceptance criteria:**
- Tests cover success, slow success, error, and repeated close/open cycles.
- Existing reopen tests pass unchanged for normal-size tabs.
- Mandatory gate passes.
