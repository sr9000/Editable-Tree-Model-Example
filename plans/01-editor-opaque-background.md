# ~~Issue 01 — Inline editor overlaps underlying cell text on Windows~~

> ALREADY DONE VIA DISABLING PAINTING OF VALUE TEXT IN EDIT MODE

**Status:** open
**Severity:** High (data-entry blocker)
**Target commit:** `fix(win): paint opaque background for inline cell editors`

## Context

When the user starts editing a cell in the tree view on Windows, the editor
widget (e.g. `QLineEdit`, type-combo, datetime editor, multiline editor) is
drawn with a *transparent* background. The cell's painted value (drawn by the
delegate's `paint()` method) shows through the editor's text, producing a
visually overlapped, unreadable composite of "old text" and "edit buffer".

On Linux/Fusion the default platform style fills the editor's background
opaquely, hiding this defect. The native Windows Vista style does not,
exposing the bug.

### Affected widgets (to verify)

- `delegates/value.py` → `createEditor()` for the value column
- `delegates/name_delegate.py` → name editor
- `delegates/type_delegate.py` → type combo
- `qmultiline_editor.py` → multiline value editor
- `datetime_editor/better_dt_editor.py` → datetime editor
- `qhexedit/`, `qbigint_spinbox/`, `qmpq_spinbox/` editor entry points

## Proposed change

1. Centralize the fix: in each `createEditor()` (or in a shared helper in
   `delegates/base.py`), set:
   - `editor.setAutoFillBackground(True)`
   - `editor.setAttribute(Qt.WA_OpaquePaintEvent, True)` where appropriate
   - For composite/container editors, ensure the **root** widget has an opaque
     palette `Base` color from the active theme (`QPalette.Base`).
2. For the delegate's `paint()` path, when `option.state & QStyle.State_Editing`
   is set OR when the index is the current editor index, **skip painting the
   value text/icon** so even a partially transparent editor cannot overlap.
   (Belt-and-suspenders; the autofill alone should suffice.)
3. Verify the multiline popup editor (`qmultiline_editor.py`) paints a solid
   `QPalette.Base` background — it currently relies on stylesheet inheritance.

## Out of scope

- Restyling the editors themselves (fonts, borders, focus rings).
- Changing the delegates' read-only painting.
- Theme palette tweaks (handled in issue #05).

## Definition of Done

- [ ] On Windows 10/11 with native style, opening any inline editor over a
      non-empty cell shows **only** the editor's text — no underlying value
      bleeds through.
- [ ] Verified for: name column, type combo, value (string/number/bool/null),
      datetime, bytes (hex), bigint, multiline popup.
- [ ] No visual regression on Linux (Fusion + KDE Breeze) and macOS.
- [ ] No new Qt warnings in `stderr` when entering/leaving edit mode.
- [ ] Existing delegate unit tests pass; a new smoke test asserts that the
      created editor has `autoFillBackground == True` (or an opaque palette
      `Base` role) for each delegate type.
- [ ] One commit, ≤ ~80 LOC of production change + helper.
