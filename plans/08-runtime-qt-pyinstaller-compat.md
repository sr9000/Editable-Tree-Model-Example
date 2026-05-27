# Stage 08 — Runtime / Qt / PyInstaller / tzinfo compatibility

Covers report scenarios **A1–A5**.

## Targets

| File                            | Line     | Probe                                                  |
|---------------------------------|----------|--------------------------------------------------------|
| `main.py`                       | 17       | `getattr(sys, "_MEIPASS", None)`                       |
| `themes/registry.py`            | 52       | `getattr(sys, "_MEIPASS", None)`                       |
| `themes/registry.py`            | 64       | `getattr(traversable, "__fspath__", None)`             |
| `themes/auto.py`                | 11       | `hasattr(hints, "colorScheme")`                        |
| `app/theme_controller.py`       | 86, 372  | `hasattr(style_hints, "colorSchemeChanged")`           |
| `app/theme_controller.py`       | 174      | `hasattr(QPalette.ColorRole, "Accent")`                |
| `app/theme_controller.py`       | 183      | `getattr(style_hints, "setColorScheme", None)`         |
| `qt2py/__init__.py`             | 11       | `getattr(dt.tzinfo, "key", None) / "zone"`             |
| `qhexedit/chunks.py`            | 109, 275 | `hasattr(_qba, "data")`                                |

## Why these are *external* runtime probes

These targets are not project-owned:

- `sys._MEIPASS` is PyInstaller's frozen-mode marker.
- `QStyleHints.colorScheme` / `setColorScheme` / `colorSchemeChanged`
  vary by Qt version and binding.
- `QPalette.ColorRole.Accent` is a Qt 6.6+ enum.
- `tzinfo` providers (`zoneinfo`, `pytz`, custom) expose `key` / `zone`
  inconsistently.
- `QByteArray.data` varies between PySide / PyQt bindings.
- `Traversable.__fspath__` is optional in `importlib.resources`.

This is a legitimate need. But the project-wide rule is: **the probe
lives in exactly one module**, and other files import a typed wrapper.

## Target design — single runtime-compat module

Create `runtime_compat/` (small package) or `app/runtime_compat.py` with:

```python
# Frozen / source layout
def meipass_root() -> Path | None:
    """Return PyInstaller extraction root if frozen, else None."""

def bundled_resource_path(traversable) -> Path:
    """Best-effort filesystem path for a Traversable (uses __fspath__ when present)."""

# Qt color-scheme
def system_color_scheme(hints: QStyleHints) -> Qt.ColorScheme | None: ...
def push_color_scheme(hints: QStyleHints, scheme: Qt.ColorScheme) -> bool: ...
def color_scheme_changed_signal(hints: QStyleHints) -> Signal | None: ...
def accent_color_role() -> QPalette.ColorRole | None: ...

# Tz
def tz_name(dt: datetime) -> str | None: ...

# Qt buffer
def qba_to_bytes(qba) -> bytes: ...
```

Each function is the **one** place a `getattr` / `hasattr` may appear,
and each is allowlisted explicitly by the stage 10 hook (allowlist by
file path **and** line, or by inline `# allow: runtime-probe` marker).

Callers:

- `main.py`, `themes/registry.py` → `meipass_root()`,
  `bundled_resource_path()`.
- `themes/auto.py`, `app/theme_controller.py` → the four Qt color-scheme
  helpers.
- `qt2py/__init__.py` → `tz_name(dt)`.
- `qhexedit/chunks.py` → `qba_to_bytes(qba)`.

## Steps

1. Create `app/runtime_compat.py` (or `runtime_compat/` package).
2. Move each probe into a typed function with explicit return type and
   docstring describing the runtime variability it hides.
3. Replace every call site listed above with an import from
   `runtime_compat`.
4. Add a unit test per helper using a stub object missing the probed
   attribute, asserting graceful fallback.
5. `grep -RIn 'getattr\|hasattr' main.py themes/ app/theme_controller.py qt2py/ qhexedit/`
   returns nothing.

## Acceptance criteria

- All seven files listed above contain zero `getattr` / `hasattr`.
- All runtime probes are concentrated in `runtime_compat.py` (or
  package), and that module is the only one allowlisted by stage 10 for
  this cluster.
- Theme switching, frozen-build resource resolution, datetime
  round-trips with named tz, and hex-edit reads pass existing tests.
- Report inventory drops by **10** expressions in these files; the same
  count reappears centralized inside `runtime_compat`.
