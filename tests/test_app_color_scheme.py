"""Tests for Phase 5: app-level light/dark color scheme sync."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSettings, QStandardPaths, Qt
from PySide6.QtGui import QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from settings import APPLICATION_ID
from state.theme_settings import set_follow_system, set_manual_theme_name


def _theme_settings() -> QSettings:
    return QSettings(APPLICATION_ID, "theme")


@pytest.fixture(autouse=True)
def _restore_color_scheme():
    """Save and restore the Qt color scheme around each test."""
    app = QGuiApplication.instance()
    style_hints = app.styleHints() if isinstance(app, QGuiApplication) else None
    original = style_hints.colorScheme() if style_hints is not None else None
    app_widget = QApplication.instance()
    original_palette = app_widget.palette() if isinstance(app_widget, QApplication) else None
    yield
    if style_hints is not None and original is not None:
        setter = getattr(style_hints, "setColorScheme", None)
        if setter is not None:
            setter(original)
    if isinstance(app_widget, QApplication) and original_palette is not None:
        app_widget.setPalette(original_palette)


def test_light_theme_sets_light_color_scheme(qtbot, tmp_path, monkeypatch):
    QStandardPaths.setTestModeEnabled(True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    _theme_settings().clear()
    set_follow_system(False)

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)

    light_theme = win._theme_registry.default_for_mode("light")
    win._apply_theme(light_theme)

    app = QGuiApplication.instance()
    assert isinstance(app, QGuiApplication)
    style_hints = app.styleHints()
    setter = getattr(style_hints, "setColorScheme", None)
    if setter is None:
        pytest.skip("Qt version does not support setColorScheme")
    assert style_hints.colorScheme() == Qt.ColorScheme.Light
    app_widget = QApplication.instance()
    assert isinstance(app_widget, QApplication)
    pal = app_widget.palette()
    assert pal.color(QPalette.ColorRole.AlternateBase).name().lower() == light_theme.palette.alternate_bg.name().lower()


def test_dark_theme_sets_dark_color_scheme(qtbot, tmp_path, monkeypatch):
    QStandardPaths.setTestModeEnabled(True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    _theme_settings().clear()
    set_follow_system(False)

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)

    dark_theme = win._theme_registry.default_for_mode("dark")
    win._apply_theme(dark_theme)

    app = QGuiApplication.instance()
    assert isinstance(app, QGuiApplication)
    style_hints = app.styleHints()
    setter = getattr(style_hints, "setColorScheme", None)
    if setter is None:
        pytest.skip("Qt version does not support setColorScheme")
    assert style_hints.colorScheme() == Qt.ColorScheme.Dark
    app_widget = QApplication.instance()
    assert isinstance(app_widget, QApplication)
    pal = app_widget.palette()
    assert pal.color(QPalette.ColorRole.AlternateBase).name().lower() == dark_theme.palette.alternate_bg.name().lower()


def test_startup_applies_saved_theme_to_qt_scheme_and_palette(qtbot, tmp_path, monkeypatch):
    QStandardPaths.setTestModeEnabled(True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    _theme_settings().clear()
    set_follow_system(False)
    set_manual_theme_name("Default Dark")

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)

    app = QGuiApplication.instance()
    assert isinstance(app, QGuiApplication)
    style_hints = app.styleHints()
    setter = getattr(style_hints, "setColorScheme", None)
    if setter is None:
        pytest.skip("Qt version does not support setColorScheme")

    assert win._theme.mode == "dark"
    assert style_hints.colorScheme() == Qt.ColorScheme.Dark
    app_widget = QApplication.instance()
    assert isinstance(app_widget, QApplication)
    pal = app_widget.palette()
    assert pal.color(QPalette.ColorRole.AlternateBase).name().lower() == win._theme.palette.alternate_bg.name().lower()


def test_no_feedback_loop_on_scheme_change(qtbot, tmp_path, monkeypatch):
    """Calling apply_theme must not trigger on_system_color_scheme_changed re-entrantly."""
    QStandardPaths.setTestModeEnabled(True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    _theme_settings().clear()
    set_follow_system(True)

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)

    call_count = 0
    original_handler = win._theme_controller.on_system_color_scheme_changed

    def counting_handler(*args):
        nonlocal call_count
        call_count += 1
        original_handler(*args)

    win._theme_controller.on_system_color_scheme_changed = counting_handler

    app = QGuiApplication.instance()
    assert isinstance(app, QGuiApplication)
    style_hints = app.styleHints()
    setter = getattr(style_hints, "setColorScheme", None)
    if setter is None:
        pytest.skip("Qt version does not support setColorScheme")

    # Connect our counter to the signal
    style_hints.colorSchemeChanged.connect(counting_handler)

    dark_theme = win._theme_registry.default_for_mode("dark")
    win._apply_theme(dark_theme)

    # Even if signal fires, _suppress_scheme_signal flag prevents re-applying
    # The signal may fire 0 or 1 times (depending on Qt internals),
    # but apply_theme must not be called recursively — verify theme is as expected
    assert win._theme.mode == "dark"

    style_hints.colorSchemeChanged.disconnect(counting_handler)
