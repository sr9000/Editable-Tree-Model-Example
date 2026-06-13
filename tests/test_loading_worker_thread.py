"""Tests for ParseWorker thread (Commit 2.3)."""

from __future__ import annotations

import time
from typing import Any

import pytest
from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import QApplication

from app.loading.worker import ParseWorker, start_parse_worker


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _slow_parser(delay_ms: int, result: tuple[Any, str]):
    """Create a parser that delays for the specified milliseconds."""

    def parser(path: str) -> tuple[Any, str]:
        time.sleep(delay_ms / 1000.0)
        return result

    return parser


def _failing_parser(error_msg: str):
    """Create a parser that raises an exception."""

    def parser(path: str) -> tuple[Any, str]:
        raise ValueError(error_msg)

    return parser


class TestParseWorkerSuccess:
    """Tests for successful parsing."""

    def test_worker_emits_finished_with_result(self, qtbot):
        """Worker emits finished signal with parse result."""
        expected_result = ({"key": "value"}, "json")
        parser = _slow_parser(10, expected_result)

        thread, worker = start_parse_worker("/fake/path.json", parser=parser)

        results = []
        worker.finished.connect(lambda r: results.append(r))

        # Wait for thread to finish
        thread.wait(2000)

        assert len(results) == 1
        assert results[0] == expected_result

        # Cleanup
        thread.deleteLater()
        worker.deleteLater()

    def test_worker_emits_stage_signals(self, qtbot):
        """Worker emits stage signals during parsing."""
        expected_result = ({"key": "value"}, "json")
        parser = _slow_parser(10, expected_result)

        thread, worker = start_parse_worker("/fake/path.json", parser=parser)

        stages = []
        worker.stage.connect(lambda s: stages.append(s))

        thread.wait(2000)

        assert "reading/parsing file" in stages
        assert "decoding number affixes" in stages

        thread.deleteLater()
        worker.deleteLater()


class TestParseWorkerFailure:
    """Tests for failed parsing."""

    def test_worker_emits_failed_on_exception(self, qtbot):
        """Worker emits failed signal when parser raises."""
        parser = _failing_parser("Test error message")

        thread, worker = start_parse_worker("/fake/path.json", parser=parser)

        errors = []
        worker.failed.connect(lambda e: errors.append(e))

        thread.wait(2000)

        assert len(errors) == 1
        error_type, error_msg = errors[0]
        assert error_type == "ValueError"
        assert "Test error message" in error_msg

        thread.deleteLater()
        worker.deleteLater()


class TestParseWorkerEventLoop:
    """Tests for GUI event loop responsiveness during parsing."""

    def test_event_loop_processes_events_during_slow_parse(self, qtbot):
        """GUI event loop processes timers during slow parsing."""
        # Use a slow parser that takes 200ms
        expected_result = ({"key": "value"}, "json")
        parser = _slow_parser(200, expected_result)

        # Track timer firings
        timer_count = [0]

        def on_timer():
            timer_count[0] += 1

        # Create a timer that fires every 50ms
        timer = QTimer()
        timer.timeout.connect(on_timer)
        timer.start(50)

        thread, worker = start_parse_worker("/fake/path.json", parser=parser)

        # Use qtbot.wait which processes events, unlike thread.wait
        qtbot.wait(300)

        timer.stop()

        # Timer should have fired at least twice during the 200ms parse
        assert timer_count[0] >= 2, f"Timer only fired {timer_count[0]} times"

        # Ensure thread finished
        thread.wait(1000)

        thread.deleteLater()
        worker.deleteLater()


class TestParseWorkerThreadCleanup:
    """Tests for thread cleanup after parsing."""

    def test_thread_quits_after_success(self, qtbot):
        """Thread quits after successful parsing."""
        expected_result = ({"key": "value"}, "json")
        parser = _slow_parser(10, expected_result)

        thread, worker = start_parse_worker("/fake/path.json", parser=parser)

        # Use qtbot.wait to process events so queued signals are delivered
        qtbot.wait(100)

        assert not thread.isRunning()

        thread.deleteLater()
        worker.deleteLater()

    def test_thread_quits_after_failure(self, qtbot):
        """Thread quits after failed parsing."""
        parser = _failing_parser("Test error")

        thread, worker = start_parse_worker("/fake/path.json", parser=parser)

        # Use qtbot.wait to process events so queued signals are delivered
        qtbot.wait(100)

        assert not thread.isRunning()

        thread.deleteLater()
        worker.deleteLater()
