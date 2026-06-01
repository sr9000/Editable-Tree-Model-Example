from __future__ import annotations

import pytest
import yaml

from themes import (DARK_DEFAULT, LIGHT_DEFAULT, ThemeLoadError,
                    load_theme_yaml, parse_theme_mapping)
from tree.types import JsonType


def _color_hex(color) -> str:
    return color.name().lower()


def _theme_to_mapping() -> dict:
    return {
        "name": "Solarized Light",
        "mode": "light",
        "palette": {
            "base_fg": "#657b83",
            "base_bg": "#fdf6e3",
            "selection_fg": "#fdf6e3",
            "selection_bg": "#268bd2",
            "accent": "#b58900",
        },
        "types": {
            "integer": {"fg": "#268bd2"},
            "float": {"fg": "#2aa198"},
            "percent": {"fg": "#2aa198", "italic": True},
            "boolean": {"fg": "#d33682"},
            "string": {"fg": "#657b83"},
            "unicode": {"fg": "#859900"},
            "multiline": {"fg": "#859900", "italic": True},
            "text": {"fg": "#859900", "italic": True},
            "date": {"fg": "#b58900"},
            "time": {"fg": "#b58900"},
            "datetime": {"fg": "#b58900"},
            "datetimezone": {"fg": "#b58900"},
            "bytes": {"fg": "#cb4b16"},
            "zlib": {"fg": "#cb4b16", "italic": True},
            "gzip": {"fg": "#cb4b16", "italic": True},
            "null": {"fg": "#93a1a1", "italic": True},
            "object": {"fg": "#073642", "bold": True},
            "array": {"fg": "#073642", "bold": True},
        },
        "icons": {
            "search_paths": ["./icons"],
            "map": {},
        },
    }


def test_round_trip_yaml_parse_load_and_hashable(tmp_path):
    mapping = _theme_to_mapping()
    path = tmp_path / "theme.yaml"
    path.write_text(yaml.safe_dump(mapping, sort_keys=False), encoding="utf-8")

    expected = parse_theme_mapping(mapping, mode_default=LIGHT_DEFAULT, base_dir=tmp_path)
    loaded = load_theme_yaml(path, mode_default=LIGHT_DEFAULT)

    assert loaded == expected
    assert hash(loaded) == hash(expected)


def test_icons_map_merges_into_type_style_icon_and_paths_are_resolved(tmp_path):
    theme_file = tmp_path / "theme.yaml"
    theme_file.write_text(
        "\n".join(
            [
                "name: With Icons",
                "mode: light",
                "icons:",
                "  search_paths: ['./icons']",
                "  map:",
                "    integer: number-icon",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    theme = load_theme_yaml(theme_file, mode_default=LIGHT_DEFAULT)
    assert theme.types[JsonType.INTEGER].icon == "number-icon"
    assert theme.icon_search_paths == ((tmp_path / "icons").resolve(),)


def test_partial_theme_overrides_only_integer_type():
    theme = parse_theme_mapping(
        {
            "name": "Partial",
            "mode": "light",
            "types": {
                "integer": {"fg": "#111111", "bold": True},
            },
        },
        mode_default=LIGHT_DEFAULT,
    )

    integer_fg = theme.types[JsonType.INTEGER].fg
    assert integer_fg is not None
    assert _color_hex(integer_fg) == "#111111"
    assert theme.types[JsonType.INTEGER].bold is True

    for json_type in JsonType:
        if json_type is JsonType.INTEGER:
            continue
        assert theme.types[json_type] == LIGHT_DEFAULT.types[json_type]


def test_bad_color_raises_with_offending_key():
    with pytest.raises(ThemeLoadError, match="types.integer.fg"):
        parse_theme_mapping(
            {
                "name": "Broken",
                "mode": "light",
                "types": {"integer": {"fg": "not-a-color"}},
            },
            mode_default=LIGHT_DEFAULT,
        )


def test_unknown_type_key_logs_warning_and_is_ignored(caplog):
    caplog.set_level("WARNING")

    theme = parse_theme_mapping(
        {
            "name": "Unknown Type",
            "mode": "light",
            "types": {
                "fancytype": {"fg": "#fff"},
            },
        },
        mode_default=LIGHT_DEFAULT,
    )

    assert theme.types == LIGHT_DEFAULT.types
    assert any("Unknown JsonType key in theme: fancytype" in rec.message for rec in caplog.records)


def test_missing_required_name_or_mode_raises():
    with pytest.raises(ThemeLoadError, match="name"):
        parse_theme_mapping({"mode": "light"}, mode_default=LIGHT_DEFAULT)

    with pytest.raises(ThemeLoadError, match="mode"):
        parse_theme_mapping({"name": "Missing mode"}, mode_default=LIGHT_DEFAULT)


def test_dark_mode_without_overrides_equals_dark_default_even_with_light_mode_default():
    theme = parse_theme_mapping(
        {
            "name": DARK_DEFAULT.name,
            "mode": "dark",
        },
        mode_default=LIGHT_DEFAULT,
    )

    assert theme == DARK_DEFAULT
