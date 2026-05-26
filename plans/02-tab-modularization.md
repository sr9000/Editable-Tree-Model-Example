# Refactoring Plan ── Phase 2: Modularizing `JsonTab` into Cohesive Controllers

## The Problem
`JsonTab` is an monolithic class spanning roughly 1,400 LOC. It mixes UI management (layouts, filters, splitters, tree views) with business and data domains such as document schema compilation, validation scanning, I/O monitoring, and history-state tracking. 

This multi-responsibility mix makes code modifications risky and prevents components from being independently tested or mock-verified.

---

## The Solution
Divide and conquer by extracting three specialized, pure-Python controller classes, reducing `JsonTab` to a layout shell that handles and wires up these dependencies:

1. **`TabValidationController`**: Governs schemas, background mutation debouncers, validation loops, and issue navigation.
2. **`TabHistoryController`**: Encapsulates undo-stack signals, state preservation (recapturing expanded nodes during undo/redo transitions), and change merges.
3. **`TabIOController`**: Governs document file names, saved formats, and dirty status.

```
       ┌──────────────────────┐
       │       JsonTab        │ (View Container)
       └────┬──────┬──────┬───┘
            │      │      │
            │      │      └─────────────────┐
            ▼      ▼                        ▼
     ┌───────────┐┌──────────────────┐┌────────────┐
     │ TabFileCtrl││TabValidationCtrl││TabUndoCtrl │ (Pure Logic Controllers)
     └───────────┘└──────────────────┘└────────────┘
```

---

## Detailed Step-by-Step Commit Plan

### Commit 2.1: Create `documents/tab_validation.py` & Extract Validation Logic
* **Change Description**:
  * Define `TabValidationController` inside a new file `documents/tab_validation.py`.
  * Move the following variables from `JsonTab` into the controller:
    * `_schema_ref`, `_schema`, `_issue_index`, `_auto_rescan`, and `_mutation_debounce_timer`.
  * Extract methods:
    * `revalidate()`, `set_schema()`, `clear_schema()`, `_on_registry_schema_reloaded()`, and `_init_validation_state()`.
  * Expose an event/signal channel (e.g., `validationFinished = Signal(object)`) that `JsonTab` can listen to in order to schedule repaints.
* **Affected Files**:
  * Create `documents/tab_validation.py`
  * Modify `documents/tab.py` to instantiate and delegate validation tasks to `TabValidationController`.
* **Definition of Done (DoD)**:
  * Check that validation tests stay green:
    ```bash
    pytest tests/ -k "validation"
    ```

### Commit 2.2: Create `documents/tab_history.py` & Extract Undo/Command Control
* **Change Description**:
  * Define `TabHistoryController` inside a new file `documents/tab_history.py`.
  * Move the `QUndoStack` instance, the `_move_view_state_by_cmd_id` map, and index change monitoring methods (`_on_undo_index_changed`, `_on_clean_changed`) to this controller.
  * Encapsulate view expansion state capture (`apply_expanded_relative_paths` and `iter_expanded_relative_paths`) within the history controller.
  * Expose state transition notification hooks so the view matches history increments.
* **Affected Files**:
  * Create `documents/tab_history.py`
  * Modify `documents/tab.py` to instantiate and delegate history operations to `TabHistoryController`.
* **Definition of Done (DoD)**:
  * Verify that all undo/redo, movement, and collision unit tests pass:
    ```bash
    pytest tests/ -k "undo or move"
    ```

### Commit 2.3: Create `documents/tab_file.py` & Extract Document I/O State
* **Change Description**:
  * Define `TabIOController` in a new file `documents/tab_file.py`.
  * Move variables: `file_path`, `save_format`, `_dirty` and dirty signal transitions from `JsonTab` into `TabIOController`.
  * Bind saving and loading cycles, bridging to `documents/tab_io` functions.
* **Affected Files**:
  * Create `documents/tab_file.py`
  * Modify `documents/tab.py` to utilize `TabIOController` for managing file states, reducing tab-level logic to basic delegation.
* **Definition of Done (DoD)**:
  * Run the complete test suite. Ensure all I/O, reload, and saving tests pass completely:
    ```bash
    pytest tests/
    ```
  * Assert that the line-of-code metrics for `documents/tab.py` have decreased to below 600 LOC.
