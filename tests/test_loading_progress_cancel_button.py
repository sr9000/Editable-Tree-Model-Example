"""Tests for loading progress cancellation button wiring (Plan 3, Commit 3.2)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton

from app.loading.cancellation import CancellationToken
from app.loading.progress_dialog import LoadingProgressDialog
from app.main_window import MainWindow


def test_cancel_button_sets_token_and_disables(qtbot):
    dialog = LoadingProgressDialog(cancellable=True, delay_ms=0)
    qtbot.addWidget(dialog)

    token = CancellationToken()
    dialog.start("task-1", cancellation_token=token)
    qtbot.wait(20)
    QApplication.processEvents()

    button = dialog.findChildren(QPushButton)[0]
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

    assert token.is_cancelled
    assert not button.isEnabled()
    assert dialog._stage_label.text() == "Cancelling…"
    assert dialog.isVisible()

    dialog.finish("task-1")
    assert not dialog.isVisible()


def test_second_click_does_not_trigger_second_cancel_action(qtbot):
    dialog = LoadingProgressDialog(cancellable=True, delay_ms=0)
    qtbot.addWidget(dialog)

    token = CancellationToken()
    cancel_count = {"value": 0}

    def on_cancel() -> None:
        cancel_count["value"] += 1

    dialog.start("task-1", cancellation_token=token, on_cancel=on_cancel)
    qtbot.wait(20)

    button = dialog.findChildren(QPushButton)[0]
    button.click()
    button.click()

    assert token.is_cancelled
    assert cancel_count["value"] == 1

    dialog.finish("task-1")


def test_non_cancellable_dialog_has_no_cancel_button(qtbot):
    dialog = LoadingProgressDialog(cancellable=False)
    qtbot.addWidget(dialog)
    assert dialog.findChildren(QPushButton) == []


def test_coordinator_starts_cancellable_dialog_with_task_token(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    doc = tmp_path / "data.json"

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        monkeypatch.setattr(win._load_coordinator, "_start_parse_worker", lambda *args, **kwargs: None)
        task_id = win._load_coordinator.open_file_async(str(doc))
        assert task_id is not None

        task = win._load_coordinator._tasks[task_id]
        dialog = win._load_coordinator._progress_dialog
        assert dialog is not None
        assert dialog._cancellable is True
        assert dialog._cancel_token is task.token
    finally:
        if task_id is not None and task_id in win._load_coordinator._tasks:
            win._load_coordinator._finish_progress(task_id)
            win._load_coordinator._tasks.pop(task_id, None)
        win.close()
        win.deleteLater()
