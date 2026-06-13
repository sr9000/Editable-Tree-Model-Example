# Plan 4 — Informative progress widget for slow tab close (no cancel)

**Goal:** Closing a tab that holds a huge document currently causes a long UI
freeze. Show an **informative** progress widget (no Cancel button — closing must
complete) when teardown exceeds a small delay, so the user knows the app is busy
rather than hung.

> This plan is independent of Plans 2/3 but should **reuse** the delayed-widget
> infrastructure from [`Plan 2`](02-big-file-loading-progress-bar.md) (the
> `QTimer`-armed progress widget) rather than building a second one. If Plan 2 is
> not yet done, Commit 4.2 extracts the shared widget first.

See [`plans/index.md`](index.md) for the **mandatory gate** every commit must pass.

## What happens on close today

[`TabLifecyclePresenter.close_tab()`](../app/tab_lifecycle.py:138):
1. `confirm_close` prompt,
2. build reopen snapshot via `widget.root_data()` (full tree → Python data),
3. `_schema_tab_pool.unregister(widget)`,
4. `view_state.save(widget)`,
5. `removeTab(index)` + `widget.deleteLater()`.

For a huge tree, the freeze likely comes from (b) `root_data()` deep-walking the
tree and/or (e) destroying a very large `JsonTreeItem`/Qt item tree (Python GC +
Qt object teardown). The exact dominant cost **must be measured** (Commit 4.1).

---

## Commits

### Commit 4.1 — MILESTONE: reproduce and locate the close-time freeze
- [ ] Completed

**Problem it solves:** Closing a huge tab freezes the UI for an unacceptable time, but we don't know *which* phase of [`close_tab()`](../app/tab_lifecycle.py:138) is dominant. The dominant phase determines whether the freeze is fixable by chunking (e.g. `root_data()` snapshot) or only by a "please wait" widget (e.g. atomic Qt object teardown). All later commits depend on this measurement.

**Required investigations:**
- Add a perf/repro test that builds a large tab and times each phase of [`close_tab()`](../app/tab_lifecycle.py:138) separately: snapshot (`root_data()`), `unregister`, `view_state.save`, `removeTab`, `deleteLater` (and the actual deletion — `deleteLater` defers; force processing).
- Identify the dominant cost(s). Likely candidates: deep `root_data()` walk, destruction of the deep item tree, or view-state serialization of many expanded paths.
- Decide which phases can be chunked / yielded vs which are atomic (Qt object deletion may need to happen on the GUI thread and may not chunk cleanly).
- After investigation, expand Commits 4.3+ with concrete sub-steps targeting the measured hotspot(s).

**Files it touches:**
- A new perf/repro test (e.g. `tests/perf/test_close_phase_timing.py`) — measures each phase on a large tab.
- A new report in `reports/close-phase-timing-<date>.md` (or test output) — names the dominant close-time cost(s).
- [`app/tab_lifecycle.py`](../app/tab_lifecycle.py:138) — possibly add per-phase timing instrumentation (guarded by a debug flag) so the test can attribute cost.

**DoD and gates:**
- A committed measurement (table in `reports/` or test output) names the dominant close-time cost(s) for a large document.
- Mandatory gate passes.

### Commit 4.2 — Shared delayed progress widget (no-cancel variant)
- [ ] Completed

**Problem it solves:** Plan 4 needs a *non-cancellable* version of the Plan 2 delayed widget. Building a second, similar widget would duplicate the `QTimer` + show/hide logic. The widget should accept a `cancellable: bool` flag (or be extracted as a shared primitive) so both plans share one implementation.

**Files it touches:**
- `app/loading/progress_dialog.py` — if Plan 2 already added this module, extend it with a `cancellable: bool` flag (no Cancel button when `False`). Otherwise, create the shared widget here and have Plan 2 import it.
- [`settings.py`](../settings.py) — add `CLOSE_PROGRESS_DELAY_MS` (e.g. 1500 ms; the report's 5s trigger is about *loading* — closing can use a shorter delay, final value decided here).
- A new unit test — uses a fake timer to cover fast-close (no widget) vs slow-close (widget shown then hidden). Confirms no Cancel button in the `cancellable=False` mode.

**DoD and gates:**
- Widget shows after the configured delay, has no Cancel button in non-cancellable mode, and dismisses on completion.
- Unit test with a fake timer covers fast-close (no widget) vs slow-close (widget shown then hidden).
- Mandatory gate passes.

### Commit 4.3 — Show the informative widget during close
- [ ] Completed

**Problem it solves:** Even if the freeze from Commit 4.1's findings is not yet fixable by chunking, we can at least show a "please wait" widget so the user knows the app is busy. This is the user-facing fix that is safe to land independently of the deeper chunking work in Commit 4.4.

**Files it touches:**
- [`app/tab_lifecycle.py`](../app/tab_lifecycle.py:138) — wrap the expensive portion of `close_tab()` so the delayed widget appears for slow closes. At minimum, set a busy cursor / show the widget before the dominant phase and hide it after.
- A new test — drives a deliberately slow close (using a fake-slow hook) and asserts the widget is shown; drives a normal close and asserts the widget is not shown.

**DoD and gates:**
- Closing a large tab shows the informative widget (test drives a slow close).
- Closing a small tab shows nothing.
- Mandatory gate passes.

### Commit 4.4 — MILESTONE: make the dominant phase yield to the event loop
- [ ] Completed

**Problem it solves:** The widget from Commit 4.3 only *appears* — it doesn't repaint during the freeze, because the dominant phase blocks the GUI thread. We must chunk / yield in the measured hotspot so the widget actually paints and the user sees a live progress indicator rather than a frozen rectangle.

**Required investigations (depend on Commit 4.1's findings):**
- If `root_data()` snapshot dominates: build the reopen snapshot in time-sliced batches (yield via `processEvents()`), or capture it lazily / skip it for very large tabs (decision: is a reopen snapshot worth the freeze? possibly store a file-path-only snapshot above a size threshold, mirroring the existing discard-path behavior in [`close_tab()`](../app/tab_lifecycle.py:148)).
- If item-tree destruction dominates: investigate whether deletion can be sliced (e.g. detaching children in batches before `deleteLater`) or whether only a "please wait" widget is feasible because Qt teardown is atomic.
- After investigation, expand this commit into concrete sub-commits.

**Files it touches:**
- [`app/tab_lifecycle.py`](../app/tab_lifecycle.py:138) — chunk the dominant phase (likely `root_data()` or tree destruction).
- Possibly a new helper in `app/loading/` (e.g. `chunked_walk`) shared with Plan 2's chunked build.
- A new test — asserts the widget repaints during a large-tab close (no frozen rectangle).
- Possibly [`state/view_state.py`](../state/view_state.py:1) — if the file-path-only snapshot decision is taken.

**DoD and gates:**
- During a large-tab close the widget remains responsive / painted (not a white frozen rectangle).
- Close still completes correctly.
- Reopen-closed-tab behavior is preserved, or its trade-off (file-path-only snapshot above threshold) is documented and tested.
- Mandatory gate passes.

### Commit 4.5 — Robust dismissal + regression coverage
- [ ] Completed

**Problem it solves:** The widget must always dismiss on completion or error (no orphan widgets, no leftover busy cursor). The reopen snapshot / `closed_tabs_stack` behavior must remain unchanged for normal-size tabs. A focused regression test module guards against future drift.

**Files it touches:**
- [`app/tab_lifecycle.py`](../app/tab_lifecycle.py:138) — ensure the widget is always hidden on completion or error, the busy cursor is restored, and the reopen snapshot / `closed_tabs_stack` behavior is unchanged for normal-size tabs.
- A new test module (e.g. `tests/test_tab_close_progress.py`) — covers normal close (no widget, snapshot intact), slow close (widget shown then hidden), and error-during-close (widget still dismissed).
- Existing reopen tests — must continue to pass.

**DoD and gates:**
- Tests cover normal close (no widget, snapshot intact), slow close (widget shown then hidden), and error-during-close (widget still dismissed).
- Reopen tests pass.
- Mandatory gate passes.
