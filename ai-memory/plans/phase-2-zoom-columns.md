# Phase 2 — Zoom preserves column sizes

**Risk:** low · **Files:** `documents/tab.py`, `documents/tab_setup.py` ·
**Tests:** `tests/test_phase_5_6_misc_polish.py` (extend)

## Issue addressed

- [ ] `Ctrl+= / Ctrl+- / Ctrl+0` currently call `resize_key_columns()`
      which forcibly does `resizeColumnToContents(0/1)`. This wipes any
      manual width the user set on the name/type columns.

## Current behaviour

`documents/tab.py:198-208`:

```python
def zoom_in(self):
    self._set_font_pt(self._font_pt + 1)
    self.resize_key_columns()
```

`resize_key_columns()` always re-snaps columns 0/1 to content width.

## Plan

1. **Detect "user has resized" once at startup.** In `tab_setup`, after
   the initial `resize_key_columns()` call, hook
   `view.header().sectionResized` and set
   `tab._user_sized_columns: set[int]` for sections whose final width
   differs from the auto-fit result.
   - If `state.view_state.restore` provided column widths, mark cols 0
     and 1 as user-sized immediately (the persisted width is the user's
     last preference).

2. **`resize_key_columns()` becomes opt-in:**
   - new flag `force: bool = False`,
   - skips columns present in `tab._user_sized_columns` unless `force`,
   - existing `_on_model_reset` path keeps `force=True` so a brand-new
     model still gets snug initial widths.

3. **Zoom helpers preserve widths:**
   - `zoom_in / zoom_out / zoom_reset` no longer call
     `resize_key_columns()`. Instead they call a new
     `_scale_columns_for_font(old_pt, new_pt)` helper that, for each
     column the user has *not* hand-resized, multiplies its current
     width by `new_pt / old_pt` (clamped to a sensible min/max). For
     hand-resized columns: leave alone.
   - Value column (col 2) is never auto-resized; it stretches.

4. **Persistence:** `state/view_state.py:save` already records
   per-column widths; nothing to do.

5. **Tests:**
   - existing `test_phase_5_6_misc_polish.py::test_zoom_reset_restores_default_font`
     stays green,
   - new `test_zoom_preserves_user_column_widths`:
     1. open a tab,
     2. set col 0 width to 200,
     3. `zoom_in()` × 3,
     4. assert col 0 is **not** snapped back to content,
     5. assert col 0 has scaled (or unchanged within tolerance — pick
        one and document).

## Out of scope

- Saving font_pt to QSettings (already done).
- Column-resize undo.

## Acceptance

- Suite green.
- Manual: drag col 0 wider, hit `Ctrl+=` repeatedly; col 0 keeps the
  user's drag, only the font grows.
