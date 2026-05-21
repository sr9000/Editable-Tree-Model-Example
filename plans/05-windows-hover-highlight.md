# Issue 05 — Distracting blue hover highlight on Windows

**Status:** open
**Severity:** Medium (visual noise)
**Target commit:** `fix(win): tame native hover highlight on tree views and tabs`

## Context

On Windows, the native Vista style paints an aggressive blue
`State_MouseOver` background over tree-view rows, tab labels and toolbar
buttons. Combined with the app's own selection / validation badge colors,
this produces a flashing blue rectangle that follows the cursor and
distracts from editing.

On Linux/Fusion the hover highlight is a subtle gray, so the issue is
Windows-specific, but the fix should be applied through the existing theme
layer so it is platform-uniform and theme-aware.

## Proposed change

1. **Force Fusion style on Windows** (cheapest, widest fix):
   - In the application bootstrap (likely `main.py`), call
     `QApplication.setStyle("Fusion")` *before* the main window is built.
   - Verify the existing theme/palette pipeline (`themes/auto.py`,
     `app/theme_controller.py`) still produces expected colors under Fusion
     on all three platforms.
2. **OR** if keeping the native Windows style is desired, override the hover
   palette role for the affected views via stylesheet/QPalette:
   - `QTreeView::item:hover { background: <theme.hover>; color: <theme.fg>; }`
   - `QTabBar::tab:hover { background: <theme.hover>; }`
   - Pull the `hover` color from the active theme spec
     (`themes/spec.py`); add the role if not present.
3. Audit `themes/builtin/*` to ensure each theme defines a `hover` color
   consistent with its `selection` and `base` roles (low contrast against
   `base`, ~6–10% lightness delta).
4. Document the chosen approach in `themes/README` (if exists) or inline
   docstring of the theme spec.

**Recommended:** ship option (1) in this commit (low risk, one line change
in `main.py`), and track option (2) as a follow-up if user feedback still
flags hover noise.

## Out of scope

- Restyling selection colors, focus rectangles, or row striping.
- Animations / fade transitions on hover.
- A user-facing toggle to switch styles.

## Definition of Done

- [ ] On Windows, hovering tree rows, tab labels and toolbar buttons no
      longer produces the bright-blue native highlight.
- [ ] Hover feedback is still present but matches the active theme (subtle
      tint over `base`).
- [ ] No regression on Linux or macOS (styling visually unchanged or
      improved).
- [ ] All built-in themes verified: light, dark, high-contrast.
- [ ] Existing UI screenshot tests (if any) updated; otherwise manual
      verification notes added to the PR.
- [ ] One commit; either a one-line `setStyle("Fusion")` change *or* a
      contained stylesheet/palette patch — not both in the same commit.
