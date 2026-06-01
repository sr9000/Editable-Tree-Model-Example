# Application Architecture Review

**Project:** Editable-Tree-Model-Example (PySide6 structured-data editor)
**Date:** 2026-06-01
**Scope:** Application architecture (layering, boundaries, data/control flow, extensibility).
**Method:** Static reading of source plus the repo's own gates
(`check-no-reflection`, `check-editors-isolation`), formatter checks, and test
collection (1124 tests collected).

---

## 1. Executive summary

The application is a **cleanly layered PySide6 desktop editor** built around a
single strong idea: *every document is a tab, and every mutation flows through a
narrow, undoable seam*. The codebase is unusually disciplined for a desktop Qt
app — boundaries are not merely conventional, they are **machine-enforced** by
custom pre-commit gates.

- **Architecture grade: A‑.** Layering is coherent, the dependency direction is
  consistent (UI → orchestration → data), and the most dangerous areas (undo,
  type coercion, structural moves) are funneled through single choke points.
- **Primary strength:** enforced isolation seams (editors can't import the app;
  mutations can't bypass undo; no reflection).
- **Primary risks:** (1) the `JsonTab` facade + `Document` protocol surface is
  large and must be kept in sync by hand; (2) `app/main_window.py` retains many
  thin forwarding shims; (3) tooling configuration is decentralized (see the
  companion `reports/` code-quality notes / Makefile).

---

## 2. Layered model

```
                         main.py  (entry point: QApplication + icon + MainWindow)
                            │
  ┌─────────────────────────┴───────────────────────────────────────────┐
  │ app/        Global shell: window, menus, tabs, themes, fonts,       │
  │             validation dock, recent files, settings presenters.     │
  │             Talks to tabs ONLY through the `Document` protocol.     │
  └─────────────────────────┬───────────────────────────────────────────┘
                            │  documents.seams.document_protocol.Document
  ┌─────────────────────────┴───────────────────────────────────────────┐
  │ documents/  Per-tab orchestration (JsonTab facade):                 │
  │   composition/  wiring & construction (bootstrap, DI bundles)       │
  │   controllers/  appearance, navigation, editability, validation,    │
  │                 history, view, status, number_types                 │
  │   states/       io, view_state, editing (+ command dispatch)        │
  │   seams/        mutation_gateway (the ONLY edit entry), protocol    │
  └───────┬─────────────────────┬──────────────────────┬────────────────┘
          │                     │                      │
  ┌───────┴──────┐     ┌────────┴────────┐    ┌────────┴─────────┐
  │ tree/        │     │ undo/           │    │ tree_actions/    │
  │ model, item, │     │ commands, diff  │    │ clipboard, dnd,  │
  │ types,       │     │ (surgical       │    │ move, sort,      │
  │ coercion     │     │  replay)        │    │ anchors, paste   │
  └───────┬──────┘     └─────────────────┘    └──────────────────┘
          │
  ┌───────┴───────────────────────────────────────────────────────────────┐
  │ editors/ (value widgets, app-agnostic)   delegates/ (paint + dispatch)│
  │ io_formats/ (load/dump/atomic)  validation/ (jsonschema)  themes/     │
  │ state/ (QSettings persistence)  ui/ (generated)                       │
  └───────────────────────────────────────────────────────────────────────┘
```

The dependency arrows point **downward and inward** only. The two enforced seams
(`Document` protocol at the app boundary, `DocumentMutationGateway` at the data
boundary) keep the upper layers from reaching into implementation detail.

---

## 3. Control & data flow

### 3.1 Construction (a tab is born)

`MainWindow._add_tab` → `TabLifecyclePresenter` → `JsonTab.__init__` →
`documents.composition.init.bootstrap()`. The `__init__` body is intentionally
*empty of logic*: it just forwards to `bootstrap()`, which assembles the tab in a
deliberate order — view state → editing controller → appearance/navigation →
services (DI) → layout → model → history → mutation gateway → validation →
delegates → shortcuts → view controller. This is a clean **composition root**.

Dependency injection is real but lightweight: `JsonTabServices`
(`host`, `theme`, `icon_provider`) is a frozen dataclass with null-object
defaults (`NullJsonTabHost`, `StubIconProvider`). This is why tabs can be
instantiated headlessly in tests with `JsonTab(lambda *_: None)`.

### 3.2 The edit flow (the spine of the app)

```
ValueDelegate (UI)
  → editors.factory.create_value_editor        # type-dispatched widget
  → JsonTab.commit_set_data / mutations.*       # the SINGLE seam
  → DocumentMutationGateway                      # routes by column 0/1/2
  → CommandDispatcher.push_rename/change_type/edit_value
  → QUndoCommand (undo/commands.py)
  → JsonTreeModel.setData → JsonTreeItem.set_data
```

**Invariant:** nothing mutates the tree except through the gateway. The gateway
also enforces read-only mode and proxy→source index translation in one place.
This is the single best architectural decision in the repo — it makes undo/redo
correctness a *structural* property rather than a discipline that each call site
must remember.

### 3.3 Undo / redo replay

Undo/redo does **not** reset the model. `undo/diff.py::DiffApplier` performs a
surgical diff between the live tree and the target snapshot and emits minimal
`dataChanged` / row insert/remove signals. This preserves selection, expansion,
and scroll — UI state that a full `beginResetModel` would destroy. Reload-from-
disk reuses the very same `DiffApplier`, so external file changes animate into
the existing tree instead of rebuilding it. Excellent reuse.

### 3.4 Structural moves

All structural moves (drag-drop, Alt+↑/↓, cut/paste) are expressed via the
`MoveAnchor` primitive in `tree_actions/anchors.py` and `push_move_rows_anchor`.
One representation, many gestures — this avoids the classic bug class where
keyboard-move and drag-move diverge.

### 3.5 Viewport via signal

The `ViewController` exposes `request_*` methods that emit `viewportRequested`;
undo commands never call `setCurrentIndex` directly. This decouples "what
changed" from "where the cursor should go," which is what lets surgical replay
stay UI-agnostic.

---

## 4. Boundary enforcement (the standout quality)

| Seam                      | Mechanism                                                                    | Gate                             |
|---------------------------|------------------------------------------------------------------------------|----------------------------------|
| Editors stay app-agnostic | `editors/inline/*`, `editors/windowed/*` may not import `app/documents/tree` | `make check-editors-isolation` ✅ |
| No mutation bypasses undo | All edits route through `DocumentMutationGateway`                            | convention + protocol            |
| No reflection             | `getattr`/`hasattr`/`TYPE_CHECKING` banned outside a 3-file allowlist        | `make check-no-reflection` ✅     |
| App ↔ tab decoupling      | `app/` sees tabs only as `Document` (a `runtime_checkable` Protocol)         | typed protocol                   |
| No external state reads   | callers reach state via typed `JsonTab.*` properties only                    | pre-commit hook                  |

Both gates pass on the current tree. The "no reflection" rule is notable: by
banning `getattr`/`hasattr`, the team forces explicit typed accessors, which is
why the `Document` protocol and `JsonTab` properties exist at all. The cost is a
**large hand-maintained surface** (see §6).

---

## 5. Strengths

1. **Single mutation seam.** Undo correctness is structural, not a per-call-site
   discipline. This is the highest-leverage design choice in the project.
2. **Surgical model updates** reused across undo/redo *and* reload — preserves UI
   state and avoids a whole category of "selection jumped" bugs.
3. **Enforced isolation** of editor widgets and the no-reflection rule give the
   codebase real, checkable modularity instead of aspirational layering.
4. **Composition root** (`bootstrap()`) cleanly separates *wiring* from *behavior*;
   the `JsonTab.__init__` is a one-liner forwarder.
5. **Lightweight DI with null objects** makes the GUI testable headlessly — the
   1124-test suite runs under offscreen Qt without a display.
6. **Type system as source of truth** (`tree/types.py`, `tree/item_coercion.py`)
   keeps type logic out of the UI layer.
7. **Small-module culture.** Most files are well under 300 lines; the `documents/`
   split into composition/controllers/states/seams reads like a textbook.

---

## 6. Risks & weaknesses

1. **Facade surface is large and hand-synced.** `JsonTab` (documents/tab.py) +
   `Document` (seams/document_protocol.py) + `DocumentMutationGateway` together
   form a wide, manually-mirrored API. Because reflection is banned, every new
   capability must be added to the facade, the protocol, and often the gateway.
   This is a deliberate trade (explicitness over magic) but it is the main place
   the architecture will rot if discipline slips. *Mitigation:* a small test that
   asserts `JsonTab` satisfies `Document` and that gateway/dispatcher method sets
   line up.

2. **`app/main_window.py` (~638 lines) still carries legacy shims.** Many methods
   are one-line forwarders to presenters (`_limits_menu`, `_setup_validation_dock`
   marked `# pragma: no cover - retained for back-compat`, deprecated
   `_closed_tabs_stack`/`_MAX_CLOSED_TABS`). These are harmless but obscure the
   true responsibilities. A forwarder-pruning pass (with a deprecation sweep of
   tests) would shrink this to a thin window shell.

3. **`bootstrap()` ordering is implicit and fragile.** The 20-step init sequence
   has real ordering constraints (e.g. view controller must be created after view
   and proxy; severity provider before first revalidation). These are encoded only
   as comments and call order. A regression here fails at runtime, not at the
   boundary. *Mitigation:* split into named phases with asserts, or document the
   dependency graph next to the function.

4. **Broad exception handling in defensive paths.** Parse/format/coercion paths use
   `except Exception` (and a few bare `except:` in the datetime editor). Acceptable
   as defensive boundaries, but they can mask real bugs; narrowing the
   non-defensive ones (IO, theme apply) is worthwhile. (Detailed in the code-quality
   review.)

5. **Local imports inside methods.** `main_window.py` imports
   `state.clipboard_settings` / `state.validation_settings` inside methods. Usually
   done to avoid cycles or startup cost, but it hides real dependencies from the
   module header and from import-graph tooling.

6. **Theming/font fan-out is push-based.** `_on_theme_applied` iterates all tabs and
   calls `tab.appearance.set_theme`. Works, but it's an O(tabs) manual broadcast; a
   subscription/signal model (as already used for validation and dirty state) would
   be more consistent with the rest of the app.

---

## 7. Targeted recommendations

| Priority | Recommendation                                                                                                                                          | Effort |
|---------:|---------------------------------------------------------------------------------------------------------------------------------------------------------|:------:|
|     High | Add a conformance test: `isinstance(JsonTab(...), Document)` + assert gateway/dispatcher method parity, so the hand-synced facade can't drift silently. |   S    |
|     High | Prune the back-compat shims in `app/main_window.py` (and the deprecated `_closed_tabs_stack` / `_MAX_CLOSED_TABS`) once tests are migrated.             |   M    |
|   Medium | Break `bootstrap()` into named phases (`_wire_state`, `_wire_model`, `_wire_validation`, `_wire_view`) with ordering asserts.                           |   M    |
|   Medium | Convert theme/font fan-out to the same signal-subscription pattern used for validation/dirty.                                                           |   M    |
|   Medium | Narrow non-defensive `except Exception` (IO open/reload, theme apply) to specific error types.                                                          |   S    |
|      Low | Hoist method-local imports in `app/` to module scope where no cycle exists; document the ones that must stay.                                           |   S    |
|      Low | Add an architecture import-direction test (e.g. assert `editors/` never imports `documents/`) to complement the shell gates with a Python-level check.  |   S    |

---

## 8. Verdict

This is a **well-architected application** whose defining feature is that its most
important boundaries are *enforced, not just documented*. The single-seam mutation
model plus surgical undo replay is the kind of design that prevents whole bug
classes rather than patching them. The main maintenance tax is the breadth of the
hand-synced facade/protocol/gateway trio and the residual forwarding shims in the
window shell — both manageable with small, targeted hardening (a conformance test
and a shim-pruning pass). No structural redesign is warranted.
