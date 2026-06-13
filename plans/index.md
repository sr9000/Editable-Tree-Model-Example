# Plans: Big-file safety, loading progress, cancellation, and close progress

These plans operationalize [`reports/big-file-loading-cancellation-review-2026-06-13.md`](../reports/big-file-loading-cancellation-review-2026-06-13.md). Use the report as the source for current code paths and risks, and use [`ai-memory/repo-map.md`](../ai-memory/repo-map.md) for repository boundaries and invariants.

## Execution order and dependencies

| Plan | File | Goal | Dependency |
|---|---|---|---|
| 0 | [`plans/00-parsing-vulnerability-tests.md`](00-parsing-vulnerability-tests.md) | Measure parsing, regex, decode, formatting, and search hotspots with adversarial strings | None |
| 1 | [`plans/01-string-parsing-len-limits.md`](01-string-parsing-len-limits.md) | Add `len()` gates for automatic inference and preserve explicit type-change parsing | Plan 0 Commit 0.8 report and threshold confirmation |
| 2 | [`plans/02-big-file-loading-progress-bar.md`](02-big-file-loading-progress-bar.md) | Show loading progress only after a load remains active for `5000` milliseconds | Plan 1 complete |
| 3 | [`plans/03-loading-cancel-button.md`](03-loading-cancel-button.md) | Add Cancel to loading progress with no-side-effect semantics before commit points | Plan 2 complete |
| 4 | [`plans/04-tab-close-progress.md`](04-tab-close-progress.md) | Show non-cancellable close progress after close remains active for `1500` milliseconds | None; reuses Plan 2 widget when present |

Plan 4 may run before Plans 2 and 3. If it does, Commit 4.2 creates the shared delayed progress widget in `app/loading/progress_dialog.py`; Plan 2 must reuse that module instead of creating a second widget.

## How to execute a plan

- Each plan is a commit-by-commit checklist.
- Mark a checkbox `[x]` only after the commit's acceptance criteria and the mandatory gate pass on a clean tree.
- On a resumed run, continue at the first `[ ]` or `[-]` checkbox.
- A `MILESTONE` commit performs a measurement or report-writing step with concrete outputs. Do not implement later commits that depend on a milestone until the milestone report or plan edit named in its acceptance criteria exists.
- Do not add application code while editing plans. Implementation requires Code mode or another implementation-capable mode.

## Mandatory gate for every implementation commit

A checkbox may be checked only when all commands below pass on a clean tree:

```bash
make lint
make check-no-reflection
make check-editors-isolation
make check-tree-isolation
make test
```

`make gate` runs lint, reflection checks, editor isolation, tree isolation, and tests. If `make gate` is present and current, it can replace the five commands above only after verifying that it still includes both isolation targets.

## Additional commands for performance/report milestones

Plan 0 performance checks are opt-in and are not part of the default `make test` gate until a future plan changes that policy.

```bash
PYTEST_PERF_STRICT=1 pytest -m perf tests/perf --parsing-report reports/parsing-vulnerability-<YYYY-MM-DD>.md
```

Plan 4 close-phase timing must write or update this report before close-progress implementation continues:

```bash
pytest -m perf tests/perf/test_close_phase_timing.py --close-report reports/close-phase-timing-<YYYY-MM-DD>.md
```

## Repository invariants used by all plans

- **No reflection:** Do not introduce `getattr`, `hasattr`, `TYPE_CHECKING`, or `AttributeError` outside the allowlist. Tests that need an exception must include the repository-required `# allow: <reason>` annotation.
- **Tree isolation:** New code under `tree/`, `core/`, or `tree/codecs/` must not import `app/`, `documents/`, `editors/`, `delegates/`, `state/`, or `validation/`.
- **Editors isolation:** Concrete editor widgets must not import `app/`, `documents/`, or `tree/`.
- **Strict undo/redo:** User mutations still route through `JsonTab.push_*` or `commit_set_data` → `DocumentMutationGateway` → `QUndoCommand`.
- **No `data_store.*` leaks:** External callers reach document state through typed `JsonTab.*` APIs.
- **No partial model binding:** Loading and reload work must not bind partially built tree/model state to a view.
- **Atomic reload cancellation:** Reload cancellation is valid before the final commit point only; do not add mid-diff cancellation without rollback support.

## Artifact naming

- Inference safety constants live in [`settings.py`](../settings.py) as `INFERENCE_*`, `EDITABLE_DECODE_LIMIT_BYTES`, and `FORMAT_PREVIEW_DECODE_LIMIT_BYTES`.
- Loading and close progress delays live in [`settings.py`](../settings.py) as `LOADING_PROGRESS_DELAY_MS = 5000` and `CLOSE_PROGRESS_DELAY_MS = 1500`.
- Parsing reports are written to `reports/parsing-vulnerability-<YYYY-MM-DD>.md`.
- Close timing reports are written to `reports/close-phase-timing-<YYYY-MM-DD>.md`.
- New tests use `tests/test_*.py` for default-suite tests and `tests/perf/test_*.py` for opt-in performance/report tests.
