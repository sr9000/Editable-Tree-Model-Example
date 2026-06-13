"""Delayed progress widget for loading operations.

The widget only appears when a task remains active for at least
``LOADING_PROGRESS_DELAY_MS`` milliseconds. Fast loads complete before
the widget shows, avoiding visual noise.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from settings import LOADING_PROGRESS_DELAY_MS


class LoadingProgressDialog(QWidget):
    """A delayed progress widget for loading operations.

    The widget uses a single-shot timer to delay showing. If the task
    completes before the timer fires, the widget never becomes visible.

    Parameters
    ----------
    parent : QWidget | None
        Parent widget.
    cancellable : bool
        If True, show a Cancel button. In Plan 2 this is always False.
    delay_ms : int | None
        Override for the show delay. Defaults to LOADING_PROGRESS_DELAY_MS.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        cancellable: bool = False,
        delay_ms: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Loading")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)

        self._cancellable = cancellable
        self._delay_ms = delay_ms if delay_ms is not None else LOADING_PROGRESS_DELAY_MS
        self._active_task_id: str | None = None
        self._was_shown = False

        # Build UI
        layout = QVBoxLayout(self)
        self._stage_label = QLabel("Loading...")
        layout.addWidget(self._stage_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)  # Indeterminate
        layout.addWidget(self._progress_bar)

        if cancellable:
            self._cancel_button = QPushButton("Cancel")
            layout.addWidget(self._cancel_button)
        else:
            self._cancel_button = None

        # Single-shot timer for delayed show
        self._show_timer = QTimer(self)
        self._show_timer.setSingleShot(True)
        self._show_timer.timeout.connect(self._on_show_timer_timeout)

        # Start hidden
        self.hide()

    @property
    def was_shown(self) -> bool:
        """True if the widget was ever shown during the current task."""
        return self._was_shown

    def start(self, task_id: str) -> None:
        """Start tracking a task.

        Arms the show timer. If the task completes before the timer fires,
        the widget never becomes visible.
        """
        self._active_task_id = task_id
        self._was_shown = False
        self._stage_label.setText("Loading...")
        self._progress_bar.setRange(0, 0)
        self.hide()
        self._show_timer.start(self._delay_ms)

    def set_stage(self, stage: str) -> None:
        """Update the stage text displayed to the user."""
        self._stage_label.setText(stage)

    def set_progress(self, done: int, total: int) -> None:
        """Update the progress bar.

        If total is 0, the bar is indeterminate. Otherwise it shows
        done/total.
        """
        if total <= 0:
            self._progress_bar.setRange(0, 0)
        else:
            self._progress_bar.setRange(0, total)
            self._progress_bar.setValue(done)

    def finish(self, task_id: str) -> None:
        """Mark a task as finished.

        Stops the show timer and hides the widget. If the task_id does
        not match the active task, this is a no-op.
        """
        if task_id != self._active_task_id:
            return
        self._show_timer.stop()
        self._active_task_id = None
        self.hide()

    def error(self, task_id: str) -> None:
        """Mark a task as failed.

        Stops the show timer and hides the widget. If the task_id does
        not match the active task, this is a no-op.
        """
        if task_id != self._active_task_id:
            return
        self._show_timer.stop()
        self._active_task_id = None
        self.hide()

    def _on_show_timer_timeout(self) -> None:
        """Show the widget when the timer fires and a task is still active."""
        if self._active_task_id is not None:
            self._was_shown = True
            self.show()
            self.raise_()
            self.activateWindow()


__all__ = ["LoadingProgressDialog"]
