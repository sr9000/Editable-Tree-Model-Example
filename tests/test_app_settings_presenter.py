"""Contract test for ``AppSettingsPresenter`` (kill-gods Phase 3.2)."""

from __future__ import annotations

from PySide6.QtCore import QSettings

from app.app_settings import AppSettingsPresenter
from app.main_window import MainWindow
from settings import APPLICATION_ID
from state.edit_limits import get_string_edit_warning_limit_chars, set_string_edit_warning_limit_chars


def _clear() -> None:
    QSettings(APPLICATION_ID, "app").remove("edit_limits")


def test_main_window_exposes_presenter(qtbot):
    _clear()
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        assert isinstance(win._app_settings, AppSettingsPresenter)
        # Forwarding shims point at presenter-owned objects.
        assert win._limits_menu is win._app_settings.limits_menu
        assert win._limit_string_action is win._app_settings.limit_string_action
        assert win._secret_prefixes_action is win._app_settings.secret_prefixes_action
    finally:
        win.close()
        win.deleteLater()


def test_presenter_refresh_updates_action_label(qtbot):
    _clear()
    set_string_edit_warning_limit_chars(4096)
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win._refresh_edit_limits_menu_entries()
        assert get_string_edit_warning_limit_chars() == 4096
        assert "chars" in win._limit_string_action.text()
    finally:
        win.close()
        win.deleteLater()
