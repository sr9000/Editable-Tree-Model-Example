# UX & Behaviour Fix Plan — overview

_Created: 2026-05-06. Tracks the next batch of UX / correctness fixes
on top of the post-Phase-6 tree (theming + package refactor shipped)._

This plan groups 14 user-reported issues into **6 cohesive phases**.
Phases are ordered by **profit / blast-radius**: small independent
polish first to ship visible value, then the foundational coercion
overhaul, then display polish that depends on coercion semantics, and
finally the largest visual change (full-app theming).

| #     | Phase                                                    | Risk    | Issues addressed                                                                                                                                                           |
|-------|----------------------------------------------------------|---------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **1** | [Context-menu column awareness](phase-1-context-menu.md) | low     | disable on kind col; copy *name+value* on name col; copy value-only on value col                                                                                           |
| **2** | [Zoom preserves column sizes](phase-2-zoom-columns.md)   | low     | Ctrl+= / Ctrl+- / Ctrl+0 keep current widths when possible                                                                                                                 |
| **3** | [Type-switch coercion overhaul](phase-3-coercion.md)     | medium  | bytes/zlib/gzip *encode* on switch; bool→str case; date/time/dt placeholder = now; epoch sec/ms → date/time/dt; object↔array preserves children with `item1,item2,…` names |
| **4** | [Display & preview](phase-4-display-preview.md)          | medium  | object/array meta when expanded; partial preview when collapsed; `#i` array indices; percent always shown as percent; theme styling on value cells (not only kind)         |
| **5** | [Full-app theme application](phase-5-app-theme.md)       | low–med | flip Qt's stock light/dark color scheme based on active theme `mode`; no custom palette/stylesheet                                                                         |
| **6** | [Tests & memory refresh](phase-6-tests-memory.md)        | low     | targeted regressions for phases 1–5; refresh `ai-memory/*`                                                                                                                 |

## Re-ordering rationale

- **Phase 1 / 2** are tiny, isolated edits in `tree_actions/` and
  `documents/tab*.py` respectively. They land first to give immediate
  visible improvement and to unblock manual UX QA.
- **Phase 3** rewrites kind-switching coercion (`tree/item_coercion.py`
  + `tree/item.py.set_data` col 1). Several display issues in Phase 4
  (preview text, percent normalization) want post-coercion shapes, so
  this must precede them.
- **Phase 4** updates `tree/model_roles.py`, `delegates/value_formatting.py`
  and the `ValueDelegate` style path. With Phase 3 done, the previewer
  can rely on coerced bool strings, normalized percent values, etc.
- **Phase 5** flips Qt's bundled light/dark color scheme based on the
  active theme's `mode`. It deliberately does **not** ship custom
  palettes or stylesheets — per-type cell colouring stays in the
  delegate, and the rest of the chrome inherits Qt defaults. Moved
  late only because it touches the global `QStyleHints`; the change
  itself is small.
- **Phase 6** is housekeeping: regression tests for each phase plus a
  refresh of `ai-memory/{repo-map,pros-n-cons,todo-n-fixme}.md`.

## Cross-cutting principles

- **No model-role coupling**: theming stays out of `tree/model_roles.py`.
  Phase 4 routes the value-cell color via `ValueDelegate.initStyleOption`
  (already done for type col); we extend it, not replicate it.
- **Coercion is total**: every kind-switch must produce *some* value
  (placeholder where parsing fails) and never raise. Phase 3 keeps
  `coerce_value_for_type` total but adds *encode-on-switch* and
  *now-fallback* branches.
- **Undo-safe**: kind switching already routes through
  `_ChangeTypeCmd`; the new behaviour must not bypass the typed undo
  stack or break `DiffApplier` replay.
- **Tests first where it's cheap**: each phase ships with at least one
  unit test before code lands. The full suite must remain green.

## Status legend (per phase doc)

```
[ ] not started
[~] in progress
[x] done
```

See `ai-memory/todo-n-fixme.md` for the canonical bug-tracking list;
this directory is the shipping plan, not a duplicate of TODO.
