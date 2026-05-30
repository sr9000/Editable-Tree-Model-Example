# Plan 22 Phase S5 Audit (JsonTab facade)

Date: 2026-05-30

## Metrics

- `JsonTab` members (`def` + `@property`): **45**
  - Command: `grep -cE "^    def |^    @property" documents/tab.py`
- Retired wrappers from S1-S4: **removed**
  - `_on_type_changed`, `_reopen_value_editor`, `_open_active_type_combo_popup`
  - `_run_tree_action`
  - `_snapshot`, `_set_dirty`, `_on_clean_changed`
  - `_size_hint_for_item`, `_on_current_changed`

## Remaining shape

`documents/tab.py` is now primarily:

- Document protocol/public surface forwarders (`save`, `save_as`, `display_name`,
  `edit_name_or_value_from_enter`, model/view accessors)
- Qt lifecycle/override glue (`eventFilter`, `closeEvent`, `__init__`)
- Controller accessors (`editing`, `io`, `appearance`, `validation`, etc.)

No additional thin private wrappers from the S1-S4 removal list remain.

## S5 outcome

- The count target (`<= 40`) is **not yet reached** (current: `45`).
- This is a 13-member reduction from the Plan 22 baseline (`58 -> 45`) after
  Phases R+S1-S4.
- Residual gap (`5`) is tied to public/documented surface and Qt overrides,
  not the retired private wrapper set.

## Next step

Schedule a follow-up S-step to evaluate whether any remaining public forwarders
can be safely collapsed without changing `documents/document_protocol.py` and
without breaking external callers.
