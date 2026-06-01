"""Theme loading and immutable theme specification types."""

from themes._defaults import DARK_DEFAULT, LIGHT_DEFAULT
from themes.auto import detect_system_mode
from themes.icon_provider import (FileIconProvider, IconProvider,
                                  StubIconProvider)
from themes.loader import ThemeLoadError, load_theme_yaml, parse_theme_mapping
from themes.registry import ThemeHandle, ThemeRegistry
from themes.spec import Palette, ThemeSpec, TypeStyle

__all__ = [
    "TypeStyle",
    "Palette",
    "ThemeSpec",
    "ThemeLoadError",
    "load_theme_yaml",
    "parse_theme_mapping",
    "LIGHT_DEFAULT",
    "DARK_DEFAULT",
    "ThemeHandle",
    "ThemeRegistry",
    "detect_system_mode",
    "IconProvider",
    "StubIconProvider",
    "FileIconProvider",
]
