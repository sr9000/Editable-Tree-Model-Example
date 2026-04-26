# Roadmap — Phased Plan

_Last updated: 2026-04-26_

The work captured in `todo-n-fixme.md` has been split into **7 sequential
phases**. Each phase is a self-contained milestone: it can be merged,
released, and tested before the next one starts.

Phases are ordered so that:
- earlier phases unblock later ones (e.g. fixing tree-mutation bugs before
  building paste/undo on top),
- the app becomes incrementally usable as a real editor rather than a demo,
- pure code-hygiene work happens early so future diffs are smaller.

## Phase index

| # | File | Theme | Status |
|---|------|-------|--------|
| 0 | [`phase-0-stabilize.md`](phase-0-stabilize.md) | Stabilize: fix critical runtime bugs, dead imports, failing test, embedded C++ blocks | ✅ done |
| 1 | [`phase-1-tree-correctness.md`](phase-1-tree-correctness.md) | Tree/model correctness: insertion semantics, naming, type-detection robustness, `flags()` hot-path | ✅ done |
| 2 | [`phase-2-type-editing.md`](phase-2-type-editing.md) | Type & name editing: wire `JsonTypeDelegate`, rename, value coercion, type pinning | ✅ done |
| 3 | [`phase-3-tree-actions.md`](phase-3-tree-actions.md) | Tree mutation actions: cut / copy / paste / delete / duplicate / move / sort, plus typed-command undo/redo | ✅ done |
| 3.x | [`phase-3-compensating-undo-plan.md`](phase-3-compensating-undo-plan.md) | Phase 3 follow-up: replace whole-document snapshot history with typed action/compensation commands | ✅ done |
| 4 | [`phase-4-file-io.md`](phase-4-file-io.md) | File I/O: open / save / save-as JSON & YAML, dirty state, close-tab, recent files | in progress (core wired) |
| 5 | [`phase-5-ux-polish.md`](phase-5-ux-polish.md) | UX polish: `displayText`, status bar, persisted column widths & expansion, search/filter — **split into 5.1–5.6 below** | not started |
| 5.1 | [`phase-5.1-carryover-and-foundations.md`](phase-5.1-carryover-and-foundations.md) | Phase-3 carry-over: auto-reopen value editor, dialog `commit_set_data` routing, decode try/except, `mergeWith` on edit/rename | ✅ done |
| 5.2 | [`phase-5.2-display-formatting.md`](phase-5.2-display-formatting.md) | Raw `EditRole`, `ValueDelegate.displayText`, `ToolTipRole` for long values | not started |
| 5.3 | [`phase-5.3-status-bar-breadcrumb.md`](phase-5.3-status-bar-breadcrumb.md) | Permanent breadcrumb on selection + transient action messages | not started |
| 5.4 | [`phase-5.4-persisted-view-state.md`](phase-5.4-persisted-view-state.md) | `QSettings`-backed per-file column widths / expansion / selection / font zoom | not started |
| 5.5 | [`phase-5.5-search-filter.md`](phase-5.5-search-filter.md) | `TreeFilterProxy` + Ctrl+F search bar + delegate/tree-view audit for `mapToSource` | not started |
| 5.6 | [`phase-5.6-misc-polish.md`](phase-5.6-misc-polish.md) | Resize on tab switch / model reset, View menu, Expand/Collapse All, optional icons | not started |
| 6 | [`phase-6-tests.md`](phase-6-tests.md) | Test coverage: model unit tests, round-trip tests, GUI smoke tests | partially done (Phases 0–3 already shipped 343-test baseline) |

## How to use these files

Each phase file follows the same shape:

1. **Goal** — one-paragraph mission statement.
2. **Entry criteria** — what must be true before starting.
3. **Exit criteria** — observable result that proves the phase is done.
4. **Work items** — checklist of TODO/FIXME entries pulled from
   `todo-n-fixme.md`, with file:symbol references.
5. **Risks / notes** — gotchas and design decisions to make.

When closing an item, tick it in the phase file **and** in
`todo-n-fixme.md` so both stay in sync.
