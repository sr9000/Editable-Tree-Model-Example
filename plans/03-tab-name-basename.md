# Issue 03 — Tab titles show full path on Windows

**Status:** open
**Severity:** High (usability — tabs become unusable)
**Target commit:** `fix(win): use os.path.basename for tab display name`

## Context

`documents/tab.py::Tab.display_name()` computes the tab title with:

```python
name = self.file_path.rsplit("/", 1)[-1] if self.file_path else "Untitled"
```

On Windows, `QFileDialog` returns paths with backslash separators
(e.g. `C:\Users\me\Documents\data.json`). `rsplit("/", 1)` does not split,
so `name` becomes the entire path string. The tab bar then shows
`C:\Users\me\Documents\data.json *` instead of `data.json *`, truncating
visually and making tab navigation unusable.

The same value is also fed into the close-confirm dialog
(`app/close_confirm.py`), which suffers the same issue.

## Proposed change

1. Replace the `rsplit("/", 1)` with `os.path.basename(self.file_path)` (or
   `pathlib.PurePath(self.file_path).name`). Both handle `/` and `\` and
   are platform-correct.
2. Add a unit test in `tests/` covering both separators:
   - `"C:\\Users\\me\\data.json"` → `"data.json"`
   - `"/home/me/data.json"` → `"data.json"`
   - `""` / `None` → `"Untitled"`
   - dirty flag still appends `" *"`.
3. Audit other places that strip the directory part by hand; replace with
   the same helper. Likely candidates:
   - `app/recent_files.py` (display labels)
   - any window-title formatter
   Use `grep` for `rsplit("/"` and `split("/")[-1]`.

## Out of scope

- Tab tooltip (showing full path on hover) — track as a separate small
  enhancement after this fix.
- Path normalization on save / recent-files persistence.

## Definition of Done

- [ ] On Windows, opening a file shows only the basename in the tab.
- [ ] On Linux/macOS, behaviour is unchanged.
- [ ] Close-confirm dialog title shows only the basename.
- [ ] New unit test covers both separators and the empty-path case.
- [ ] No remaining hand-rolled `rsplit("/", 1)` / `split("/")[-1]` calls
      against file paths in the codebase (verified by `grep`).
- [ ] One commit, < 30 LOC of change + test.
