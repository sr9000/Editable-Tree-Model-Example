from __future__ import annotations

import logging
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal

import yaml
from PySide6.QtGui import QColor

from themes._defaults import DARK_DEFAULT, LIGHT_DEFAULT
from themes.spec import Palette, ThemeSpec, TypeStyle
from tree.types import JsonType

LOGGER = logging.getLogger(__name__)

_TYPE_KEYS: dict[str, JsonType] = {
    "integer": JsonType.INTEGER,
    "float": JsonType.FLOAT,
    "percent": JsonType.PERCENT,
    "boolean": JsonType.BOOLEAN,
    "string": JsonType.STRING,
    "unicode": JsonType.UNICODE,
    "multiline": JsonType.MULTILINE,
    "text": JsonType.TEXT,
    "date": JsonType.DATE,
    "time": JsonType.TIME,
    "datetime": JsonType.DATETIME,
    "datetimezone": JsonType.DATETIMEZONE,
    "bytes": JsonType.BYTES,
    "zlib": JsonType.ZLIB,
    "gzip": JsonType.GZIP,
    "null": JsonType.NULL,
    "object": JsonType.OBJECT,
    "array": JsonType.ARRAY,
}


class ThemeLoadError(ValueError):
    pass


def _copy_color(value: QColor | None) -> QColor | None:
    return None if value is None else QColor(value)


def _parse_color(value: Any, *, key: str) -> QColor:
    if not isinstance(value, str):
        raise ThemeLoadError(f"Invalid color for '{key}': {value!r}")
    color = QColor(value)
    if not color.isValid():
        raise ThemeLoadError(f"Invalid color for '{key}': {value!r}")
    return color


def _as_mapping(value: Any, *, key: str) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    LOGGER.warning("Theme key '%s' should be a mapping; ignoring invalid value", key)
    return {}


def _as_mode(value: Any) -> Literal["light", "dark"]:
    if value not in {"light", "dark"}:
        raise ThemeLoadError(f"Invalid mode: {value!r}")
    return value


def _pick_base_default(mode: Literal["light", "dark"], mode_default: ThemeSpec) -> ThemeSpec:
    if mode_default.mode == mode:
        return mode_default
    return DARK_DEFAULT if mode == "dark" else LIGHT_DEFAULT


def _merge_palette(palette_data: dict[str, Any], base: Palette) -> Palette:
    return Palette(
        base_fg=(
            _parse_color(palette_data["base_fg"], key="palette.base_fg")
            if "base_fg" in palette_data
            else QColor(base.base_fg)
        ),
        base_bg=(
            _parse_color(palette_data["base_bg"], key="palette.base_bg")
            if "base_bg" in palette_data
            else QColor(base.base_bg)
        ),
        selection_fg=(
            _parse_color(palette_data["selection_fg"], key="palette.selection_fg")
            if "selection_fg" in palette_data
            else QColor(base.selection_fg)
        ),
        selection_bg=(
            _parse_color(palette_data["selection_bg"], key="palette.selection_bg")
            if "selection_bg" in palette_data
            else QColor(base.selection_bg)
        ),
        accent=(
            _parse_color(palette_data["accent"], key="palette.accent")
            if "accent" in palette_data
            else QColor(base.accent)
        ),
    )


def _merge_style(style_data: dict[str, Any], base: TypeStyle, *, key_prefix: str) -> TypeStyle:
    fg = _parse_color(style_data["fg"], key=f"{key_prefix}.fg") if "fg" in style_data else _copy_color(base.fg)
    bg = _parse_color(style_data["bg"], key=f"{key_prefix}.bg") if "bg" in style_data else _copy_color(base.bg)

    bold = style_data.get("bold", base.bold)
    if not isinstance(bold, bool):
        LOGGER.warning("Theme key '%s.bold' should be bool; keeping default", key_prefix)
        bold = base.bold

    italic = style_data.get("italic", base.italic)
    if not isinstance(italic, bool):
        LOGGER.warning("Theme key '%s.italic' should be bool; keeping default", key_prefix)
        italic = base.italic

    icon = style_data.get("icon", base.icon)
    if icon is not None and not isinstance(icon, str):
        LOGGER.warning("Theme key '%s.icon' should be string; keeping default", key_prefix)
        icon = base.icon

    return TypeStyle(fg=fg, bg=bg, bold=bold, italic=italic, icon=icon)


def _merge_types(types_data: dict[str, Any], base: ThemeSpec) -> MappingProxyType:
    merged: dict[JsonType, TypeStyle] = {}
    for json_type in JsonType:
        merged[json_type] = _merge_style({}, base.types[json_type], key_prefix=f"types.{json_type.value}")

    for raw_key, raw_style in types_data.items():
        if not isinstance(raw_key, str):
            LOGGER.warning("Theme type key %r is not a string; ignoring", raw_key)
            continue

        json_type = _TYPE_KEYS.get(raw_key.casefold())
        if json_type is None:
            LOGGER.warning("Unknown JsonType key in theme: %s", raw_key)
            continue

        style_data = _as_mapping(raw_style, key=f"types.{raw_key}")
        merged[json_type] = _merge_style(style_data, base.types[json_type], key_prefix=f"types.{raw_key}")

    return MappingProxyType(merged)


def _parse_icon_search_paths(data: dict[str, Any]) -> tuple[Path, ...]:
    icons_data = _as_mapping(data.get("icons"), key="icons")
    raw_paths = icons_data.get("search_paths", [])
    if raw_paths is None:
        return ()
    if not isinstance(raw_paths, list):
        LOGGER.warning("Theme key 'icons.search_paths' should be a list; ignoring")
        return ()

    paths: list[Path] = []
    for item in raw_paths:
        if isinstance(item, str):
            paths.append(Path(item))
        else:
            LOGGER.warning("Ignoring non-string icon search path: %r", item)
    return tuple(paths)


def parse_theme_mapping(data: dict, *, mode_default: ThemeSpec) -> ThemeSpec:
    if not isinstance(data, dict):
        raise ThemeLoadError("Theme YAML root must be a mapping")

    if "name" not in data:
        raise ThemeLoadError("Theme is missing required top-level key: name")
    if "mode" not in data:
        raise ThemeLoadError("Theme is missing required top-level key: mode")

    name = data["name"]
    if not isinstance(name, str) or not name.strip():
        raise ThemeLoadError("Theme key 'name' must be a non-empty string")

    mode = _as_mode(data["mode"])
    base_default = _pick_base_default(mode, mode_default)

    palette_data = _as_mapping(data.get("palette"), key="palette")
    types_data = _as_mapping(data.get("types"), key="types")

    return ThemeSpec(
        name=name,
        mode=mode,
        palette=_merge_palette(palette_data, base_default.palette),
        types=_merge_types(types_data, base_default),
        icon_search_paths=_parse_icon_search_paths(data),
    )


def load_theme_yaml(path: Path, *, mode_default: ThemeSpec) -> ThemeSpec:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ThemeLoadError(f"Invalid YAML in {path}: {exc}") from exc
    except OSError as exc:
        raise ThemeLoadError(f"Unable to read theme file: {path}") from exc

    if loaded is None:
        loaded = {}
    if not isinstance(loaded, dict):
        raise ThemeLoadError("Theme YAML root must be a mapping")

    return parse_theme_mapping(loaded, mode_default=mode_default)
