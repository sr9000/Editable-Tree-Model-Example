"""Tests for LoadingProgressDialog (Commit 2.2)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QPushButton

from app.loading.progress_dialog import LoadingProgressDialog


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestLoadingProgressDialogFastTask:
    """Tests for tasks that complete before the delay."""

    def test_fast_task_never_shows_widget(self, qtbot):
        """A task that finishes before the delay never shows the widget."""
        dialog = LoadingProgressDialog(delay_ms=100)
        qtbot.addWidget(dialog)

        dialog.start("task-1")
        assert not dialog.isVisible()
        assert not dialog.was_shown

        # Finish before the timer fires
        dialog.finish("task-1")
        assert not dialog.isVisible()
        assert not dialog.was_shown

    def test_fast_task_error_never_shows_widget(self, qtbot):
        """A task that errors before the delay never shows the widget."""
        dialog = LoadingProgressDialog(delay_ms=100)
        qtbot.addWidget(dialog)

        dialog.start("task-1")
        assert not dialog.isVisible()

        # Error before the timer fires
        dialog.error("task-1")
        assert not dialog.isVisible()
        assert not dialog.was_shown


class TestLoadingProgressDialogSlowTask:
    """Tests for tasks that take longer than the delay."""

    def test_slow_task_shows_widget_after_delay(self, qtbot):
        """A task that takes longer than the delay shows the widget."""
        dialog = LoadingProgressDialog(delay_ms=50)
        qtbot.addWidget(dialog)

        dialog.start("task-1")
        assert not dialog.isVisible()

        # Wait for the timer to fire
        qtbot.wait(100)
        QApplication.processEvents()

        assert dialog.isVisible()
        assert dialog.was_shown

        # Finish hides the widget
        dialog.finish("task-1")
        assert not dialog.isVisible()

    def test_slow_task_error_hides_widget(self, qtbot):
        """A task that errors after showing hides the widget."""
        dialog = LoadingProgressDialog(delay_ms=50)
        qtbot.addWidget(dialog)

        dialog.start("task-1")
        qtbot.wait(100)
        QApplication.processEvents()

        assert dialog.isVisible()

        # Error hides the widget
        dialog.error("task-1")
        assert not dialog.isVisible()


class TestLoadingProgressDialogCancelButton:
    """Tests for the Cancel button presence."""

    def test_no_cancel_button_when_not_cancellable(self, qtbot):
        """No Cancel button exists when cancellable=False."""
        dialog = LoadingProgressDialog(cancellable=False)
        qtbot.addWidget(dialog)

        # Find all QPushButton children
        buttons = dialog.findChildren(QPushButton)
        assert len(buttons) == 0

    def test_cancel_button_exists_when_cancellable(self, qtbot):
        """A Cancel button exists when cancellable=True."""
        dialog = LoadingProgressDialog(cancellable=True)
        qtbot.addWidget(dialog)

        # Find all QPushButton children
        buttons = dialog.findChildren(QPushButton)
        assert len(buttons) == 1
        assert buttons[0].text() == "Cancel"


class TestLoadingProgressDialogStageAndProgress:
    """Tests for stage text and progress bar updates."""

    def test_set_stage_updates_label(self, qtbot):
        """set_stage() updates the displayed stage text."""
        dialog = LoadingProgressDialog(delay_ms=50)
        qtbot.addWidget(dialog)

        dialog.start("task-1")
        dialog.set_stage("reading/parsing file")

        # Wait for widget to show
        qtbot.wait(100)
        QApplication.processEvents()

        assert dialog._stage_label.text() == "reading/parsing file"

    def test_set_progress_indeterminate(self, qtbot):
        """set_progress(0, 0) sets indeterminate progress."""
        dialog = LoadingProgressDialog()
        qtbot.addWidget(dialog)

        dialog.start("task-1")
        dialog.set_progress(0, 0)

        assert dialog._progress_bar.maximum() == 0

    def test_set_progress_determinate(self, qtbot):
        """set_progress(done, total) sets determinate progress."""
        dialog = LoadingProgressDialog()
        qtbot.addWidget(dialog)

        dialog.start("task-1")
        dialog.set_progress(5, 10)

        assert dialog._progress_bar.maximum() == 10
        assert dialog._progress_bar.value() == 5


class TestLoadingProgressDialogDetailRefresh:
    """Tests for detail-label rendering and throttling."""

    def test_detail_updates_only_on_refresh_tick(self, qtbot):
        """Many detail updates are collapsed into timer-driven repaint."""
        dialog = LoadingProgressDialog(delay_ms=10, detail_refresh_ms=40)
        qtbot.addWidget(dialog)

        dialog.start("task-1")
        dialog.set_detail(1, "/a")
        dialog.set_detail(50, "/b")
        dialog.set_detail(1234, "/orders/1000/price")

        # No repaint before the refresh tick.
        qtbot.wait(10)
        assert dialog._detail_label.text() == ""

        # One refresh tick applies the latest values.
        qtbot.wait(60)
        assert "1,234" in dialog._detail_label.text()
        assert "/orders/1000/price" in dialog._detail_label.text()

    def test_detail_resets_on_start_and_freezes_after_finish(self, qtbot):
        """Detail text resets when task starts and no longer updates after finish."""
        dialog = LoadingProgressDialog(delay_ms=10, detail_refresh_ms=25)
        qtbot.addWidget(dialog)

        dialog.start("task-1")
        dialog.set_detail(42, "/x")
        qtbot.wait(40)
        assert "/x" in dialog._detail_label.text()

        dialog.finish("task-1")
        frozen = dialog._detail_label.text()

        dialog.set_detail(999, "/y")
        qtbot.wait(40)
        assert dialog._detail_label.text() == frozen

        dialog.start("task-2")
        assert dialog._detail_label.text() == ""


class TestLoadingProgressDialogTaskIdMatching:
    """Tests for task ID matching on finish/error."""

    def test_finish_with_wrong_task_id_is_noop(self, qtbot):
        """finish() with a non-matching task_id does not hide the widget."""
        dialog = LoadingProgressDialog(delay_ms=50)
        qtbot.addWidget(dialog)

        dialog.start("task-1")
        qtbot.wait(100)
        QApplication.processEvents()

        assert dialog.isVisible()

        # Finish with wrong task_id
        dialog.finish("task-2")
        assert dialog.isVisible()

        # Finish with correct task_id
        dialog.finish("task-1")
        assert not dialog.isVisible()

    def test_error_with_wrong_task_id_is_noop(self, qtbot):
        """error() with a non-matching task_id does not hide the widget."""
        dialog = LoadingProgressDialog(delay_ms=50)
        qtbot.addWidget(dialog)

        dialog.start("task-1")
        qtbot.wait(100)
        QApplication.processEvents()

        assert dialog.isVisible()

        # Error with wrong task_id
        dialog.error("task-2")
        assert dialog.isVisible()

        # Error with correct task_id
        dialog.error("task-1")
        assert not dialog.isVisible()
