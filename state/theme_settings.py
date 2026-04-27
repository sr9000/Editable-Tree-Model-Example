from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtGui import QGuiApplication

from settings import APPLICATION_ID
from themes.auto import detect_system_mode
from themes.registry import ThemeRegistry
from themes.spec import ThemeSpec

_FOLLOW_SYSTEM_KEY = "theme/follow_system"
_LIGHT_THEME_KEY = "theme/light_name"
_DARK_THEME_KEY = "theme/dark_name"

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


def resolve_active_theme(registry: ThemeRegistry, app: QGuiApplication) -> ThemeSpec:
    settings = QSettings(APPLICATION_ID, "theme")
    follow_system = _coerce_bool(settings.value(_FOLLOW_SYSTEM_KEY, True), default=True)

    mode = detect_system_mode(app)
    if follow_system:
        preferred_name = _coerce_name(
            settings.value(_DARK_THEME_KEY if mode == "dark" else _LIGHT_THEME_KEY),
            default=_DEFAULT_DARK_NAME if mode == "dark" else _DEFAULT_LIGHT_NAME,
        )
        try:
            return registry.get(preferred_name)
        except KeyError:
            return registry.default_for_mode(mode)

    # Phase 2 has no manual light/dark toggle yet; keep deterministic behavior.
    preferred_name = _coerce_name(settings.value(_LIGHT_THEME_KEY), default=_DEFAULT_LIGHT_NAME)
    if mode == "dark":
        preferred_name = _coerce_name(settings.value(_DARK_THEME_KEY), default=_DEFAULT_DARK_NAME)

    try:
        return registry.get(preferred_name)
    except KeyError:
        return registry.default_for_mode(mode)
