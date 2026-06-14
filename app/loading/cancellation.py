"""Thread-safe cooperative cancellation primitives for loading flows."""

from __future__ import annotations

import threading


class CancelledError(RuntimeError):
    """Raised when cooperative cancellation has been requested."""


class CancellationToken:
    """A thread-safe cancellation token.

    The token uses a standard :class:`threading.Event` so producer and
    consumer code can coordinate cancellation across threads without any Qt
    synchronization primitives.
    """

    __slots__ = ("_cancelled",)

    def __init__(self) -> None:
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        """Request cancellation.

        The operation is idempotent; repeated calls keep the token cancelled.
        """
        self._cancelled.set()

    @property
    def is_cancelled(self) -> bool:
        """Return ``True`` once cancellation has been requested."""
        return self._cancelled.is_set()

    def raise_if_cancelled(self) -> None:
        """Raise :class:`CancelledError` if cancellation has been requested."""
        if self.is_cancelled:
            raise CancelledError("Operation was cancelled")


__all__ = ["CancellationToken", "CancelledError"]
