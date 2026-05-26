# Refactoring Plan ── Phase 3: De-monolithing the `MainWindow` Application Shell

## The Problem
`MainWindow` (~1,116 LOC) is the monolithic root shell subclass of the application. It acts as the visual window and direct controller for everything in the application workspace. It contains a lot of boilerplate UI setup alongside heavy non-visual management logic:
* Tab addition, container lists, LIFO caches of closed tabs.
* App-wide preference panels, custom secret name filters, and warning thresholds.
* Connecting validation dock widgets, schema attachments, and event jumps.

These cross-cutting concerns should not occupy space inside the primary `QMainWindow` UI container.

---

## The Solution
Refactor `MainWindow` to act as a visual shell that delegates logical sub-systems to independent controller classes:

1. **`TabLifecycleController`**: Manages tab sets, selected tab tracking, and the closed tabs history stack.
2. **`AppSettingsController`**: Manages warning thresholds and confidential name prefixes.
3. **`DockValidationPresenter`**: Coordinates interaction between the validation panel, schema bindings, schema registry reloads, and navigation rules.

---

## Detailed Step-by-Step Commit Plan

### Commit 3.1: Create `app/tab_lifecycle.py` & Move Tab Stack Caches
* **Change Description**:
  * Define `TabLifecycleController` in `app/tab_lifecycle.py`.
  * Move variables:
    * `self.tabs` (QTabWidget controller), `_closed_tabs_stack` (LIFO stack), and limit thresholds.
  * Move methods:
    * `_add_tab()`, `_on_tab_changed()`, `close_tab()`, `_reopen_tab()`, and tab closure prompts.
* **Affected Files**:
  * Create `app/tab_lifecycle.py`
  * Modify `app/main_window.py` to delegate tab cycles, additions, switches, closures, and recoveries to this controller.
* **Definition of Done (DoD)**:
  * Check that all tab life-cycle, reopen, tooltip, and closure tests stay green:
    ```bash
    pytest tests/ -k "lifecycle or tab"
    ```

### Commit 3.2: Create `app/app_settings.py` & Extract Config Constraints
* **Change Description**:
  * Define `AppSettingsController` in `app/app_settings.py`.
  * Move configuration controls, warning range limits, and secret word prefixes into `AppSettingsController`.
  * Extract methods:
    * Dialog integrations for secret prefix alterations and warning limit configurations.
* **Affected Files**:
  * Create `app/app_settings.py`
  * Modify `app/main_window.py` to leverage `AppSettingsController` rather than hosting dialog logic directly.
* **Definition of Done (DoD)**:
  * Confirm that configurations are loaded/saved correctly (QSettings integration testing).
  * Run the unit tests to verify no regressions in settings or prefix detection:
    ```bash
    pytest tests/
    ```

### Commit 3.3: Create `app/validation_presenter.py` & Decouple Dock Actions
* **Change Description**:
  * Create `DockValidationPresenter` inside `app/validation_presenter.py`.
  * Move the docking layout actions, schema attachment dialog prompts, registry loaders, and issue double-click navigation controllers into the presenter.
  * Connect signals directly between the validation dock widgets and active documents through this presenter.
* **Affected Files**:
  * Create `app/validation_presenter.py`
  * Modify `app/main_window.py` to instantiate and connect this presenter.
* **Definition of Done (DoD)**:
  * Run all tests, verifying schema validation panel attachments and rule navigation tests stay completely green:
    ```bash
    pytest tests/
    ```
  * Verify that `app/main_window.py` code quality metrics have improved and its line count is under 400 LOC.
