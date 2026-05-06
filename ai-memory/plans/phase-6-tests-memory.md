# Phase 6 — Tests & memory refresh

**Risk:** low · **Files:** `tests/*`, `ai-memory/*` ·

## Goals

- Each preceding phase already adds at least one targeted test;
  Phase 6 is the catch-all for cross-phase regressions plus the
  `ai-memory/` refresh.

## Test additions

- `tests/test_phase_ux_batch.py` — end-to-end smoke that touches
  every phase 1–5 path:
  1. Open `data.yaml`.
  2. Right-click on a name cell, Copy → assert clipboard is
     `name: value`.
  3. Right-click on a value cell, Copy → assert clipboard is value
     only.
  4. Drag col 0 wider, `Ctrl+=`, assert col 0 width unchanged.
  5. Switch a BOOLEAN row to STRING → assert `"true"` / `"false"`.
  6. Switch a primitive row to BYTES → assert it round-trips on
     switch back.
  7. Switch ARRAY → OBJECT → assert children kept with `item1, …`
     names.
  8. Inspect a collapsed OBJECT row → assert preview text contains
     `{N keys}`.
  9. Apply a dark theme → assert `QApplication.palette().window()`
     darkens.

- Re-run the full suite under
  `QT_QPA_PLATFORM=offscreen pytest -q`; record the new pass count
  in `ai-memory/repo-map.md`.

## `ai-memory/` updates

After each phase lands:

- **`repo-map.md`** — bump "Last scanned" date; if any module added,
  list under §2; in particular note:
  - `themes/qt_palette.py`, `themes/qt_stylesheet.py` (Phase 5).
  - new helpers in `tree/item_coercion.py` (`_now_for_type`,
    `_try_parse_temporal`).
  - new clipboard helpers in `tree_actions/clipboard.py`.
  - `_format_array_preview` / `_format_object_preview` in
    `delegates/value_formatting.py`.

- **`pros-n-cons.md`** —
  - move "Theme switching is content-scoped, not full-app chrome
    scoped" out of *Cons* into *Pros* once Phase 5 lands.
  - add a *Pros* bullet for "kind switching is total and lossless
    across BYTES/datetime/object↔array".
  - drop "match-highlight delegate" only when Phase 4 visually solves
    the same UX gap (it does **not** — keep that bullet).

- **`todo-n-fixme.md`** —
  - check off `[ux] Apply the active theme to more of the application
    chrome` after Phase 5.
  - add **resolved** entries for each issue from the user's request,
    cross-linked to the phase doc.
  - if any new follow-up surfaces (e.g. icon-asset hot reload,
    accessibility contrast on the new palette keys), add as new TODO.

## Order of work

1. Land Phase 1 → run targeted tests → update memory note.
2. Repeat for Phase 2 / 3 / 4 / 5.
3. Run Phase 6 cross-phase smoke last.
4. Final memory pass: bump dates, update test counts, mark all
   issues resolved.
