# `getattr` / `hasattr` elimination — overview

## Why

`hasattr` / `getattr` against known internal classes (`JsonTab`, `JsonTreeModel`,
`JsonTypeDelegate`, `ValidationDock`, …) is an OOP rule violation: it replaces
explicit method calls, typed parameters, and protocols with stringly-typed
reflection. Source of truth: `reports/getattr-usage-analysis.md`.

Future enforcement: a pre-commit / CI `grep` hook will reject any new
`getattr(` or `hasattr(` outside a small allowlist (see stage 10).

## Allowed exceptions (after migration)

Reflection is acceptable only where the target is genuinely unknowable at
write time. The allowlist after migration is:

- `jsontream/__init__.py` — generic streaming encoder must probe arbitrary
  user data for `__iter__` / `__len__` / `__next__`.
- A single, central runtime-compat module (introduced in stage 8) that wraps
  PyInstaller / Qt / tzinfo / `Traversable` feature probes. Everything else
  imports the wrapper instead of calling `getattr` / `hasattr` directly.

No other production file may use `getattr` / `hasattr` after stage 10 lands.

## Stage map

| Stage | File                                                 | Scope                                                                  |
|-------|------------------------------------------------------|------------------------------------------------------------------------|
| 01    | `01-jsontab-discovery-tree-actions.md`               | `tree_actions/*` discovering and consuming `JsonTab` (B1, B2, B3)      |
| 02    | `02-jsontab-internal-and-view-state.md`              | `state/view_state.py` + `documents/tab.py` self-probes (B4, B5)        |
| 03    | `03-delegates-and-editor-factory.md`                 | `documents/tab_setup.py`, `delegates/editor_factory.py`, type delegate |
| 04    | `04-font-controller-protocol.md`                     | `app/font_controller.py` subscriber protocol (C4)                      |
| 05    | `05-model-actions-protocol.md`                       | `model_actions.py` model-like protocol (D1)                            |
| 06    | `06-validation-error-adapter.md`                     | `validation/validator.py` error normalization (F1)                     |
| 07    | `07-validation-dock-and-schema-binding.md`           | `app/validation_dock.py`, `documents/tab_validation.py` (F2, F3)       |
| 08    | `08-runtime-qt-pyinstaller-compat.md`                | Qt / PyInstaller / tzinfo / Traversable / QByteArray (A1–A5)           |
| 09    | `09-affix-mru-and-dnd-data.md`                       | `state/affix_mru.py`, `tree_actions/dnd.py` data shapes (E2–E4)        |
| 10    | `10-allowlist-and-precommit-hook.md`                 | Final allowlist, grep hook, CI gate                                    |

## Cross-cutting principles

1. **Internal target → typed dependency.** If the object is `JsonTab`,
   `JsonTreeModel`, `JsonTypeDelegate`, `ValidationDock`, `JsonTreeView`,
   `JsonTreeItem`, `AffixMRU`, `SchemaRef`, … the parameter type must be
   that class (or a `typing.Protocol` declared next to it). No reflection.
2. **Capability discovery → explicit accessor, not `hasattr`.** Replace
   parent-chain hunts (`while ... hasattr(cursor, "parent")`) with a
   typed helper like `find_owning_tab(view: QTreeView) -> JsonTab | None`
   that uses `isinstance` against `JsonTab`.
3. **Optional collaborators → constructor injection or property.** When a
   delegate needs `_status_message_callback`, `_icon_provider`,
   `affix_mru`, inject them in `__init__` (or expose them as typed
   `@property` on `JsonTab`) instead of `getattr(tab, ...)`.
4. **Foreign objects → adapter at the boundary.** Adapt once into a frozen
   `@dataclass` (e.g. `NormalizedValidationError`). Inside the app, the
   normalized type is consumed by attribute access, not `getattr`.
5. **Runtime probes → centralized in one module.** Stage 8 introduces
   `app/runtime_compat.py` (name TBD) that owns every Qt / PyInstaller /
   tzinfo / `Traversable` / `QByteArray` capability check. Callers import
   booleans / functions, not `getattr`.
6. **Data protocol probing stays in `jsontream`.** Everything else that
   currently shapes-checks dict/list/JsonTreeItem must use `isinstance`.

## Ordering rationale

- Stages 01–02 first: they remove the largest number of probes and unblock
  typing in the most-touched call sites.
- Stages 03–05 next: they introduce the small `Protocol`s and typed
  constructors that later stages reuse.
- Stages 06–07 isolate validation/schema adapter work, which is mostly
  local to `validation/` and `app/validation_dock.py`.
- Stage 08 is intentionally late: until app-internal probes are gone, it
  is hard to see which runtime probes are truly external.
- Stage 09 mops up the small data-shape cluster.
- Stage 10 turns the rule on permanently with a pre-commit grep hook.

## Definition of done (per stage)

Each stage MD lists its own acceptance criteria, but every stage must:

- leave the repo importable and the test suite green,
- introduce no new `getattr` / `hasattr` outside the allowlist,
- shrink the count in `reports/getattr-usage-analysis.md` by the
  expressions claimed in that stage,
- update `ai-memory/repo-map.md` if a public type/protocol is added.
