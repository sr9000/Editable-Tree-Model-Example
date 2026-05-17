# Step 5 — In-tree indication of validation problems

_Commit-sized: 7 source files + 2 test files; ~420 LOC._

## Scope

Decorate the tree itself so every row that *is* an issue (and every
ancestor of an issue) is visually marked. Implementation route:

- new model role `VALIDATION_SEVERITY_ROLE`;
- the model returns the role's value from the active tab's
  `IssueIndex` (no copy of state in the model);
- the existing `ValueDelegate` and `NameDelegate` paint a small
  10×10 px badge in the bottom-right corner of the cell, plus an
  optional foreground/background tint pulled from the theme.

## Files touched (9)

```
tree/model_roles.py                  # +VALIDATION_SEVERITY_ROLE = UserRole + 2
tree/model.py                        # data(): forward VALIDATION_SEVERITY_ROLE
                                     # to self._issue_index_provider; lightweight
                                     # provider setter so the model stays
                                     # standalone-testable
documents/tab.py                     # plug provider: model.set_issue_index_provider(
                                     #   lambda path: self._issue_index)
                                     # repaint via dataChanged on
                                     # validationChanged
delegates/value.py                   # paint(): overlay badge after super().paint
delegates/name_delegate.py           # idem (badge only on name col)
delegates/validation_badge.py        # _draw_severity_badge(painter, rect, severity, theme)
themes/spec.py                       # +ValidationStyle(error_fg, warning_fg,
                                     #  error_badge, warning_badge) in Palette
themes/builtin/light.yaml            # +validation: {error: ..., warning: ...}
themes/builtin/dark.yaml             # idem
tests/test_validation_tree_indication.py
tests/test_validation_role.py
```

(Counted source-file budget: 9 — one over comfort. If review pushes
back, fold `delegates/validation_badge.py` into `delegates/base.py`
to drop to 8.)

## Public API

```python
# tree/model_roles.py
VALIDATION_SEVERITY_ROLE: Final = Qt.ItemDataRole.UserRole + 2  # "error"/"warning"/None

# tree/model.py
def set_issue_index_provider(
    self,
    provider: Callable[[tuple[int, ...]], str | None] | None,
) -> None: ...

# themes/spec.py (additive, frozen)
@dataclass(frozen=True, slots=True)
class ValidationStyle:
    error_fg: QColor | None
    warning_fg: QColor | None
    error_badge: QColor
    warning_badge: QColor

@dataclass(frozen=True, slots=True)
class Palette:
    # ...existing fields...
    validation: ValidationStyle
```

## Implementation notes

- Provider lookup happens **only** when the role is requested, so
  the model does no work for rows the delegate doesn't repaint.
- Path is computed once per `data()` call via
  `_index_to_model_path(index)` (already exists internally; expose
  as a `_path_of` helper if missing).
- `IssueIndex` answers `severity_at(path)` for exact hits and
  `ancestor_severity(path)` for ancestor highlighting; the model
  combines them: exact > ancestor when both apply.
- The delegate badge is drawn *after* the existing
  `_apply_type_style` so it overlays the cell without disturbing
  selection/hover paint. Position: bottom-right corner, 8px square,
  filled circle.
- `JsonTab` listens to its own `validationChanged` and emits a
  recursive `dataChanged(top_left, bottom_right, [VALIDATION_SEVERITY_ROLE])`
  span so all visible rows repaint without rebuilding indices.
- Themes:
  - `light.yaml`: `error: '#d13438'`, `warning: '#bf6900'`.
  - `dark.yaml`: `error: '#ff6b6b'`, `warning: '#ffb84d'`.
  - Loader falls back to hard-coded defaults if the block is absent
    (preserves Step-1 total-fallback semantics for user themes).

## Tests

- `test_validation_role.py`: model returns "error" / "warning" /
  `None` for exact and ancestor paths; provider absent → always
  `None`.
- `test_validation_tree_indication.py` (qtbot):
  - render a tab with two errors, grab the badge pixmap from the
    value-col rect, assert non-default pixel exists at the expected
    corner;
  - removing the schema clears all badges.

## Out of scope

- Toolbar / auto-rescan (Step 6).
- WCAG contrast verification — relies on existing
  `themes/_contrast.py` helpers but adds no new accessibility tests.

## Commit message

```
feat(validation): in-tree severity badges

- VALIDATION_SEVERITY_ROLE plumbed through JsonTreeModel via a
  pluggable IssueIndex provider (no model-level state copy)
- ValueDelegate / NameDelegate overlay a corner badge using the
  theme's new ValidationStyle palette block
- built-in light/dark themes ship sensible default error/warning
  colours; loader fall-back keeps user themes valid
- JsonTab repaints visible rows via dataChanged on
  validationChanged
```
