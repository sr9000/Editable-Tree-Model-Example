from __future__ import annotations

from typing import Literal

from PySide6.QtCore import QSettings
from PySide6.QtGui import QGuiApplication

from settings import APPLICATION_ID
from themes.auto import detect_system_mode
from themes.registry import ThemeRegistry
from themes.spec import ThemeSpec

_FOLLOW_SYSTEM_KEY = "theme/follow_system"
_LIGHT_THEME_KEY = "theme/light_name"
_DARK_THEME_KEY = "theme/dark_name"
_MANUAL_THEME_KEY = "theme/manual_name"
_WATCH_USER_DIR_KEY = "theme/watch_user_dir"

_DEFAULT_LIGHT_NAME = "Default Light"
_DEFAULT_DARK_NAME = "Default Dark"


def _coerce_bool(value, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().casefold()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def _coerce_name(value, *, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def _settings() -> QSettings:
    return QSettings(APPLICATION_ID, "theme")


def get_follow_system() -> bool:
    return _coerce_bool(_settings().value(_FOLLOW_SYSTEM_KEY, True), default=True)


def set_follow_system(enabled: bool) -> None:
    _settings().setValue(_FOLLOW_SYSTEM_KEY, bool(enabled))


def get_watch_user_dir() -> bool:
    return _coerce_bool(_settings().value(_WATCH_USER_DIR_KEY, False), default=False)


def set_watch_user_dir(enabled: bool) -> None:
    _settings().setValue(_WATCH_USER_DIR_KEY, bool(enabled))


def get_preferred_theme_name(mode: Literal["light", "dark"]) -> str:
    key = _DARK_THEME_KEY if mode == "dark" else _LIGHT_THEME_KEY
    default = _DEFAULT_DARK_NAME if mode == "dark" else _DEFAULT_LIGHT_NAME
    return _coerce_name(_settings().value(key), default=default)


def set_preferred_theme_name(mode: Literal["light", "dark"], name: str) -> None:
    if mode == "dark":
        _settings().setValue(_DARK_THEME_KEY, name)
    else:
        _settings().setValue(_LIGHT_THEME_KEY, name)


def get_manual_theme_name() -> str:
    return _coerce_name(_settings().value(_MANUAL_THEME_KEY), default=_DEFAULT_LIGHT_NAME)


def set_manual_theme_name(name: str) -> None:
    _settings().setValue(_MANUAL_THEME_KEY, name)


def resolve_active_theme(registry: ThemeRegistry, app: QGuiApplication) -> ThemeSpec:
    follow_system = get_follow_system()

    mode = detect_system_mode(app)
    if follow_system:
        preferred_name = get_preferred_theme_name(mode)
        try:
            return registry.get(preferred_name)
        except KeyError:
            return registry.default_for_mode(mode)

    preferred_name = get_manual_theme_name()

    try:
        return registry.get(preferred_name)
    except KeyError:
        fallback_name = get_preferred_theme_name(mode)
        try:
            return registry.get(fallback_name)
        except KeyError:
            return registry.default_for_mode(mode)
