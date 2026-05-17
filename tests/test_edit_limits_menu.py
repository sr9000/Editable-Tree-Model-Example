from __future__ import annotations

from PySide6.QtCore import QSettings

from app.main_window import MainWindow
from settings import APPLICATION_ID
from state.edit_limits import (
    get_attach_file_warning_limit_bytes,
    get_binary_edit_warning_limit_bytes,
    get_multiline_edit_warning_limit_chars,
    get_string_edit_warning_limit_chars,
    set_attach_file_warning_limit_bytes,
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

    picks = iter([111, 222, 333, 444])

    def _pick(*_args, **_kwargs):
        return next(picks), True

    monkeypatch.setattr("app.main_window.QInputDialog.getInt", _pick)

    win._limit_string_action.trigger()
    win._limit_multiline_action.trigger()
    win._limit_binary_action.trigger()
    win._limit_attach_action.trigger()

    assert get_string_edit_warning_limit_chars() == 111
    assert get_multiline_edit_warning_limit_chars() == 222
    assert get_binary_edit_warning_limit_bytes() == 333
    assert get_attach_file_warning_limit_bytes() == 444


def test_file_menu_limit_actions_restore_after_restart(qtbot):
    _clear_limits_settings()
    set_string_edit_warning_limit_chars(1001)
    set_multiline_edit_warning_limit_chars(2002)
    set_binary_edit_warning_limit_bytes(3003)
    set_attach_file_warning_limit_bytes(4004)

    first = MainWindow(yaml_filename="")
    qtbot.addWidget(first)
    first._refresh_edit_limits_menu_entries()
    assert "1,001" in first._limit_string_action.text()
    assert "2,002" in first._limit_multiline_action.text()
    assert "3,003" in first._limit_binary_action.text()
    assert "4,004" in first._limit_attach_action.text()
    first.close()
    first.deleteLater()

    second = MainWindow(yaml_filename="")
    qtbot.addWidget(second)
    second._refresh_edit_limits_menu_entries()
    assert "1,001" in second._limit_string_action.text()
    assert "2,002" in second._limit_multiline_action.text()
    assert "3,003" in second._limit_binary_action.text()
    assert "4,004" in second._limit_attach_action.text()
