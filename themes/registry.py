from __future__ import annotations

import logging
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Literal

import yaml
from PySide6.QtCore import QStandardPaths

from themes._defaults import DARK_DEFAULT, LIGHT_DEFAULT
from themes.loader import ThemeLoadError, load_theme_yaml, parse_theme_mapping
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

    def _register(self, theme: ThemeSpec, path: Path, *, is_builtin: bool) -> None:
        if not is_builtin and theme.name in self._builtin_names:
            LOGGER.info("User theme '%s' overrides built-in theme", theme.name)

        self._themes[theme.name] = theme
        self._handles[theme.name] = ThemeHandle(name=theme.name, mode=theme.mode, path=path)

        if is_builtin:
            self._builtin_names.add(theme.name)

    def _load_builtin_themes(self) -> None:
        builtins_dir = resources.files("themes.builtin")
        for entry in sorted(builtins_dir.iterdir(), key=lambda p: p.name):
            if entry.name.startswith("_") or not entry.name.lower().endswith(".yaml"):
                continue

            try:
                loaded = yaml.safe_load(entry.read_text(encoding="utf-8"))
                if loaded is None:
                    loaded = {}
                theme = parse_theme_mapping(loaded, mode_default=LIGHT_DEFAULT)
            except (ThemeLoadError, yaml.YAMLError, OSError) as exc:
                LOGGER.warning("Failed to load built-in theme '%s': %s", entry.name, exc)
                continue

            self._register(theme, Path(str(entry)), is_builtin=True)

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
