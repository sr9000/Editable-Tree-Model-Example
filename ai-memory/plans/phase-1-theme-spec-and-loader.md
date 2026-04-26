# Phase 1 — Theme spec & loader

## Deliverable

A `themes/` package that parses a YAML theme file into an immutable
`ThemeSpec` dataclass with **total fallback** semantics.

## Scope

- New package `themes/` with no dependency on Qt widgets, only on
  `QColor` (which is in `PySide6.QtGui` and is cheap to import).
- No editor wiring yet — Phase 3 does that. This phase ends with a
  green test suite proving load + merge + fallback.

## File-by-file

### `themes/spec.py`

```python
@dataclass(frozen=True)
class TypeStyle:
    fg: QColor | None = None
    bg: QColor | None = None
    bold: bool = False
    italic: bool = False
    icon: str | None = None          # logical icon key, resolved in Phase 4

@dataclass(frozen=True)
class Palette:
    base_fg: QColor
    base_bg: QColor
    selection_fg: QColor
    selection_bg: QColor
    accent: QColor

@dataclass(frozen=True)
class ThemeSpec:
    name: str
    mode: Literal["light", "dark"]
    palette: Palette
    types: Mapping[JsonType, TypeStyle]   # complete: every JsonType
    icon_search_paths: tuple[Path, ...]   # empty in Phase 1
```

`ThemeSpec.types` is guaranteed to contain **every** `JsonType` after
load, by merging with a built-in default-for-mode dict.

### `themes/loader.py`

```python
def load_theme_yaml(path: Path, *, mode_default: ThemeSpec) -> ThemeSpec
def parse_theme_mapping(data: dict, *, mode_default: ThemeSpec) -> ThemeSpec
```

- Uses `yaml.safe_load`.
- Color values accept `#rgb`, `#rrggbb`, `#rrggbbaa`, and named CSS
  colors (delegated to `QColor.isValidColor`).
- Unknown JsonType keys → `logging.warning` + ignored (forward-
  compatible).
- Missing keys → filled from `mode_default`.
- Returns a fully-populated `ThemeSpec`; never raises on partial input.
  Raises `ThemeLoadError` only on syntactically broken YAML or on a
  required top-level key (`name`, `mode`) being absent.

### `themes/_defaults.py` (private)

Hard-coded `LIGHT_DEFAULT: ThemeSpec` and `DARK_DEFAULT: ThemeSpec`
covering every `JsonType`. These are the ground truth that Phase 2's
`light.yaml` / `dark.yaml` must reproduce; they also serve as the
fallback target when a user theme leaves keys unset.

## YAML grammar (frozen this phase)

```yaml
name: Solarized Light
mode: light          # 'light' | 'dark'

palette:
  base_fg:       "#657b83"
  base_bg:       "#fdf6e3"
  selection_fg:  "#fdf6e3"
  selection_bg:  "#268bd2"
  accent:        "#b58900"

types:
  integer:    { fg: "#268bd2" }
  float:      { fg: "#2aa198" }
  percent:    { fg: "#2aa198", italic: true }
  boolean:    { fg: "#d33682" }
  string:     { fg: "#657b83" }
  unicode:    { fg: "#859900" }
  multiline:  { fg: "#859900", italic: true }
  text:       { fg: "#859900", italic: true }
  date:       { fg: "#b58900" }
  time:       { fg: "#b58900" }
  datetime:   { fg: "#b58900" }
  datetimezone: { fg: "#b58900" }
  bytes:      { fg: "#cb4b16" }
  zlib:       { fg: "#cb4b16", italic: true }
  gzip:       { fg: "#cb4b16", italic: true }
  null:       { fg: "#93a1a1", italic: true }
  object:     { fg: "#073642", bold: true }
  array:      { fg: "#073642", bold: true }

icons:               # parsed but unused in Phase 1
  search_paths: ["./icons"]
  map: {}            # JsonType → logical icon key, filled in Phase 4
```

## Tests (`tests/test_theme_loader.py`)

- Round-trip: dump a known mapping, reload, assert `ThemeSpec`
  equality on every field.
- Partial file: only `integer` overridden → all other types equal the
  `mode_default` styles.
- Bad color string → `ThemeLoadError` with the offending key in the
  message.
- Unknown JsonType key (`fancytype: { fg: "#fff" }`) → logged, no
  raise, theme still usable.
- Missing `name` or `mode` → `ThemeLoadError`.
- `mode: dark` with no overrides → equals `DARK_DEFAULT`.

## Done criteria

- `pytest tests/test_theme_loader.py -q` is green.
- No imports from `delegates/`, `documents/`, or `tree/` in the
  `themes/` package (one-way dependency: theming knows about
  `JsonType`, nothing else knows about themes yet).
- `ThemeSpec` is hashable + frozen so it can sit on `JsonTab` safely.
