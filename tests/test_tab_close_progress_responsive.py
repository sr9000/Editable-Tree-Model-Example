"""Responsiveness tests for large tab close progress (Plan 4, Commit 4.4)."""

from __future__ import annotations

import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import settings
from app.main_window import MainWindow


def test_large_close_processes_events_while_progress_visible(qtbot, monkeypatch):
    monkeypatch.setattr(settings, "CLOSE_PROGRESS_DELAY_MS", 10)

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win.create_new_file()
        assert win.tabWidget.count() == 1
        tab = win.tabWidget.widget(0)
        tab.io.file_path = "/tmp/close-progress-responsive.json"

        def slow_expanded_paths_iter():
            for i in range(3000):
                if i % 64 == 0:
                    time.sleep(0.001)
                yield (i,)

        monkeypatch.setattr(tab.editing.move, "iter_expanded_paths", slow_expanded_paths_iter)

        tick_count = 0

        def on_tick() -> None:
            nonlocal tick_count
            tick_count += 1

        timer = QTimer(win)
        timer.setInterval(5)
        timer.timeout.connect(on_tick)
        timer.start()

        QTimer.singleShot(0, lambda: win.close_tab(0))
        qtbot.waitUntil(lambda: win.tabWidget.count() == 0, timeout=4000)

        dialog = win._tab_lifecycle._close_progress_dialog
        assert dialog is not None
        assert dialog.was_shown
        assert not dialog.isVisible()
        assert tick_count > 0
    finally:
        win.close()
        win.deleteLater()
