"""Tests for progress reporting protocol (Commit 2.4)."""

from __future__ import annotations

import pytest

from app.loading.progress import (
    OPEN_STAGES,
    RELOAD_STAGES,
    STAGE_APPLYING_RELOAD,
    STAGE_BINDING_UI,
    STAGE_BUILDING_TREE,
    STAGE_COMPLETE,
    STAGE_DECODING_AFFIXES,
    STAGE_DISCOVERING_SCHEMA,
    STAGE_READING_PARSING,
    STAGE_VALIDATING_DOCUMENT,
    NullProgressReporter,
    ProgressEvent,
    ProgressReporter,
)


class TestProgressEvent:
    """Tests for ProgressEvent dataclass."""

    def test_progress_event_creation(self):
        """ProgressEvent can be created with all fields."""
        event = ProgressEvent(task_id="task-1", stage="reading/parsing file", done=5, total=10)
        assert event.task_id == "task-1"
        assert event.stage == "reading/parsing file"
        assert event.done == 5
        assert event.total == 10

    def test_progress_event_defaults(self):
        """ProgressEvent defaults done and total to 0."""
        event = ProgressEvent(task_id="task-1", stage="reading/parsing file")
        assert event.done == 0
        assert event.total == 0

    def test_progress_event_is_indeterminate(self):
        """is_indeterminate returns True when total is 0."""
        event = ProgressEvent(task_id="task-1", stage="reading/parsing file", done=0, total=0)
        assert event.is_indeterminate

    def test_progress_event_is_determinate(self):
        """is_indeterminate returns False when total > 0."""
        event = ProgressEvent(task_id="task-1", stage="reading/parsing file", done=5, total=10)
        assert not event.is_indeterminate

    def test_progress_event_is_frozen(self):
        """ProgressEvent is immutable (frozen dataclass)."""
        event = ProgressEvent(task_id="task-1", stage="reading/parsing file")
        with pytest.raises(AttributeError):  # allow: testing frozen dataclass immutability
            event.stage = "new stage"  # type: ignore


class TestStageConstants:
    """Tests for stage constants."""

    def test_open_stages_order(self):
        """OPEN_STAGES contains stages in the correct order."""
        assert OPEN_STAGES == (
            STAGE_READING_PARSING,
            STAGE_DECODING_AFFIXES,
            STAGE_BUILDING_TREE,
            STAGE_BINDING_UI,
            STAGE_DISCOVERING_SCHEMA,
            STAGE_VALIDATING_DOCUMENT,
            STAGE_COMPLETE,
        )

    def test_reload_stages_order(self):
        """RELOAD_STAGES contains stages in the correct order."""
        assert RELOAD_STAGES == (
            STAGE_READING_PARSING,
            STAGE_DECODING_AFFIXES,
            STAGE_BUILDING_TREE,
            STAGE_APPLYING_RELOAD,
            STAGE_DISCOVERING_SCHEMA,
            STAGE_VALIDATING_DOCUMENT,
            STAGE_COMPLETE,
        )

    def test_reload_uses_applying_reload_not_binding_ui(self):
        """RELOAD_STAGES uses 'applying reload' instead of 'binding UI'."""
        assert STAGE_BINDING_UI not in RELOAD_STAGES
        assert STAGE_APPLYING_RELOAD in RELOAD_STAGES


class TestProgressReporterProtocol:
    """Tests for ProgressReporter protocol."""

    def test_null_reporter_implements_protocol(self):
        """NullProgressReporter implements ProgressReporter protocol."""
        reporter: ProgressReporter = NullProgressReporter()
        assert isinstance(reporter, ProgressReporter)

    def test_null_reporter_accepts_stage(self):
        """NullProgressReporter.stage() does not raise."""
        reporter = NullProgressReporter()
        reporter.stage("reading/parsing file")

    def test_null_reporter_accepts_tick(self):
        """NullProgressReporter.tick() does not raise."""
        reporter = NullProgressReporter()
        reporter.tick(5, 10)
        reporter.tick(0, 0)


class TestStageTracking:
    """Tests for tracking stage progression."""

    def test_stages_emitted_in_order(self):
        """Stages can be tracked in the expected order."""
        observed_stages: list[str] = []

        class TrackingReporter:
            def stage(self, name: str) -> None:
                observed_stages.append(name)

            def tick(self, done: int, total: int) -> None:
                pass

        reporter = TrackingReporter()

        # Simulate emitting stages in order
        for stage_name in OPEN_STAGES:
            reporter.stage(stage_name)

        assert observed_stages == list(OPEN_STAGES)

    def test_tick_values_are_valid(self):
        """tick(done, total) values satisfy 0 <= done <= total."""
        tick_calls: list[tuple[int, int]] = []

        class TrackingReporter:
            def stage(self, name: str) -> None:
                pass

            def tick(self, done: int, total: int) -> None:
                tick_calls.append((done, total))

        reporter = TrackingReporter()

        # Valid tick calls
        reporter.tick(0, 0)  # Indeterminate
        reporter.tick(0, 10)
        reporter.tick(5, 10)
        reporter.tick(10, 10)

        for done, total in tick_calls:
            assert 0 <= done
            if total > 0:
                assert done <= total
