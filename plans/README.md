# Windows UX Fix Plan

This directory contains per-issue plans for Windows-specific UX problems
discovered after the first Windows build. Each issue is tracked in its own
markdown file and is intended to land as a **single, self-contained commit**.

| # | File | Issue | Severity |
|---|------|-------|----------|
| 1 | [`01-editor-opaque-background.md`](01-editor-opaque-background.md) | Semi-transparent inline editors overlap underlying cell value, making text unreadable | High |
| 2 | [`02-windows-app-icon.md`](02-windows-app-icon.md) | Windows executable uses default PyInstaller icon (no app branding) | Medium |
| 3 | [`03-tab-name-basename.md`](03-tab-name-basename.md) | Tab titles on Windows show full path instead of file name only | High |
| 4 | [`04-copy-full-path-action.md`](04-copy-full-path-action.md) | Add "Copy Full File Path" action in File menu | Low |
| 5 | [`05-windows-hover-highlight.md`](05-windows-hover-highlight.md) | Distracting blue hover highlight on Windows native style | Medium |

## Conventions

- One issue → one branch → one PR → one commit (squash on merge if needed).
- Each commit message follows the form:
  `fix(win): <imperative summary>` (or `feat(win):` for issue #4).
- Each plan file lists:
  - **Context** — what the user sees and why it happens
  - **Proposed change** — files to touch and high-level approach
  - **Out of scope** — explicit non-goals to keep the commit focused
  - **Definition of Done (DoD)** — verifiable acceptance criteria

## Suggested merge order

1. `03-tab-name-basename` — trivial bug-fix, unblocks Windows usability immediately.
2. `01-editor-opaque-background` — high-impact correctness fix.
3. `05-windows-hover-highlight` — visual polish, depends on theme stack only.
4. `02-windows-app-icon` — build/packaging change, no runtime risk.
5. `04-copy-full-path-action` — new feature, lowest priority.
