# Phase 5.1 — Carry-over & Foundations

## Goal

Close the four Phase-3 carry-over items so the editor pipeline is
stable enough for the rest of Phase 5 (display formatting, search,
persisted state) to layer cleanly on top.

## Entry criteria

- Phase 4 complete.
- All Phase 3 typed-undo commands present and green
  (`tests/test_typed_undo_commands.py`,
  `tests/test_undo_redo_scenario.py`).

## Exit criteria

- Changing a row's `JsonType` interactively reopens the value editor on
  the same row; programmatic `model.setData` does **not** trigger
  `view.edit(...)` (smoke test stays green).
- Multiline / hex dialogs commit through `JsonTab.commit_set_data`, not
  `model.setData`. Their edits land on the typed undo stack and survive
  unrelated row mutations during the modal session.
- Malformed `BYTES` / `ZLIB` / `GZIP` payloads no longer raise out of
  `ValueDelegate.createEditor`; the failure is reported via the status
  bar.
- Consecutive value or name edits to the **same path** within ~500 ms
  collapse into a single `QUndoCommand` entry.

## Work items

### Auto-reopen value editor on interactive type change
- [x] [delegate] Add an `_interactive` instance flag on
      `JsonTypeDelegate`; set `True` in `setModelData` for the duration
      of the commit, then reset.
      — `delegate.py:JsonTypeDelegate`
- [x] [tab] In `JsonTab._on_type_changed`, after closing the persistent
      editor, check `self.type_delegate._interactive`; if `True`, queue
      `self.view.edit(value_index)` via `QTimer.singleShot(0, ...)` so
      Qt finishes its commit cycle before the new editor opens.
      — `json_tab.py:JsonTab._on_type_changed`
- [x] [tests] Existing
      `tests/test_smoke_mainwindow.py::test_cycling_inline_types_does_not_log_edit_failed`
      stays green: programmatic `model.setData` keeps `_interactive`
      `False`, so no extra `view.edit` is queued.
- [x] [tests] `test_phase_5_1_carryover.py::test_programmatic_type_change_does_not_set_interactive_flag`
      asserts the flag stays `False` for programmatic paths.

### Dialog edits routed through `commit_set_data`
- [x] [delegate] `_save_multiline` / `_save_binary` use
      `QPersistentModelIndex` and `ValueDelegate._commit(...)`, which
      routes through `JsonTab.commit_set_data` when a tab ancestor
      exists.
      — `delegate.py:ValueDelegate.createEditor`

### Decode failures surfaced via status bar
- [x] [delegate] Wrapped `decode_bytes(item.value, item.json_type)` for
      `BYTES` / `ZLIB` / `GZIP` in
      `try / except (ValueError, OSError, zlib.error, binascii.Error)`;
      failures are reported via `ValueDelegate._notify_status` and
      `createEditor` returns `None` cleanly.
- [x] [tests] `test_phase_5_1_carryover.py::test_malformed_bytes_payload_does_not_raise_in_create_editor`.

### `mergeWith` for value/name edits
- [x] [undo] `_EditValueCmd` and `_RenameCmd` now have stable `id()`
      values (`_CMD_ID_EDIT_VALUE`, `_CMD_ID_RENAME` — fit signed int32
      so PySide doesn't overflow), and capture `_timestamp =
      time.monotonic()` at construction.
- [x] [undo] `mergeWith(other)` collapses same-`id()` + same-`_path` +
      `_timestamp` delta ≤ `_MERGE_WINDOW_SECONDS` (0.5 s); returns
      `True` and updates the new-value/name + timestamp.
- [x] [tests] `test_consecutive_edits_to_same_path_merge`,
      `test_edits_outside_merge_window_do_not_merge`,
      `test_rename_commands_merge`.

## Risks / notes

- `view.edit(value_index)` on a model index whose row was just rebuilt
  can still log "edit: editing failed" if the editor host has no focus.
  The `QTimer.singleShot(0, ...)` deferral is critical — call directly
  from `_on_type_changed` and you'll re-introduce the warning the
  smoke test guards against.
- `mergeWith` only fires while the undo command is still on top of the
  stack and not yet acted on (Qt invariant). That's fine for
  keystroke-level merging but means an `undo()` between two edits
  correctly resets the merge window.
- The "interactive" flag must be reset in a `try/finally` around the
  underlying `commit_set_data` call so an exception still clears it.
