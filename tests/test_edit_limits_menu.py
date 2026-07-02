from __future__ import annotations

from PySide6.QtCore import QSettings

from app.main_window import MainWindow
from settings import APPLICATION_ID
from state.edit_limits import (
    get_attach_file_warning_limit_bytes,
    get_base64_inference_min_length_chars,
    get_binary_edit_warning_limit_bytes,
    get_multiline_edit_warning_limit_chars,
    get_string_edit_warning_limit_chars,
    set_attach_file_warning_limit_bytes,
    set_base64_inference_min_length_chars,
    set_binary_edit_warning_limit_bytes,
    set_multiline_edit_warning_limit_chars,
    set_string_edit_warning_limit_chars,
)


def _clear_limits_settings() -> None:
    settings = QSettings(APPLICATION_ID, "app")
    settings.remove("edit_limits")


def test_file_menu_limit_actions_persist_updates(qtbot, monkeypatch):
    _clear_limits_settings()
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)

    picks = iter([111, 222, 333, 444, 555])

    def _pick(*_args, **_kwargs):
        return next(picks), True

    monkeypatch.setattr("app.app_settings.QInputDialog.getInt", _pick)

    win._app_settings.limit_string_action.trigger()
    win._app_settings.limit_multiline_action.trigger()
    win._app_settings.limit_binary_action.trigger()
    win._app_settings.limit_attach_action.trigger()
    win._app_settings.limit_base64_min_length_action.trigger()

    assert get_string_edit_warning_limit_chars() == 111
    assert get_multiline_edit_warning_limit_chars() == 222
    assert get_binary_edit_warning_limit_bytes() == 333
    assert get_attach_file_warning_limit_bytes() == 444
    assert get_base64_inference_min_length_chars() == 555


def test_file_menu_limit_actions_restore_after_restart(qtbot):
    _clear_limits_settings()
    set_string_edit_warning_limit_chars(1001)
    set_multiline_edit_warning_limit_chars(2002)
    set_binary_edit_warning_limit_bytes(3003)
    set_attach_file_warning_limit_bytes(4004)
    set_base64_inference_min_length_chars(5005)

    first = MainWindow(yaml_filename="")
    qtbot.addWidget(first)
    first._app_settings.refresh_edit_limits_menu_entries()
    assert "1.00K" in first._app_settings.limit_string_action.text()
    assert "2.00K" in first._app_settings.limit_multiline_action.text()
    assert "KiB" in first._app_settings.limit_binary_action.text()
    assert "KiB" in first._app_settings.limit_attach_action.text()
    assert "5.00K" in first._app_settings.limit_base64_min_length_action.text()
    first.close()
    first.deleteLater()

    second = MainWindow(yaml_filename="")
    qtbot.addWidget(second)
    second._app_settings.refresh_edit_limits_menu_entries()
    assert "1.00K" in second._app_settings.limit_string_action.text()
    assert "2.00K" in second._app_settings.limit_multiline_action.text()
    assert "KiB" in second._app_settings.limit_binary_action.text()
    assert "KiB" in second._app_settings.limit_attach_action.text()
    assert "5.00K" in second._app_settings.limit_base64_min_length_action.text()
