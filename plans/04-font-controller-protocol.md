# Stage 04 — Font controller subscriber protocol

Covers report scenario **C4**.

## Targets

| File                         | Lines | Probe                                             |
|------------------------------|-------|---------------------------------------------------|
| `app/font_controller.py`     | 194   | `getattr(target, "apply_font_profile", None)`     |
| `app/font_controller.py`     | 202   | `getattr(target, "setFont", None)`                |
| `app/font_controller.py`     | 205   | `getattr(target, "font", None)`                   |

## Why this is an OOP violation

The font controller dispatches on whether a target is "font-profile
aware" or "plain Qt widget". Both populations are finite and known to
the project:

- `JsonTab` (project-owned, has `apply_font_profile`).
- Any `QWidget` (Qt API, always has `font()` / `setFont(...)`).

`getattr` here hides what is really a two-branch type check, and reads
`.font` / `.setFont` from Qt with default `None`, which is misleading
because Qt **always** exposes them.

## Target design

### 1. `FontProfileAware` protocol (or ABC)

```python
@runtime_checkable
class FontProfileAware(Protocol):
    def apply_font_profile(self, profile: FontProfile) -> None: ...
```

`JsonTab` implements it. The controller registers subscribers typed as
`FontProfileAware | QWidget`.

### 2. Two-branch dispatch using `isinstance`

```python
def apply(self, target: FontProfileAware | QWidget, profile: FontProfile) -> None:
    if isinstance(target, FontProfileAware):
        target.apply_font_profile(profile)
        return
    # QWidget contract: font()/setFont() always exist
    base = target.font()
    target.setFont(profile.merged_with(base))
```

No `getattr`. Wrong-typed subscribers are rejected at registration time:

```python
def subscribe(self, target: FontProfileAware | QWidget) -> None:
    if not isinstance(target, (FontProfileAware, QWidget)):
        raise TypeError(...)
    self._subscribers.append(target)
```

## Steps

1. Declare `FontProfileAware` (`Protocol` + `@runtime_checkable`).
2. Mark `JsonTab` as implementing it (no inheritance needed, but the
   method signature must match — verify after stage 02).
3. Rewrite `FontController.apply(...)` to the two-branch `isinstance`
   form; remove all three `getattr` calls.
4. Add the `isinstance` precondition in `subscribe(...)`.
5. `grep -n 'getattr\|hasattr' app/font_controller.py` returns nothing.

## Acceptance criteria

- `app/font_controller.py` contains zero `getattr` / `hasattr`.
- `FontProfileAware` protocol is declared and `@runtime_checkable`.
- Font zoom / theme / per-tab font tests pass unchanged.
- Report inventory drops by **3** `getattr` expressions.
