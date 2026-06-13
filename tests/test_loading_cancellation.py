"""Tests for loading cancellation primitives (Plan 3, Commit 3.1)."""

from __future__ import annotations

import threading
import time

import pytest

from app.loading.cancellation import CancellationToken, CancelledError


def test_token_starts_not_cancelled() -> None:
    token = CancellationToken()
    assert not token.is_cancelled
    token.raise_if_cancelled()


def test_cancel_is_idempotent() -> None:
    token = CancellationToken()
    token.cancel()
    token.cancel()
    assert token.is_cancelled


def test_raise_if_cancelled_raises_after_cancel() -> None:
    token = CancellationToken()
    token.cancel()
    with pytest.raises(CancelledError):
        token.raise_if_cancelled()


def test_cross_thread_observer_sees_cancellation() -> None:
    token = CancellationToken()
    observer_saw_cancel = threading.Event()

    def observe() -> None:
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            if token.is_cancelled:
                observer_saw_cancel.set()
                return
            time.sleep(0.001)

    def trigger_cancel() -> None:
        time.sleep(0.01)
        token.cancel()

    observer = threading.Thread(target=observe)
    canceller = threading.Thread(target=trigger_cancel)
    observer.start()
    canceller.start()
    observer.join(timeout=2.0)
    canceller.join(timeout=2.0)

    assert observer_saw_cancel.is_set()
    assert token.is_cancelled
