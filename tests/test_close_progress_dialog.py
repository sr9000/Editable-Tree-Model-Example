"""Tests for close-progress dialog reuse (Plan 4, Commit 4.2)."""

from __future__ import annotations

from PySide6.QtWidgets import QPushButton

from app.loading.progress_dialog import LoadingProgressDialog
from settings import CLOSE_PROGRESS_DELAY_MS


def test_fast_close_completes_before_delay_and_never_shows(qtbot):
    dialog = LoadingProgressDialog(cancellable=False, delay_ms=CLOSE_PROGRESS_DELAY_MS)
    qtbot.addWidget(dialog)

    dialog.start("close-task")
    dialog.set_stage("closing tab")
    dialog.finish("close-task")

    # Even if we wait a little, the stopped timer must not show the widget.
    qtbot.wait(50)
    assert not dialog.was_shown
    assert not dialog.isVisible()


def test_slow_close_shows_once_after_delay_then_hides_on_finish(qtbot):
    dialog = LoadingProgressDialog(cancellable=False, delay_ms=CLOSE_PROGRESS_DELAY_MS)
    qtbot.addWidget(dialog)

    show_count = 0
    hide_count = 0

    def on_shown() -> None:
        nonlocal show_count
        show_count += 1

    def on_hidden() -> None:
        nonlocal hide_count
        hide_count += 1

    original_show_event = dialog.showEvent
    original_hide_event = dialog.hideEvent

    def wrapped_show_event(event):
        on_shown()
        original_show_event(event)

    def wrapped_hide_event(event):
        on_hidden()
        original_hide_event(event)

    dialog.showEvent = wrapped_show_event  # type: ignore[method-assign]
    dialog.hideEvent = wrapped_hide_event  # type: ignore[method-assign]

    dialog.start("close-task")
    dialog.set_stage("closing tab")

    qtbot.wait(CLOSE_PROGRESS_DELAY_MS + 150)
    assert dialog.was_shown
    assert dialog.isVisible()

    dialog.finish("close-task")
    qtbot.wait(20)

    assert not dialog.isVisible()
    assert show_count == 1
    assert hide_count >= 1


def test_close_mode_dialog_has_no_cancel_button(qtbot):
    dialog = LoadingProgressDialog(cancellable=False, delay_ms=CLOSE_PROGRESS_DELAY_MS)
    qtbot.addWidget(dialog)

    assert dialog.findChildren(QPushButton) == []
