# MASTER PLAN: Decoupling and Refactoring of God Objects

This plan details a multi-phase, commit-by-commit roadmap to unpack the responsibilities of the three god classes:
1. **`ValueDelegate`** (`delegates/value.py`)
2. **`JsonTab`** (`documents/tab.py`)
3. **`MainWindow`** (`app/main_window.py`)

By breaking these monoliths into cohesive controllers, service classes, and event-driven bridges, we aim to untighten their relations, reduce cognitive load, and make each component independently testable.

---

## Refactoring Philosophy & Goals

1. **Unidirectional Control Flow**: Remove recursive sibling/parent widget traversal (such as `_find_tab()` in `ValueDelegate`). All child-to-ancestor communications must utilize **Qt signals** or **abstract interfaces**.
2. **Separation of Concerns (SoC)**: View classes (widgets) should only govern layout, drawing, event propagation, and visual state. Business logic (validation loops, I/O conversions, configuration persistence, history state limits) must be housed in lightweight, pure-Python controller classes.
3. **Commit-by-Commit Verifiability**: Each phase is broken down into precise, atomic commits. Every commit provides a clear, automated "Definition of Done" (DoD) via pytest commands or static verification rules (greps, interface audits) to ensure no regressions are introduced and that the test suite remains fully green.

---

## Roadmap Index

The refactoring plan is structured into the following sequence of independent, sequential phases, each documented in its own detailed sub-plan:

### [Phase 1: Decoupling `ValueDelegate` from `JsonTab`](01-valuedelegate-decoupling.md)
* **Objective**: Remove the anti-pattern where the delegate walks up the widget tree to find and mutate `JsonTab`.
* **Strategy**: Introduce a formal, signal-based bridge on `ValueDelegate`. Have the tab's initialization plumbing bind these signals to the transaction router.
* **Benefits**: Enables testing `ValueDelegate` in isolation without requiring parent tab widgets; enforces unidirectional data flows.

### [Phase 2: Modularizing `JsonTab` into Cohesive Controllers](02-tab-modularization.md)
* **Objective**: Carve out non-UI responsibilities from the ~1,400 LOC `JsonTab` class.
* **Strategy**: Extract three specialized helper controllers:
  1. `TabIOController`: Manages paths, saving formats, dirty states, and disk/memory checks.
  2. `TabValidationController`: Runs background validation, debouncing timers, schema resolution, and maps issue indices.
  3. `TabHistoryController`: Handles `QUndoStack` state, command routing, and restores view-expansion state profiles around actions.
* **Benefits**: Reduces `JsonTab` lines of code drastically (estimating down to < 500 LOC); isolates validator loop testing from heavy visual widget cycles.

### [Phase 3: De-monolithing the `MainWindow` Application Shell](03-mainwindow-refactoring.md)
* **Objective**: Slim down the master workspace shell (~1,116 LOC) into visual coordinates only.
* **Strategy**: Relocate complex sub-systems into dedicated managers:
  1. `ClosedTabsController` / `TabLifecycleManager`: Coordinates the LIFO history stack, tab addition details, and dirty tab prompts.
  2. `AppConfigController`: Centralizes system capabilities (sizes, word search triggers, confidential prefix lists).
  3. `MainActionStateController`: Manages menu integration and dynamically updates permission locks.
* **Benefits**: Isolates window geometry, makes session tracking/restoring cleanly unit-testable, and divides action enablement from central QT widgets.

---

## Verification Rules (General Instructions)
* Execute `pytest` after every single commit to guarantee zero functional regressions.
* Use static analysis checks (e.g., searching for forbidden patterns such as `_find_tab` in `ValueDelegate` after completion) to ensure complete separation has been maintained.
