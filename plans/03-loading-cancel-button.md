# Plan 3 — Cancel button on the loading progress bar

**Goal:** Add a **Cancel** button to the loading progress widget from
[`Plan 2`](02-big-file-loading-progress-bar.md) with *real* no-side-effect
semantics: cancelling an open adds no tab, pushes no recent file, registers no
schema/validation state; cancelling a reload leaves the existing tab fully intact.

> Hard prerequisite: Plan 2 (coordinator, delayed widget, worker parse, chunked
> build, build-then-swap reload) must be in place.

See [`plans/index.md`](index.md) for the **mandatory gate** every commit must pass.

## Definition of "REALLY cancel" (from the report)

- **Initial open** — on cancel before commit: no tab added
  ([`TabLifecyclePresenter.add_tab()`](../app/tab_lifecycle.py:64) never called or
  fully unwound), no [`push_recent()`](../app/main_window.py:316), no validation/
  schema registration, dirty state untouched, status bar shows a "cancelled" message.
- **Reload** — on cancel before atomic commit: existing tab data, dirty flag,
  undo stack, validation state, and view state remain exactly as before. Current
  [`DiffApplier.apply()`](../undo/diff.py:13) mutates in place and is **not**
  safe to interrupt mid-recursion, so reload commit must be atomic (build-then-swap
  from Plan 2, Commit 2.7).
- **Worker parse** — a cancel while `simplejson`/`yaml` is mid-parse cannot abort
  the C/Python call in-thread. First-cut semantics: the UI stops waiting, the
  late result is **discarded** on arrival. (Hard CPU kill = optional milestone.)

## Cancel scope decision (default)

**Default:** cooperative, no-side-effect cancellation with discarded late results.
Hard CPU/IO termination of an in-flight parser (worker process) is deferred to the
optional milestone at the end of this plan, since it is heavier and not required
for responsive UX.

---

## Commits

- [ ] **Commit 3.1 — Cancellation token primitive**
  - Add `app/loading/cancellation.py` with a thread-safe `CancellationToken`
    (`cancel()`, `is_cancelled`) and a `CancelledError`/sentinel for cooperative
    checkpoints. No Qt dependency beyond what's needed for thread-safety.
  - **DoD:** unit tests cover set/observe across threads; `make check-no-reflection`
    clean. Gate passes.

- [ ] **Commit 3.2 — Add Cancel button to the progress widget**
  - Extend the Plan 2 widget with a Cancel button that triggers the token. Button
    disabled/hidden when a phase is non-cancellable (e.g. mid worker parse if we
    only discard later) — but visible during chunked build.
  - **DoD:** clicking Cancel sets the token; widget shows a "cancelling…" state;
    a test drives the button and asserts the token flips. Gate passes.

- [ ] **Commit 3.3 — Cooperative cancel in chunked model build (initial open)**
  - Check the token between batches in the chunked build (Plan 2, Commit 2.5).
    On cancel: abort the build, discard the half-built off-side tree, do **not**
    add a tab, do **not** push recent, restore status bar.
  - **DoD:** test cancels mid-build and asserts: tab count unchanged, recent list
    unchanged, no schema/validation registered, no exception surfaced to the user.
    Gate passes.

- [ ] **Commit 3.4 — Discard late worker-parse results on cancel**
  - When the worker parse finishes after a cancel, the coordinator drops the
    result instead of building a tab.
  - **DoD:** test simulates cancel during parse then late `finished` signal; asserts
    no tab added and no recent push. Gate passes.

- [ ] **Commit 3.5 — MILESTONE: atomic, cancel-safe reload**
  - **Requirement:** cancelling a reload leaves the old tab untouched.
  - **Investigation required:**
    - Confirm the Plan 2 build-then-swap reload path produces a complete new
      model/tree before any mutation of the live tab.
    - Decide the apply step: (a) swap to the freshly built model (simplest atomicity,
      may lose minimal-diff view-state preservation), or (b) keep
      [`DiffApplier.apply()`](../undo/diff.py:13) but only start it **after** the
      cancellable build phase, treating the diff apply itself as the
      non-cancellable commit point.
    - If view-state preservation must survive a swap, define capture/restore of
      expanded paths/selection/scroll around the swap
      ([`state/view_state.py`](../state/view_state.py:1)).
  - After investigation, **edit this commit** into concrete sub-commits.
  - **DoD:** cancelling reload before the commit point leaves data, dirty flag,
    undo stack, validation, and view state identical (tests assert each);
    completing reload behaves as today. Gate passes.

- [ ] **Commit 3.6 — No-side-effect regression suite**
  - Add a focused test module asserting all cancel invariants in one place:
    open-cancel (no tab/recent/schema), reload-cancel (state preserved), late
    result discarded, dirty unchanged.
  - **DoD:** suite green; covers both open and reload; complements
    [`tests/test_reload_from_disk.py`](../tests/test_reload_from_disk.py:1) and
    [`tests/test_smoke_mainwindow.py`](../tests/test_smoke_mainwindow.py:1). Gate passes.

- [ ] **Commit 3.7 — OPTIONAL MILESTONE: hard CPU cancellation via worker process**
  - Only if cooperative cancel proves insufficient (a giant file wedges inside
    `simplejson.load`/`yaml.load_all` for an unacceptable time).
  - **Investigation required:** evaluate a `multiprocessing`/`QProcess` parser that
    can be terminated; measure IPC cost of returning parsed Python data; decide
    serialization (pickle vs re-parse in child and stream); confirm `gmpy2.mpq`
    values survive IPC.
  - After investigation, **edit this commit** into concrete sub-commits or split
    into its own plan.
  - **DoD:** clicking Cancel during a wedged parse frees CPU within a bounded time;
    no orphaned processes; results parity with in-thread parse. Gate passes.
