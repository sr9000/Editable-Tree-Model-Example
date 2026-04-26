# Phase 4 — Icon provider stub

## Deliverable

An `IconProvider` API that returns a `QIcon` for any `JsonType`. The
real implementation is wired but **all icons are empty placeholders**
in this phase — no SVGs are bundled yet. The theme YAML's `icons:`
block is parsed and resolved against an asset search path so that
later phases (and end users) can drop in their own SVG/PNG sets.

This phase exists so that Phase 5 (placement in tree + combobox) and
the user theme-file format are forward-compatible *today*: the
`icons:` block is valid and consumed, just visually empty.

## Scope

### `themes/icon_provider.py`

```python
class IconProvider(Protocol):
    def for_type(self, t: JsonType) -> QIcon: ...
    def reload(self) -> None: ...

class StubIconProvider:
    """Returns QIcon() for every type. Used until SVGs ship."""
    def for_type(self, t): return QIcon()
    def reload(self): pass

class FileIconProvider:
    """Resolves theme.icons.map[json_type] against search_paths."""
    def __init__(self, theme: ThemeSpec): ...
    def for_type(self, t): ...   # returns QIcon(<resolved path>) or QIcon()
    def reload(self): ...        # clears internal QIcon cache
```

`FileIconProvider` resolution algorithm:
1. Take logical key `key = theme.types[t].icon` (or
   `theme.icons.map[t]` if not on `TypeStyle`).
2. If `key is None` → empty `QIcon()`.
3. For each `dir` in `theme.icon_search_paths` (in order), try
   `dir / f"{key}.svg"`, then `.png`, then `.ico`.
4. First hit wins; cached in a `dict[JsonType, QIcon]`.
5. Miss → empty `QIcon()` and a single WARNING log per session.

### `themes/spec.py` (extension)

- `TypeStyle.icon: str | None` already declared in Phase 1.
- `ThemeSpec.icon_search_paths: tuple[Path, ...]` populated by the
  loader from `icons.search_paths` (paths are resolved relative to
  the theme YAML's directory).

### `themes/loader.py` (extension)

- Parse `icons:` block.
  - `icons.search_paths: list[str]` → resolved to absolute paths
    relative to the YAML file's parent dir.
  - `icons.map: dict[str, str]` → `JsonType` name → logical icon key
    (string). Merged into each `TypeStyle.icon`.
- A theme that omits `icons:` is still valid; default
  `icon_search_paths = ()`, all `TypeStyle.icon = None`.

### `themes/registry.py` (extension)

- `ThemeRegistry.build_icon_provider(theme) -> IconProvider`:
  - Returns `StubIconProvider()` when no icon mapping is present
    (Phase-4-default for built-ins).
  - Returns `FileIconProvider(theme)` when the theme declares any
    `icons.map` entry.

### Built-in YAMLs (Phase 2 files)

- Add an empty stub:
  ```yaml
  icons:
    search_paths: []
    map: {}
  ```
- No SVGs ship in Phase 4. Phase 5 will add them under
  `themes/builtin/icons/` and reference them here.

## Tests (`tests/test_icon_provider.py`)

- `StubIconProvider.for_type(t).isNull()` is `True` for every
  `JsonType`.
- `FileIconProvider` with a tmp dir and a fake `<key>.svg` returns a
  non-null `QIcon` for the mapped type.
- Search-path order respected: file in the first dir wins over a
  same-key file in the second.
- Missing key → null icon, single WARNING (use `caplog`).
- `reload()` re-reads the filesystem after a file is added/removed.

## Done criteria

- Theme YAMLs can declare `icons:` blocks without breaking the
  loader.
- `JsonTab` (or `MainWindow`) holds an `IconProvider` alongside the
  `ThemeSpec`. Nothing visually changes yet — Phase 5 places the
  icons.
- All previous tests still green; new icon-provider tests green.
