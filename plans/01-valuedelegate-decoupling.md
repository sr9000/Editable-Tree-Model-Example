# Refactoring Plan ── Phase 1: Decoupling `ValueDelegate` from `JsonTab`

## The Problem
Inside `delegates/value.py`, `ValueDelegate` is heavily coupled to `JsonTab` via a "dynamic parent crawler" anti-pattern. 
Specifically, the static methods:
* `_find_tab(host)` recursively crawls the widget hierarchy checking for the existence of the `commit_set_data` method.
* `_commit(...)` calls `tab.commit_set_data(...)`.
* `_notify_status(...)` crawls the parent tree to extract and invoke `_status_message_callback(...)`.

This makes `ValueDelegate` completely coupled to the visual widget hierarchy, preventing:
1. Reusing `ValueDelegate` in other trees or simplified views where a full `JsonTab` isn't present in the widget ancestry.
2. Headless/out-of-window testing of cell delegation logic without instantiating complex `JsonTab` configurations.

---

## The Solution
Convert this hard reference tree-crawling mechanism into a modern **Event-Driven Signal Bridge**. 

Instead of searching for parent tabs, `ValueDelegate` will emit Qt Signals during edit and notification actions. The class that sets up the delegates (`JsonTab` and its companion modules) will be responsible for binding these signals directly back to the tab's internal business routes.

---

## Detailed Step-by-Step Commit Plan

### Commit 1.1: Introduce Custom Signals on `ValueDelegate`
* **Change Description**:
  * Add the following `Signal` definitions to `ValueDelegate` in `delegates/value.py`:
    ```python
    commitRequested = Signal(QModelIndex, object, int)  # Emits (source_index, raw_value, role)
    statusMessageRequested = Signal(str, int)          # Emits (message, timeout_ms)
    ```
  * Refactor `ValueDelegate._commit` and `ValueDelegate._notify_status` to emit these signals instead of looking up `_find_tab` or invoking callbacks directly on parent tree widgets.
  * *Backward compatibility route (transitional support)*: If no slots are connected to `commitRequested`, fall back gracefully to calling standard `model.setData()`.
* **Affected Files**:
  * `delegates/value.py`
* **Definition of Done (DoD)**:
  * Running `grep -r "_find_tab" delegates/` shows that `_find_tab` is no longer invoked inside any standard edit pathway.
  * Verify that `ValueDelegate` compiles correctly using `python -m py_compile delegates/value.py`.

### Commit 1.2: Connect Delegate Signals in Tab Setup
* **Change Description**:
  * Modify `documents/tab_setup.py::init_delegates_and_connections` to catch the new signals.
  * Connect the active `ValueDelegate` instances' signals to the tab's actions:
    ```python
    delegate.commitRequested.connect(tab.commit_set_data)
    delegate.statusMessageRequested.connect(
        lambda msg, t: tab._status_message_callback(msg, t) if tab._status_message_callback else None
    )
    ```
* **Affected Files**:
  * `documents/tab_setup.py`
* **Definition of Done (DoD)**:
  * Complete full testing suite via:
    ```bash
    pytest tests/
    ```
  * Assert that all standard unit tests and manual inline field edits function identically.

### Commit 1.3: Clean Up Leftovers and Remove Dead Code
* **Change Description**:
  * Remove `_find_tab` completely from `ValueDelegate`.
  * Simplify warning/confirmation prompts (`_confirm_large_text_edit`, `_confirm_large_binary_edit`) to accept a generic `QWidget` window handle for QMessageBox parenting, ensuring they don't assume a `JsonTab` instance.
* **Affected Files**:
  * `delegates/value.py`
* **Definition of Done (DoD)**:
  * Search the codebase for `_find_tab` using grep and confirm it returns exactly zero findings:
    ```bash
    grep -rn "_find_tab" .
    ```
  * Run the test suite:
    ```bash
    pytest tests/
    ```
