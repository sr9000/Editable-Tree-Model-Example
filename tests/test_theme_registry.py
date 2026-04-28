from __future__ import annotations

from importlib import resources
from typing import cast

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication

from themes import DARK_DEFAULT, LIGHT_DEFAULT, ThemeRegistry, detect_system_mode, load_theme_yaml
from themes._contrast import contrast_ratio
from themes.icon_provider import FileIconProvider, StubIconProvider


def _color_hex(color: QColor | None) -> str | None:
    if color is None:
        return None
    return color.name().lower()


def _assert_theme_equal(actual, expected) -> None:
    assert actual.name == expected.name
    assert actual.mode == expected.mode
    assert _color_hex(actual.palette.base_fg) == _color_hex(expected.palette.base_fg)
    assert _color_hex(actual.palette.base_bg) == _color_hex(expected.palette.base_bg)
    assert _color_hex(actual.palette.selection_fg) == _color_hex(expected.palette.selection_fg)
    assert _color_hex(actual.palette.selection_bg) == _color_hex(expected.palette.selection_bg)
    assert _color_hex(actual.palette.accent) == _color_hex(expected.palette.accent)
    assert actual.icon_search_paths == expected.icon_search_paths

    for json_type in expected.types:
        left = actual.types[json_type]
        right = expected.types[json_type]
        assert _color_hex(left.fg) == _color_hex(right.fg)
        assert _color_hex(left.bg) == _color_hex(right.bg)
        assert left.bold == right.bold
        assert left.italic == right.italic
        assert left.icon == right.icon


def _load_builtin(name: str):
    traversable = resources.files("themes.builtin").joinpath(name)
    with resources.as_file(traversable) as path:
        return load_theme_yaml(path, mode_default=LIGHT_DEFAULT)


def test_builtin_themes_reproduce_defaults():
    _assert_theme_equal(_load_builtin("light.yaml"), LIGHT_DEFAULT)
    _assert_theme_equal(_load_builtin("dark.yaml"), DARK_DEFAULT)


def test_builtin_themes_meet_wcag_aa_contrast():
    for theme in (_load_builtin("light.yaml"), _load_builtin("dark.yaml")):
        background = theme.palette.base_bg
        base_ratio = contrast_ratio(theme.palette.base_fg, background)
        assert base_ratio >= 3.0, f"{theme.name} base_fg contrast {base_ratio:.2f} < 3.0"

        for style in theme.types.values():
            if style.fg is None:
                continue
            ratio = contrast_ratio(style.fg, background)
            required = 3.0
            assert ratio >= required, f"{theme.name} contrast {ratio:.2f} < {required:.1f}"


def test_user_theme_override_wins_by_name(tmp_path):
    user_dir = tmp_path / "themes"
    user_dir.mkdir()
    (user_dir / "override.yaml").write_text(
        "\n".join(
            [
                "name: Default Light",
                "mode: light",
                "palette:",
                "  accent: '#ff0000'",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    registry = ThemeRegistry(user_dir=user_dir)
    overridden = registry.get("Default Light")

    assert overridden.mode == "light"
    assert _color_hex(overridden.palette.accent) == "#ff0000"


def test_broken_user_file_is_skipped(tmp_path, caplog):
    user_dir = tmp_path / "themes"
    user_dir.mkdir()
    (user_dir / "broken.yaml").write_text("name: [\n", encoding="utf-8")

    caplog.set_level("WARNING")
    registry = ThemeRegistry(user_dir=user_dir)

    assert registry.get("Default Light")
    assert any("Skipping broken user theme" in rec.message for rec in caplog.records)


def test_registry_build_icon_provider_uses_stub_without_icons_and_file_with_map(tmp_path):
    registry = ThemeRegistry(user_dir=tmp_path / "themes")
    assert isinstance(registry.build_icon_provider(registry.get("Default Light")), StubIconProvider)

    user_dir = tmp_path / "themes"
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "mapped.yaml").write_text(
        "\n".join(
            [
                "name: Mapped",
                "mode: light",
                "icons:",
                "  search_paths: []",
                "  map:",
                "    integer: number",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    registry.reload()
    assert isinstance(registry.build_icon_provider(registry.get("Mapped")), FileIconProvider)


class _FakeStyleHints:
    def __init__(self, scheme):
        self._scheme = scheme

    def colorScheme(self):
        return self._scheme


class _FakeWindowBrush:
    def __init__(self, color: QColor):
        self._color = color

    def color(self) -> QColor:
        return self._color


class _FakePalette:
    def __init__(self, color: QColor):
        self._window = _FakeWindowBrush(color)

    def window(self):
        return self._window


class _FakeApp:
    def __init__(self, scheme, window_color: str):
        self._hints = _FakeStyleHints(scheme)
        self._palette = _FakePalette(QColor(window_color))

    def styleHints(self):
        return self._hints

    def palette(self):
        return self._palette


@pytest.mark.parametrize(
    ("scheme", "window_color", "expected"),
    [
        (Qt.ColorScheme.Dark, "#fdf6e3", "dark"),
        (object(), "#1a1b26", "dark"),
        (object(), "#fdf6e3", "light"),
    ],
)
def test_detect_system_mode_prefers_color_scheme_then_palette_fallback(scheme, window_color, expected):
    app = _FakeApp(scheme, window_color)
    assert detect_system_mode(cast(QGuiApplication, cast(object, app))) == expected
