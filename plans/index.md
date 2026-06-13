# Plans: Big-file safety, loading progress, and cancellation

These plans operationalize [`reports/big-file-loading-cancellation-review-2026-06-13.md`](../reports/big-file-loading-cancellation-review-2026-06-13.md).
Read that report first; it is the source of truth for current code paths and risks.

## Plan files (execute roughly in this order)

| Plan | File | Goal | Depends on |
|---|---|---|---|
| 0 | [`plans/00-parsing-vulnerability-tests.md`](00-parsing-vulnerability-tests.md) | Tests that find which regex/parsing functions choke on huge, versatile strings | none |
| 1 | [`plans/01-string-parsing-len-limits.md`](01-string-parsing-len-limits.md) | `len()`-based gates on expensive inference; explicit type-change bypasses gates | Plan 0 (for thresholds) |
| 2 | [`plans/02-big-file-loading-progress-bar.md`](02-big-file-loading-progress-bar.md) | Progress bar that appears only when loading exceeds 5s | Plan 1 (recommended) |
| 3 | [`plans/03-loading-cancel-button.md`](03-loading-cancel-button.md) | Cancel button on the loading progress bar with real no-side-effect semantics | Plan 2 |
| 4 | [`plans/04-tab-close-progress.md`](04-tab-close-progress.md) | Informative (no-cancel) progress widget for slow tab close/teardown | none (parallel to 2/3) |

## How to use these plans

- Each plan is a **commit-by-commit** checklist. Every step is a checkbox title.
- **Mark the checkbox `[x]` only when the step is fully done and the gate passes.**
  On a resumed run, jump to the first `[ ]` (or `[-]` in progress) box.
- Steps tagged **MILESTONE** cannot be fully specified ahead of time. They contain
  an `Investigation` block describing what must be measured/decided before the
  remaining sub-steps can be detailed. When you reach a MILESTONE, do the
  investigation, then **edit this plan** to expand the step into concrete
  sub-commits before continuing.

## Mandatory gate (applies to EVERY commit in every plan)

A box may be checked **only** when all of the following pass on a clean tree:

```bash
make lint                     # autoflake + isort + black
make check-no-reflection      # no new getattr/hasattr/TYPE_CHECKING outside allowlist
make check-editors-isolation  # editors/ stays app/documents/tree-free
make check-tree-isolation     # tree/ stays app/documents/editors/delegates/state/validation-free
make test                     # full offscreen pytest suite (currently green)
```

(`make gate` runs lint → reflection → tests; run the two isolation targets too,
since this work touches `tree/`, `editors/`, `delegates/`, and `app/`.)

Additional non-negotiables, derived from repo invariants in
[`ai-memory/repo-map.md`](../ai-memory/repo-map.md):

- **No reflection**: do not introduce `getattr`/`hasattr`/`TYPE_CHECKING`/`AttributeError`
  outside the allowlist. Tests must justify any exception with `# allow: <reason>`.
- **Tree isolation**: pure parsing/length-guard logic added under `tree/`, `core/`,
  or `tree/codecs/` must not import `app/`, `documents/`, `editors/`, `delegates/`,
  `state/`, or `validation/`.
- **Editors isolation**: concrete editor widgets must not import `app/`, `documents/`,
  or `tree/`.
- **Strict undo/redo**: any new mutation path still routes through
  `JsonTab.push_*` / `commit_set_data` → `DocumentMutationGateway` → `QUndoCommand`.
- **No `data_store.*` leaks**: external callers reach state through typed `JsonTab.*`.

## Naming conventions used by these plans

- New tunable limits live in [`settings.py`](../settings.py) as `INFERENCE_*` constants
  (see Plan 1's storage decision).
- New report artifacts are written to `reports/parsing-vulnerability-<YYYY-MM-DD>.md`.
- New test files follow the existing `tests/test_*.py` layout.
