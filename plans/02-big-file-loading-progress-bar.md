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

### Commit 2.1 — LoadCoordinator scaffold (no behavior change)
- [ ] Completed

**Problem it solves:** Every later change in this plan (worker parse, chunked build, delayed widget, cancel) needs a single owner to route open/reload through. Today the call chain runs synchronously across `MainWindow`, `load_file_with_format`, and `TabLifecyclePresenter.add_tab` — there is no seam to intercept.

**Files it touches:**
- `app/loading/coordinator.py` — new module with a `LoadCoordinator` that today simply calls the existing synchronous open/reload and returns the same result.
- [`app/main_window.py`](../app/main_window.py:303) — route `_open_path()` through the coordinator.
- [`app/main_window.py`](../app/main_window.py:362) — route `_reload_tab_from_path()` through the coordinator.

**DoD and gates:**
- Behavior is byte-for-byte identical to the pre-existing open/reload path.
- Existing open/reload tests ([`tests/test_file_io_phase4.py`](../tests/test_file_io_phase4.py:1), [`tests/test_reload_from_disk.py`](../tests/test_reload_from_disk.py:1)) pass unchanged.
- Mandatory gate passes.

### Commit 2.2 — Delayed progress widget (timer only, not yet shown for real work)
- [ ] Completed

**Problem it solves:** The 5s-trigger contract requires a widget that arms a `QTimer` and only reveals itself if the task is still active when the timer fires. We need that widget in isolation (driven by a fake/advanced timer) before wiring it to real loads.

**Files it touches:**
- `app/loading/progress_dialog.py` — new module; an indeterminate progress widget owned by the coordinator, armed by a single-shot `QTimer` (`LOADING_PROGRESS_DELAY_MS = 5000` in [`settings.py`](../settings.py)); shown only if the task is still active when the timer fires; hidden on finish/error.
- A new unit test (e.g. `tests/test_loading_progress_dialog.py`) — uses a fake/advanced timer to prove: task < 5s ⇒ widget never shown; task ≥ 5s ⇒ widget shown then hidden.

**DoD and gates:**
- Unit test with a fake/advanced timer proves the < 5s vs ≥ 5s contract.
- No real loading wired yet.
- Mandatory gate passes.

### Commit 2.3 — MILESTONE: move file parse to a worker thread
- [ ] Completed

**Problem it solves:** The delayed widget from Commit 2.2 cannot paint while the GUI thread is blocked inside `simplejson.load` / `yaml.load_all`. The parse must move to a `QThread` worker so the GUI thread keeps spinning events and the widget can render. This is the load-bearing change for the whole plan.

**Required investigations:**
- Confirm `simplejson` / `yaml` / `gmpy2.mpq` / `MpqSafeLoader` are safe to run in a `QThread` worker and that the resulting Python object can cross the thread boundary (it's plain Python data — verify no Qt objects are created during parse).
- Choose marshaling: `QThread` + worker `QObject` with `finished(result)` / `failed(exc)` signals delivered to the GUI thread.
- Decide error-propagation parity with the current `QMessageBox.critical` behavior.
- After investigation, expand this commit into concrete sub-commits.

**Files it touches:**
- `app/loading/coordinator.py` — runs [`load_file_with_format()`](../io_formats/load.py:64) in the worker; on success it resumes the existing (still synchronous) tab build on the GUI thread.
- New worker `QObject` in `app/loading/worker.py` (or inline) — emits `finished(result)` / `failed(exc)`.
- A new test — asserts the GUI thread processes events while a slow fake parser runs (event loop not blocked).

**DoD and gates:**
- Open/reload still produce identical results.
- GUI thread no longer blocks during file parse (test asserts the event loop processes events while a slow fake parser runs).
- Mandatory gate passes.

### Commit 2.4 — Progress reporting protocol
- [ ] Completed

**Problem it solves:** The widget needs a way to receive coarse stage updates ("reading", "parsing", "building tree", …) from the coordinator, but we don't want the coordinator to know about the widget. A small, Qt-thread-safe protocol decouples them and keeps signal-slot delivery idiomatic.

**Files it touches:**
- `app/loading/progress.py` (or a sub-module) — new `ProgressReporter` protocol with `stage(name)` and `tick(done, total)`.
- `app/loading/coordinator.py` — emits coarse stages; the widget renders the current stage text. Use signals to stay Qt-thread-safe.

**DoD and gates:**
- A test asserts stages fire in the expected order for a normal open.
- Mandatory gate passes.

### Commit 2.5 — MILESTONE: chunked cooperative model build
- [ ] Completed

**Problem it solves:** Even with the parse moved off-thread, model/tree construction is fully recursive in [`JsonTreeItem.__init__()`](../tree/item.py:37) and runs on the GUI thread, which would still freeze long enough to prevent the progress widget from painting and (in Plan 3) Cancel from working. We need to build incrementally with event-loop yielding, but **without** ever binding a partial/garbage model to the view.

**Required investigations:**
- Determine how to build [`JsonTreeModel`](../tree/model.py:25) / [`JsonTreeItem`](../tree/item.py:37) incrementally. Today construction is fully recursive in `__init__`. Options: (a) build the item tree in time-sliced batches *before* constructing the model, yielding via `QCoreApplication.processEvents()` between batches; (b) build fully but emit `tick` progress and rely on Plan 1 to keep per-node cost low.
- Decide a batch size / time-slice (e.g. yield every ~16 ms) and how to count total nodes for the progress fraction without a full pre-walk (estimate vs two-pass).
- Confirm no partial/garbage model is ever bound to the view (build off to the side, bind once complete) — this also sets up Plan 3 cancel and reload swap.
- After investigation, expand this commit into concrete sub-commits.

**Files it touches:**
- `app/loading/coordinator.py` (or a new `app/loading/builder.py`) — chunked cooperative build with yields.
- [`tree/model.py`](../tree/model.py:25) / [`tree/item.py`](../tree/item.py:37) — possibly a builder entry point, but **only** if it does not break tree isolation.
- A new test (fixture comparison) — asserts results are identical to the synchronous build.

**DoD and gates:**
- Opening a large file keeps the UI responsive and reports build progress.
- The view is only bound to a fully-built model.
- Results are identical to the synchronous build (fixture comparison).
- Mandatory gate passes.

### Commit 2.6 — Wire stages to the delayed widget for real loads
- [ ] Completed

**Problem it solves:** The delayed widget (Commit 2.2), the worker parse (Commit 2.3), the progress protocol (Commit 2.4), and the chunked build (Commit 2.5) all exist in isolation. We must connect them end-to-end so a slow real load actually shows the widget with advancing stage text, while a fast load shows nothing.

**Files it touches:**
- `app/loading/coordinator.py` — wires worker-parse stages and chunked-build ticks into the 5s-delayed widget.
- A new test — uses a deliberately slow (>5s) fake load to assert the widget appears with advancing stage text, and a fast load to assert the widget never appears.

**DoD and gates:**
- A deliberately slow (>5s) fake load shows the widget with advancing stage text.
- A fast load shows nothing.
- Mandatory gate passes.

### Commit 2.7 — Reload via build-then-swap (no cancel yet)
- [ ] Completed

**Problem it solves:** Reload currently mutates the live tab in place, so a slow reload (or an interrupted one) leaves the tab in a half-updated state. Plan 3 will require a fully-built replacement before any commit point; this commit lays the groundwork (without cancel) so Plan 3 can drop in cancel-safety later.

**Files it touches:**
- [`app/main_window.py`](../app/main_window.py:362) — change `_reload_tab_from_path()` to build the new data/model off to the side (with progress) and then apply.
- [`undo/diff.py`](../undo/diff.py:13) — possibly a thin shim around `DiffApplier.apply()`; the apply step stays isolated so Plan 3 can make it cancel-safe.
- Reload tests ([`tests/test_reload_from_disk.py`](../tests/test_reload_from_disk.py:1)) — must still pass.

**DoD and gates:**
- Reload still preserves view state where it did before.
- Slow reload (>5s) shows the progress widget.
- Reload tests pass.
- Mandatory gate passes.

### Commit 2.8 — DECISION: validation/schema scope inside the 5s window
- [ ] Completed

**Problem it solves:** Post-build validation and schema discovery can be expensive on a large doc. We must decide whether they are part of the 5s-tracked work (and therefore potentially shown in the progress widget) or run after the widget closes. The wrong choice either double-flashes the widget or hides real work from the user.

**Required investigations:**
- Measure typical validation cost (e.g. on a 100 MB doc) for [`TabValidationController.revalidate()`](../documents/controllers/validation.py:145) and [`discover_schema()`](../validation/schema_source.py:89) to decide.
- Implement the chosen behavior; document it in this file.
- (No implementation sub-commits needed if the decision is "run after the widget closes".)

**Files it touches:**
- `app/loading/coordinator.py` — possibly stage validation, possibly defer it past `widget.hide()`.
- [`documents/controllers/validation.py`](../documents/controllers/validation.py:145) — possibly re-ordering.
- A new test — asserts the chosen behavior (stage present or explicitly excluded) and asserts no double-shown / again-after-close flicker.

**DoD and gates:**
- Behavior is documented in this file and tested.
- No double-shown / again-after-close flicker.
- Mandatory gate passes.
