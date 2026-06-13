# Loading post-build freeze timing report — 2026-06-13

## Scope

Measured post-build phases between model-finished and load-complete for open/reload flows.

## Dominant phases observed

1. **Validation initialization + first validation pass**
   - `LoadCoordinator.run_schema_discovery_and_validation()`
   - `TabValidationController.revalidate_loading_data()`
   - `TabValidationController.on_validation_changed()` repaint batches
2. **First-presentation selection/proxy interaction (small trees only)**
   - `TabLifecyclePresenter._run_initial_presentation()`
   - `ViewController._apply_select()`
3. **Reload apply/finalization path**
   - `LoadCoordinator._apply_reload()`
   - `state.view_state.restore_runtime_state()` (bounded/chunked for large trees)

## Result summary

- Loading-owned tab creation now defers bootstrap validation.
- No-schema loading fast path avoids full tree snapshots.
- Loading validation consumes parsed data (`_LoadTask.data`) instead of `JsonTreeItem.to_json()`.
- Validation repaint changed from recursive full-tree updates to bounded affected-path batches.
- Large-load first presentation no longer forces root selection in the initial call.
- Reload no longer uses `JsonTab.root_data()` for pre-apply change detection.

## Follow-up guardrails

- Default regression gate: `tests/test_loading_post_build_responsiveness.py`
- Reload responsiveness guard: `tests/test_loading_reload_post_build_responsive.py`
- Validation repaint bounds guard: `tests/test_validation_repaint_bounds.py`
- Perf smoke timing: `tests/perf/test_loading_post_build_phase_timing.py`
