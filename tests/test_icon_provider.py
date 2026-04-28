from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from themes import LIGHT_DEFAULT, parse_theme_mapping
from themes.icon_provider import FileIconProvider, StubIconProvider
from tree.types import JsonType


def _write_png(path: Path, color: str) -> None:
    image = QImage(8, 8, QImage.Format.Format_ARGB32)
    image.fill(QColor(color))
    assert image.save(str(path))


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_stub_provider_returns_null_icons_for_all_types(qapp):
    provider = StubIconProvider()
    for json_type in JsonType:
        assert provider.for_type(json_type).isNull()


def test_file_provider_loads_icon_from_svg_mapping(tmp_path, qapp):
    icons_dir = tmp_path / "icons"
    icons_dir.mkdir()
    (icons_dir / "integer.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"><rect width="16" height="16" fill="#ff0000"/></svg>',
        encoding="utf-8",
    )

    theme = parse_theme_mapping(
        {
            "name": "Icon Theme",
            "mode": "light",
            "icons": {
                "search_paths": [str(icons_dir)],
                "map": {"integer": "integer"},
            },
        },
        mode_default=LIGHT_DEFAULT,
        base_dir=tmp_path,
    )

    provider = FileIconProvider(theme)
    assert not provider.for_type(JsonType.INTEGER).isNull()


def test_search_path_order_prefers_first_directory(tmp_path, qapp):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    _write_png(first / "integer.png", "#ff0000")
    _write_png(second / "integer.png", "#0000ff")

    theme = parse_theme_mapping(
        {
            "name": "Path Order",
            "mode": "light",
            "icons": {
                "search_paths": [str(first), str(second)],
                "map": {"integer": "integer"},
            },
        },
        mode_default=LIGHT_DEFAULT,
        base_dir=tmp_path,
    )

    provider = FileIconProvider(theme)
    image = provider.for_type(JsonType.INTEGER).pixmap(8, 8).toImage()
    assert image.pixelColor(0, 0) == QColor("#ff0000")


def test_missing_icon_logs_warning_once(tmp_path, caplog, qapp):
    caplog.set_level("WARNING")

    theme = parse_theme_mapping(
        {
            "name": "Missing",
            "mode": "light",
            "icons": {
                "search_paths": [str(tmp_path)],
                "map": {"integer": "does-not-exist"},
            },
        },
        mode_default=LIGHT_DEFAULT,
        base_dir=tmp_path,
    )

    provider = FileIconProvider(theme)
    assert provider.for_type(JsonType.INTEGER).isNull()
    assert provider.for_type(JsonType.INTEGER).isNull()

    warnings = [r for r in caplog.records if "Missing icon asset" in r.message]
    assert len(warnings) == 1


def test_reload_rechecks_filesystem(tmp_path, qapp):
    icons_dir = tmp_path / "icons"
    icons_dir.mkdir()

    theme = parse_theme_mapping(
        {
            "name": "Reload",
            "mode": "light",
            "icons": {
                "search_paths": [str(icons_dir)],
                "map": {"integer": "integer"},
            },
        },
        mode_default=LIGHT_DEFAULT,
        base_dir=tmp_path,
    )

    provider = FileIconProvider(theme)

    assert provider.for_type(JsonType.INTEGER).isNull()

    _write_png(icons_dir / "integer.png", "#00ff00")
    provider.reload()
    assert not provider.for_type(JsonType.INTEGER).isNull()

    (icons_dir / "integer.png").unlink()
    provider.reload()
    assert provider.for_type(JsonType.INTEGER).isNull()
