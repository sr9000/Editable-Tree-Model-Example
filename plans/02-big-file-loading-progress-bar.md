# Plan 2 — Loading progress bar that appears only after 5 seconds

**Goal:** When opening or reloading a file takes longer than **5 seconds**, show
a progress widget. The 5s is purely a *trigger to reveal* the widget — fast loads
must show nothing. This plan adds the coordinator, the delayed widget, and the
off-GUI-thread / chunked work needed for the widget to actually paint. **No cancel
button yet** (that is [`Plan 3`](03-loading-cancel-button.md)).

> Prerequisite: [`Plan 1`](01-string-parsing-len-limits.md) should land first.
> Without it, per-node inference can still dominate load time; with it, progress
> stages reflect genuine structural work.

See [`plans/index.md`](index.md) for the **mandatory gate** every commit must pass.

## Current blocking flow (from the report)

Everything runs synchronously on the GUI thread:
[`MainWindow._open_path()`](../app/main_window.py:303) →
[`load_file_with_format()`](../io_formats/load.py:64) →
[`_add_tab()`](../app/main_window.py:297) →
[`TabLifecyclePresenter.add_tab()`](../app/tab_lifecycle.py:64) →
[`create_tab()`](../documents/composition/factory.py:16) →
[`bootstrap()`](../documents/composition/init.py:34) →
[`init_model()`](../documents/composition/setup.py:108) →
recursive [`JsonTreeItem.__init__()`](../tree/item.py:37).

A delayed dialog **cannot appear** while this blocks the GUI thread, so the work
must move off-thread or be chunked with event-loop yielding.

## Worker strategy — DECISION (default chosen; confirm at Commit 2.3)

The report lists three options. **Default decision:**

- **File parse → `QThread` worker.** `simplejson.load` / `yaml.load_all` are not
  cooperative and not interruptible in-thread, but a worker keeps the GUI
  responsive; on cancel (Plan 3) we discard late results.
- **Model/tree build → chunked cooperative build on the GUI thread.** Building Qt
  model items off-thread is fragile; instead build in time-sliced batches that
  yield to the event loop so the progress widget paints and (later) Cancel works.
- **Worker *process*** (hard CPU kill) is explicitly deferred to a Plan 3
  milestone; not required for the 5s-trigger progress bar.

This split is a recommendation; Commit 2.3 confirms feasibility before deeper work.

## Progress stages (coarse, from the report)

`reading → parsing → decoding affixes → building item tree → binding UI → (validation?)`

Whether validation/schema discovery is inside the 5s-tracked work is a **scope
decision** finalized at Commit 2.8.

---

## Commits

- [ ] **Commit 2.1 — LoadCoordinator scaffold (no behavior change)**
  - Add `app/loading/coordinator.py` with a `LoadCoordinator` that today simply
    calls the existing synchronous open/reload and returns the same result.
    Route [`_open_path()`](../app/main_window.py:303) and
    [`_reload_tab_from_path()`](../app/main_window.py:362) through it.
  - **DoD:** behavior byte-for-byte identical; existing open/reload tests
    ([`tests/test_file_io_phase4.py`](../tests/test_file_io_phase4.py:1),
    [`tests/test_reload_from_disk.py`](../tests/test_reload_from_disk.py:1)) pass
    unchanged. Gate passes.

- [ ] **Commit 2.2 — Delayed progress widget (timer only, not yet shown for real work)**
  - Add `app/loading/progress_dialog.py`: an indeterminate progress widget owned
    by the coordinator, armed by a single-shot `QTimer` (`LOADING_PROGRESS_DELAY_MS = 5000`
    in [`settings.py`](../settings.py)); shows only if the task is still active when
    the timer fires; hidden on finish/error.
  - **DoD:** unit test with a fake/advanced timer proves: task < 5s ⇒ widget never
    shown; task ≥ 5s ⇒ widget shown then hidden. No real loading wired yet. Gate passes.

- [ ] **Commit 2.3 — MILESTONE: move file parse to a worker thread**
  - **Investigation required:**
    - Confirm `simplejson`/`yaml`/`gmpy2.mpq`/`MpqSafeLoader` are safe to run in a
      `QThread` worker and that the resulting Python object can cross the thread
      boundary (it's plain Python data — verify no Qt objects created in parse).
    - Choose marshaling: `QThread` + worker `QObject` with `finished(result)` /
      `failed(exc)` signals delivered to the GUI thread.
    - Decide error propagation parity with current `QMessageBox.critical` behavior.
  - Implement: coordinator runs [`load_file_with_format()`](../io_formats/load.py:64)
    in the worker; on success it resumes the existing (still synchronous) tab build
    on the GUI thread.
  - After investigation, **edit this commit** into concrete sub-commits.
  - **DoD:** open/reload still produce identical results; GUI thread no longer
    blocks during file parse (a test asserts the event loop processes events while
    a slow fake parser runs). Gate passes.

- [ ] **Commit 2.4 — Progress reporting protocol**
  - Add a tiny `ProgressReporter` protocol (`stage(name)`, `tick(done, total)`)
    in `app/loading/`. Coordinator emits coarse stages; widget renders current
    stage text. Keep it Qt-thread-safe (signals).
  - **DoD:** stages fire in order for a normal open (assert recorded stage
    sequence in a test). Gate passes.

- [ ] **Commit 2.5 — MILESTONE: chunked cooperative model build**
  - **Investigation required:**
    - Determine how to build [`JsonTreeModel`](../tree/model.py:25) /
      [`JsonTreeItem`](../tree/item.py:37) incrementally. Today construction is
      fully recursive in `__init__`. Options: (a) build the item tree in time-sliced
      batches before constructing the model, yielding via
      `QCoreApplication.processEvents()` between batches; (b) build fully but emit
      `tick` progress and rely on Plan 1 to keep per-node cost low.
    - Decide a batch size / time-slice (e.g. yield every ~16 ms) and how to count
      total nodes for the progress fraction without a full pre-walk (estimate vs
      two-pass).
    - Confirm no partial/garbage model is ever bound to the view (build off to the
      side, bind once complete) — this also sets up Plan 3 cancel and reload swap.
  - After investigation, **edit this commit** into concrete sub-commits.
  - **DoD:** opening a large file keeps the UI responsive and reports build
    progress; the view is only bound to a fully-built model; results identical to
    synchronous build (fixture comparison). Gate passes.

- [ ] **Commit 2.6 — Wire stages to the delayed widget for real loads**
  - Connect coordinator stages/ticks to the 5s-delayed widget for both worker
    parse and chunked build.
  - **DoD:** a deliberately slow (>5s) fake load shows the widget with advancing
    stage text; a fast load shows nothing. Gate passes.

- [ ] **Commit 2.7 — Reload via build-then-swap (no cancel yet)**
  - Change [`_reload_tab_from_path()`](../app/main_window.py:362) to build the new
    data/model off to the side (with progress) and then apply. Decide whether to
    keep [`DiffApplier.apply()`](../undo/diff.py:13) (minimal-diff, preserves view
    state) as the final apply step or to swap the model wholesale.
  - **Note:** minimal-diff vs atomic-swap is also raised in Plan 3; keep the apply
    step isolated so Plan 3 can make it cancel-safe.
  - **DoD:** reload still preserves view state where it did before; slow reload
    (>5s) shows progress; reload tests pass. Gate passes.

- [ ] **Commit 2.8 — DECISION: validation/schema scope inside the 5s window**
  - Decide whether post-build [`TabValidationController.revalidate()`](../documents/controllers/validation.py:145)
    and [`discover_schema()`](../validation/schema_source.py:89) are tracked by the
    progress widget or run after the widget closes.
  - **Investigation:** measure typical validation cost on a large doc to decide.
  - Implement the chosen behavior; document it in this file.
  - **DoD:** behavior documented and tested (stage present or explicitly excluded);
    no double-shown/again-after-close flicker. Gate passes.
