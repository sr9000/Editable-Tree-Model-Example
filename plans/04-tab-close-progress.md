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

- [ ] **Commit 4.1 — MILESTONE: reproduce and locate the close-time freeze**
  - **Investigation required (cannot be pre-specified):**
    - Add a perf/repro test that builds a large tab and times each phase of
      [`close_tab()`](../app/tab_lifecycle.py:138) separately: snapshot
      (`root_data()`), `unregister`, `view_state.save`, `removeTab`, `deleteLater`
      (and the actual deletion — `deleteLater` defers; force processing).
    - Identify the dominant cost(s). Likely candidates: deep `root_data()` walk,
      destruction of the deep item tree, or view-state serialization of many
      expanded paths.
    - Decide which phases can be chunked/yielded vs which are atomic (Qt object
      deletion may need to happen on the GUI thread and may not chunk cleanly).
  - After investigation, **edit Commits 4.3+** with concrete sub-steps targeting
    the measured hotspot(s).
  - **DoD:** a committed measurement (table in `reports/` or test output) names the
    dominant close-time cost(s) for a large document. Gate passes.

- [ ] **Commit 4.2 — Shared delayed progress widget (no-cancel variant)**
  - Provide a reusable delayed progress widget supporting a "no cancel,
    informative only" mode. If [`Plan 2`](02-big-file-loading-progress-bar.md)
    already added `app/loading/progress_dialog.py`, extend it with a
    `cancellable: bool` flag; otherwise create the shared widget here.
  - Add `CLOSE_PROGRESS_DELAY_MS` to [`settings.py`](../settings.py) (e.g. 1500 ms;
    the report's 5s trigger is about *loading* — closing can use a shorter delay,
    final value decided here).
  - **DoD:** widget shows after the configured delay, has no Cancel button in this
    mode, and dismisses on completion; unit test with a fake timer covers
    fast-close (no widget) vs slow-close (widget shown then hidden). Gate passes.

- [ ] **Commit 4.3 — Show the informative widget during close**
  - Wrap the expensive portion of [`close_tab()`](../app/tab_lifecycle.py:138) so
    the delayed widget appears for slow closes. At minimum, set a busy cursor /
    show the widget before the dominant phase and hide it after.
  - **DoD:** closing a large tab shows the informative widget (test drives a
    >delay fake-slow close); closing a small tab shows nothing. Gate passes.

- [ ] **Commit 4.4 — MILESTONE: make the dominant phase yield to the event loop**
  - Depends on Commit 4.1's findings.
  - **Investigation/implementation:** chunk the measured hotspot so the widget
    actually paints during the freeze:
    - If `root_data()` snapshot dominates: build the reopen snapshot in time-sliced
      batches (yield via `processEvents()`), or capture it lazily/skip it for very
      large tabs (decision: is a reopen snapshot worth the freeze? possibly store a
      file-path-only snapshot above a size threshold, mirroring the existing
      discard-path behavior in [`close_tab()`](../app/tab_lifecycle.py:148)).
    - If item-tree destruction dominates: investigate whether deletion can be
      sliced (e.g. detaching children in batches before `deleteLater`) or whether
      only a "please wait" widget is feasible because Qt teardown is atomic.
  - After investigation, **edit this commit** into concrete sub-commits.
  - **DoD:** during a large-tab close the widget remains responsive/painted (not a
    white frozen rectangle); close still completes correctly; reopen-closed-tab
    behavior is preserved or its trade-off (file-path-only snapshot above threshold)
    is documented and tested. Gate passes.

- [ ] **Commit 4.5 — Robust dismissal + regression coverage**
  - Ensure the widget is always hidden on completion or error, the busy cursor is
    restored, and reopen snapshot / `closed_tabs_stack` behavior is unchanged for
    normal-size tabs.
  - **DoD:** tests cover normal close (no widget, snapshot intact), slow close
    (widget shown then hidden), and error-during-close (widget still dismissed);
    reopen tests pass. Gate passes.
