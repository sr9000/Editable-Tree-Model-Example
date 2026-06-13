# Close Phase Timing Report — 2026-06-13

## Phase timings

| Phase | Elapsed (ms) |
|---|---:|
| snapshot_root_data | 3.026 |
| schema_unregister | 0.002 |
| view_state_save | 728.461 |
| remove_tab | 0.425 |
| delete_later | 0.003 |
| forced_deferred_delete | 4.894 |

## Summary

- Dominant phase: **view_state_save**
- Chosen implementation path: **chunk/yield**

## Notes

- Measurement run executed in `QT_QPA_PLATFORM=offscreen` mode.
- `forced_deferred_delete` measures one explicit flush of deferred-delete events after `deleteLater`.