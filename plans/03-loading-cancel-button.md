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

### Commit 3.1 — Cancellation token primitive
- [ ] Completed

**Problem it solves:** Every later change in this plan (button, cooperative build, late-result discard, atomic reload) needs a single, thread-safe way to signal "cancel" and observe "is cancelled?" from many call sites. Ad-hoc flags or Qt-only `QAtomicInt` are either error-prone or not importable from non-Qt modules.

**Files it touches:**
- `app/loading/cancellation.py` — new module with a thread-safe `CancellationToken` (`cancel()`, `is_cancelled`) and a `CancelledError`/sentinel for cooperative checkpoints. Uses whatever Qt primitives are needed for thread-safety, but exposes a plain Python API.
- A new unit test (e.g. `tests/test_loading_cancellation.py`) — covers set/observe across threads.

**DoD and gates:**
- Unit tests cover set/observe across threads.
- `make check-no-reflection` is clean.
- Mandatory gate passes.

### Commit 3.2 — Add Cancel button to the progress widget
- [ ] Completed

**Problem it solves:** The widget from Plan 2 has no way for the user to ask for cancel. We need a button that flips the cancellation token and shows a "cancelling…" state, while staying hidden/disabled in phases that are non-cancellable (e.g. mid worker parse where we only discard later).

**Files it touches:**
- `app/loading/progress_dialog.py` — extend the Plan 2 widget with a Cancel button; the button triggers the token; show a "cancelling…" state after click.
- A new test — drives the button and asserts the token flips.

**DoD and gates:**
- Clicking Cancel sets the token.
- Widget shows a "cancelling…" state.
- Test drives the button and asserts the token flips.
- Mandatory gate passes.

### Commit 3.3 — Cooperative cancel in chunked model build (initial open)
- [ ] Completed

**Problem it solves:** The chunked build from Plan 2 / Commit 2.5 yields to the event loop, which means we can check the cancellation token between batches. We must wire that check in so a mid-build cancel aborts the build, discards the half-built off-side tree, and leaves the world looking like the user never clicked Open.

**Files it touches:**
- `app/loading/coordinator.py` (or `app/loading/builder.py`) — check the token between batches; on cancel, abort the build, discard the half-built off-side tree, do **not** add a tab, do **not** push recent, restore status bar.
- A new test — cancels mid-build and asserts: tab count unchanged, recent list unchanged, no schema/validation registered, no exception surfaced to the user.

**DoD and gates:**
- Test cancels mid-build and asserts: tab count unchanged, recent list unchanged, no schema/validation registered, no exception surfaced to the user.
- Mandatory gate passes.

### Commit 3.4 — Discard late worker-parse results on cancel
- [ ] Completed

**Problem it solves:** `simplejson`/`yaml` cannot be interrupted in-thread (Commit 2.3). If the user clicks Cancel during parse, the worker will eventually emit `finished(result)` for a parse the user no longer wants. We must drop that result instead of building a tab from it.

**Files it touches:**
- `app/loading/coordinator.py` — when the worker parse finishes after a cancel, drop the result instead of building a tab.
- A new test — simulates cancel during parse, then a late `finished` signal; asserts no tab added and no recent push.

**DoD and gates:**
- Test simulates cancel during parse, then a late `finished` signal; asserts no tab added and no recent push.
- Mandatory gate passes.

### Commit 3.5 — MILESTONE: atomic, cancel-safe reload
- [ ] Completed

**Problem it solves:** A cancelled reload must leave the old tab fully intact — data, dirty flag, undo stack, validation state, and view state must all be byte-identical to the pre-reload snapshot. Today [`DiffApplier.apply()`](../undo/diff.py:13) mutates in place and is not safe to interrupt mid-recursion, so the commit point must become atomic. Getting this wrong silently corrupts user data on a Cancel click.

**Required investigations:**
- Confirm the Plan 2 / Commit 2.7 build-then-swap reload path produces a complete new model/tree before any mutation of the live tab.
- Decide the apply step: (a) swap to the freshly built model (simplest atomicity, may lose minimal-diff view-state preservation), or (b) keep [`DiffApplier.apply()`](../undo/diff.py:13) but only start it **after** the cancellable build phase, treating the diff apply itself as the non-cancellable commit point.
- If view-state preservation must survive a swap, define capture/restore of expanded paths / selection / scroll around the swap ([`state/view_state.py`](../state/view_state.py:1)).
- After investigation, expand this commit into concrete sub-commits.

**Files it touches:**
- `app/loading/coordinator.py` — gate the apply step behind the cancellation token; only run the apply (swap or `DiffApplier.apply()`) if not cancelled.
- [`undo/diff.py`](../undo/diff.py:13) — possibly a thin shim that confirms it is being called only at the commit point.
- [`state/view_state.py`](../state/view_state.py:1) — possibly capture/restore helpers.
- A new test — asserts cancelling reload before the commit point leaves data, dirty flag, undo stack, validation, and view state identical; completing reload behaves as today.

**DoD and gates:**
- Cancelling reload before the commit point leaves data, dirty flag, undo stack, validation, and view state identical (tests assert each).
- Completing reload behaves as today.
- Mandatory gate passes.

### Commit 3.6 — No-side-effect regression suite
- [ ] Completed

**Problem it solves:** Cancel invariants are easy to break with a future refactor (e.g. accidentally re-introducing `push_recent` before the commit point). We need a single focused test module that asserts all cancel invariants in one place, complementing the existing reload and smoke tests.

**Files it touches:**
- A new test module (e.g. `tests/test_loading_cancel_invariants.py`) — covers open-cancel (no tab / no recent / no schema), reload-cancel (data, dirty, undo, validation, view state preserved), late result discarded, dirty unchanged.
- Existing tests ([`tests/test_reload_from_disk.py`](../tests/test_reload_from_disk.py:1), [`tests/test_smoke_mainwindow.py`](../tests/test_smoke_mainwindow.py:1)) — remain as complements.

**DoD and gates:**
- Suite is green.
- Covers both open and reload cancel paths.
- Mandatory gate passes.

### Commit 3.7 — OPTIONAL MILESTONE: hard CPU cancellation via worker process
- [ ] Completed

**Problem it solves:** Cooperative cancel (Commits 3.3, 3.4) cannot free the CPU while `simplejson.load` / `yaml.load_all` are wedged. If a giant file wedges inside the parser for an unacceptable time, the only fix is to run the parser in a separate process that we can `terminate()`. This is heavier (IPC, serialization) and is kept as optional.

**Required investigations:**
- Evaluate a `multiprocessing` / `QProcess` parser that can be terminated.
- Measure IPC cost of returning parsed Python data to the GUI process.
- Decide serialization: pickle vs re-parse in child and stream parsed chunks.
- Confirm `gmpy2.mpq` values survive IPC (they must round-trip across the boundary).
- After investigation, expand this commit into concrete sub-commits or split it into its own plan if it's larger than expected.

**Files it touches:**
- New `app/loading/parser_process.py` (or similar) — wraps the parser in a `multiprocessing.Process` / `QProcess` with a `terminate()`-friendly lifecycle.
- `app/loading/coordinator.py` — switches to the process-based parser when the feature flag / env var is set.
- A new test — asserts clicking Cancel during a wedged parse frees CPU within a bounded time; no orphaned processes; results parity with the in-thread parser.

**DoD and gates:**
- Clicking Cancel during a wedged parse frees CPU within a bounded time.
- No orphaned processes.
- Results parity with in-thread parse.
- Mandatory gate passes.
