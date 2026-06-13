"""Tests for tab-close progress ownership (Plan 4, Commit 4.3)."""

from __future__ import annotations

import time

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import settings
import state.view_state as view_state
from app.main_window import MainWindow
from documents.tab import JsonTab


def test_normal_close_finishes_without_showing_progress(qtbot, monkeypatch):
    monkeypatch.setattr(settings, "CLOSE_PROGRESS_DELAY_MS", 200)

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win.create_new_file()
        assert win.tabWidget.count() == 1

        win.close_tab(0)

        dialog = win._tab_lifecycle._close_progress_dialog
        assert dialog is not None
        assert not dialog.was_shown
        assert not dialog.isVisible()
        assert win.tabWidget.count() == 0
    finally:
        win.close()
        win.deleteLater()


def test_slow_close_shows_progress_with_stage_text(qtbot, monkeypatch):
    monkeypatch.setattr(settings, "CLOSE_PROGRESS_DELAY_MS", 20)

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win.create_new_file()
        assert win.tabWidget.count() == 1
        tab = win.tabWidget.widget(0)

        original_root_data = tab.root_data

        def slow_root_data():
            end = time.monotonic() + 0.15
            while time.monotonic() < end:
                QApplication.processEvents()
                time.sleep(0.005)
            return original_root_data()

        monkeypatch.setattr(tab, "root_data", slow_root_data)

        observed_stages: list[str] = []
        original_set_stage = win._tab_lifecycle._set_close_stage

        def record_stage(dialog, stage: str) -> None:
            observed_stages.append(stage)
            original_set_stage(dialog, stage)

        monkeypatch.setattr(win._tab_lifecycle, "_set_close_stage", record_stage)

        QTimer.singleShot(0, lambda: win.close_tab(0))
        qtbot.waitUntil(lambda: win.tabWidget.count() == 0, timeout=2000)

        dialog = win._tab_lifecycle._close_progress_dialog
        assert dialog is not None
        assert dialog.was_shown
        assert "snapshot" in observed_stages
        assert "saving view state" in observed_stages
        assert "removing tab" in observed_stages
        assert "destroying tab" in observed_stages
        assert not dialog.isVisible()
    finally:
        win.close()
        win.deleteLater()


def test_close_error_hides_progress_and_restores_cursor(qtbot, monkeypatch):
    monkeypatch.setattr(settings, "CLOSE_PROGRESS_DELAY_MS", 0)

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win.create_new_file()
        assert win.tabWidget.count() == 1

        original_save = view_state.save

        def boom(_tab):
            raise RuntimeError("close failed")

        monkeypatch.setattr(view_state, "save", boom)

        with pytest.raises(RuntimeError, match="close failed"):
            win.close_tab(0)

        dialog = win._tab_lifecycle._close_progress_dialog
        assert dialog is not None
        assert not dialog.isVisible()
        assert QApplication.overrideCursor() is None
    finally:
        monkeypatch.setattr(view_state, "save", original_save)
        while QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
        win.close()
        win.deleteLater()


def test_reopen_preserves_snapshot_for_normal_size_tab(qtbot, monkeypatch):
    monkeypatch.setattr(settings, "CLOSE_PROGRESS_DELAY_MS", 0)

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    monkeypatch.setattr(win, "_confirm_close", lambda _widget: True)
    try:
        tab = win._add_tab(data={"alpha": 1, "beta": {"x": True}})
        assert isinstance(tab, JsonTab)
        assert win.tabWidget.count() == 1

        win.close_tab(0)
        assert win.tabWidget.count() == 0

        win.reopen_closed_tab()
        assert win.tabWidget.count() == 1

        reopened = win._current_tab()
        assert isinstance(reopened, JsonTab)
        assert reopened.model.root_item.to_json() == {"alpha": 1, "beta": {"x": True}}

        dialog = win._tab_lifecycle._close_progress_dialog
        assert dialog is not None
        assert not dialog.isVisible()
        assert QApplication.overrideCursor() is None
    finally:
        for i in range(win.tabWidget.count()):
            maybe_tab = win.tabWidget.widget(i)
            if isinstance(maybe_tab, JsonTab):
                maybe_tab.undo_stack.setClean()
        while win.tabWidget.count() > 0:
            win.close_tab(0)
        while QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
        win.close()
        win.deleteLater()


def test_repeated_close_reopen_cycles_leave_no_orphan_progress(qtbot, monkeypatch):
    monkeypatch.setattr(settings, "CLOSE_PROGRESS_DELAY_MS", 0)

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    monkeypatch.setattr(win, "_confirm_close", lambda _widget: True)
    try:
        tab = win._add_tab(data={"seed": 1})
        assert isinstance(tab, JsonTab)
        assert win.tabWidget.count() == 1

        for _ in range(3):
            win.close_tab(0)
            assert win.tabWidget.count() == 0
            win.reopen_closed_tab()
            assert win.tabWidget.count() == 1

            dialog = win._tab_lifecycle._close_progress_dialog
            assert dialog is not None
            assert not dialog.isVisible()
            assert QApplication.overrideCursor() is None
    finally:
        for i in range(win.tabWidget.count()):
            maybe_tab = win.tabWidget.widget(i)
            if isinstance(maybe_tab, JsonTab):
                maybe_tab.undo_stack.setClean()
        while win.tabWidget.count() > 0:
            win.close_tab(0)
        while QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
        win.close()
        win.deleteLater()
