from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Literal

from PySide6.QtCore import QStandardPaths

from themes._defaults import DARK_DEFAULT, LIGHT_DEFAULT
from themes.icon_provider import FileIconProvider, IconProvider, StubIconProvider
from themes.loader import ThemeLoadError, load_theme_yaml
from themes.spec import ThemeSpec

LOGGER = logging.getLogger(__name__)

_DEFAULT_THEME_NAME_BY_MODE: dict[Literal["light", "dark"], str] = {
    "light": LIGHT_DEFAULT.name,
    "dark": DARK_DEFAULT.name,
}


@dataclass(frozen=True)
class ThemeHandle:
    name: str
    mode: Literal["light", "dark"]
    path: Path


def _find_builtins_dir() -> Path | None:
    """Locate the on-disk ``themes/builtin`` directory.

    Tries, in order:

    1. ``<sys._MEIPASS>/themes/builtin`` — PyInstaller frozen onefile/onefolder.
       ``collect_data_files("themes.builtin")`` in the spec places the full
       subtree (YAMLs + every icon sub-directory) here, so this branch is
       authoritative when frozen.
    2. ``Path(__file__).parent / "builtin"`` — running from source / a wheel
       installed in *editable* mode.
    3. ``importlib.resources.files("themes.builtin")`` cast to ``Path`` —
       last-ditch fallback for unusual install layouts.  We *intentionally*
       do not use ``importlib.resources`` as the primary strategy: when the
       package is bundled by PyInstaller, ``resources.as_file`` of individual
       YAML files can extract each file in isolation, separating it from
       its sibling icon sub-directories and breaking the relative
       ``./mingcute-light`` icon search paths declared inside each YAML.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if isinstance(meipass, str) and meipass:
        cand = Path(meipass) / "themes" / "builtin"
        if cand.is_dir():
            return cand

    cand = Path(__file__).resolve().parent / "builtin"
    if cand.is_dir():
        return cand

    try:
        traversable = resources.files("themes.builtin")
        fspath = getattr(traversable, "__fspath__", None)
        if callable(fspath):
            raw = fspath()
            if isinstance(raw, (str, bytes)):
                cand = Path(os.fsdecode(raw))
                if cand.is_dir():
                    return cand
    except (ModuleNotFoundError, TypeError, OSError):
        pass

    return None


class ThemeRegistry:
    def __init__(self, user_dir: Path | None = None) -> None:
        if user_dir is None:
            app_config = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation))
            user_dir = app_config / "themes"
        self._user_dir = user_dir
        self._themes: dict[str, ThemeSpec] = {}
        self._handles: dict[str, ThemeHandle] = {}
        self._builtin_names: set[str] = set()
        self.reload()

    def reload(self) -> None:
        self._themes.clear()
        self._handles.clear()
        self._builtin_names.clear()
        self._load_builtin_themes()
        self._load_user_themes()

    def list_themes(self) -> list[ThemeHandle]:
        return sorted(self._handles.values(), key=lambda h: (h.mode, h.name.casefold()))

    def get(self, name: str) -> ThemeSpec:
        return self._themes[name]

    def default_for_mode(self, mode: Literal["light", "dark"]) -> ThemeSpec:
        default_name = _DEFAULT_THEME_NAME_BY_MODE[mode]
        if default_name in self._themes:
            return self._themes[default_name]
        return LIGHT_DEFAULT if mode == "light" else DARK_DEFAULT

    def build_icon_provider(self, theme: ThemeSpec) -> IconProvider:
        if any(style.icon for style in theme.types.values()):
            return FileIconProvider(theme)
        return StubIconProvider()

    @property
    def user_dir(self) -> Path:
        return self._user_dir

    def _register(self, theme: ThemeSpec, path: Path, *, is_builtin: bool) -> None:
        if not is_builtin and theme.name in self._builtin_names:
            LOGGER.info("User theme '%s' overrides built-in theme", theme.name)

        self._themes[theme.name] = theme
        self._handles[theme.name] = ThemeHandle(name=theme.name, mode=theme.mode, path=path)

        if is_builtin:
            self._builtin_names.add(theme.name)

    def _load_builtin_themes(self) -> None:
        builtins_dir = _find_builtins_dir()
        if builtins_dir is None:
            LOGGER.error(
                "Built-in themes directory could not be located. "
                "Looked under sys._MEIPASS, source tree, and importlib.resources. "
                "Falling back to compiled-in defaults only.",
            )
            return

        yaml_files = sorted(builtins_dir.glob("*.yaml"))
        if not yaml_files:
            LOGGER.error(
                "No built-in theme YAMLs found in %s. " "Falling back to compiled-in defaults only.",
                builtins_dir,
            )
            return

        loaded = 0
        for entry in yaml_files:
            if entry.name.startswith("_"):
                continue
            try:
                theme = load_theme_yaml(entry, mode_default=LIGHT_DEFAULT)
            except (ThemeLoadError, OSError) as exc:
                LOGGER.warning("Failed to load built-in theme '%s': %s", entry.name, exc)
                continue
            self._register(theme, entry, is_builtin=True)
            loaded += 1

        LOGGER.info("Loaded %d built-in theme(s) from %s", loaded, builtins_dir)

    def _load_user_themes(self) -> None:
        if not self._user_dir.exists():
            return

        for path in sorted(self._user_dir.glob("*.yaml")):
            try:
                theme = load_theme_yaml(path, mode_default=LIGHT_DEFAULT)
            except ThemeLoadError as exc:
                LOGGER.warning("Skipping broken user theme '%s': %s", path, exc)
                continue

            self._register(theme, path, is_builtin=False)
