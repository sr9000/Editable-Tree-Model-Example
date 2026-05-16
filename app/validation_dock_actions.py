"""app/validation_dock_actions.py — helpers for the validation dock toolbar.

Currently contains the ``_Debouncer`` utility used by the auto-rescan
feature and available to tests.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, QTimer


class _Debouncer(QObject):
    """QTimer-based 250 ms *trailing* debounce.

    Usage::

        debouncer = _Debouncer(parent)
        debouncer.schedule(some_callable)   # (re-)arms the 250 ms timer
        debouncer.cancel()                  # stops a pending invocation

    Rapid calls to ``schedule`` reset the timer each time, so the callable is
    invoked only once — 250 ms after the *last* call in a burst.
    """

    #: Delay in milliseconds before the scheduled callable is invoked.
    DELAY_MS = 250

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._fn: Callable[[], None] | None = None
        self._timer.timeout.connect(self._fire)

    def schedule(self, fn: Callable[[], None]) -> None:
        """(Re-)arm the debounce timer to call *fn* after ``DELAY_MS`` ms."""
        self._fn = fn
        self._timer.start(self.DELAY_MS)

    def cancel(self) -> None:
        """Stop a pending invocation without calling the callable."""
        self._timer.stop()
        self._fn = None

    def _fire(self) -> None:
        if self._fn is not None:
            fn = self._fn
            self._fn = None
            fn()
