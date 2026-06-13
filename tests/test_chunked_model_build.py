"""Tests for chunked model/tree builder (Commit 2.5)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app.loading.builder import ChunkedTreeBuilder, _count_items, build_model_sync
from app.loading.progress import NullProgressReporter
from tree.model import JsonTreeModel
from tree.types import JsonType


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _compare_trees(sync_model: JsonTreeModel, chunked_model: JsonTreeModel) -> None:
    """Compare two models to ensure they have the same structure."""
    sync_root = sync_model.root_item
    chunked_root = chunked_model.root_item

    def compare_items(sync_item, chunked_item, path="root"):
        assert sync_item.json_type == chunked_item.json_type, f"Type mismatch at {path}"
        assert sync_item.name == chunked_item.name, f"Name mismatch at {path}"

        if sync_item.json_type in (JsonType.OBJECT, JsonType.ARRAY):
            assert sync_item.child_count() == chunked_item.child_count(), f"Child count mismatch at {path}"
            for i in range(sync_item.child_count()):
                sync_child = sync_item.child(i)
                chunked_child = chunked_item.child(i)
                compare_items(sync_child, chunked_child, f"{path}[{i}]")
        else:
            assert sync_item.value == chunked_item.value, f"Value mismatch at {path}"

    compare_items(sync_root, chunked_root)


class TestChunkedTreeBuilderFixtureComparison:
    """Tests comparing chunked build against synchronous build."""

    def test_simple_object_matches_sync_build(self, qtbot):
        """Chunked build of a simple object matches synchronous build."""
        data = {"name": "test", "value": 42, "nested": {"a": 1, "b": 2}}

        sync_model = build_model_sync(data)
        chunked_model = [None]

        builder = ChunkedTreeBuilder(data)
        builder.finished.connect(lambda m: chunked_model.__setitem__(0, m))
        builder.start()

        qtbot.wait(200)

        assert chunked_model[0] is not None
        _compare_trees(sync_model, chunked_model[0])

    def test_simple_array_matches_sync_build(self, qtbot):
        """Chunked build of a simple array matches synchronous build."""
        data = [1, 2, 3, {"nested": True}]

        sync_model = build_model_sync(data)
        chunked_model = [None]

        builder = ChunkedTreeBuilder(data)
        builder.finished.connect(lambda m: chunked_model.__setitem__(0, m))
        builder.start()

        qtbot.wait(200)

        assert chunked_model[0] is not None
        _compare_trees(sync_model, chunked_model[0])

    def test_deeply_nested_matches_sync_build(self, qtbot):
        """Chunked build of deeply nested data matches synchronous build."""
        data = {"level1": {"level2": {"level3": {"value": "deep"}}}}

        sync_model = build_model_sync(data)
        chunked_model = [None]

        builder = ChunkedTreeBuilder(data)
        builder.finished.connect(lambda m: chunked_model.__setitem__(0, m))
        builder.start()

        qtbot.wait(200)

        assert chunked_model[0] is not None
        _compare_trees(sync_model, chunked_model[0])


class TestChunkedTreeBuilderEventLoop:
    """Tests for event loop responsiveness during chunked build."""

    def test_event_loop_processes_events_during_large_build(self, qtbot):
        """GUI event loop processes timers during large chunked build."""
        # Create a large data structure
        data = {"items": [{"id": i, "value": f"item_{i}"} for i in range(500)]}

        timer_count = [0]

        def on_timer():
            timer_count[0] += 1

        timer = QTimer()
        timer.timeout.connect(on_timer)
        timer.start(10)

        chunked_model = [None]
        builder = ChunkedTreeBuilder(data)
        builder.finished.connect(lambda m: chunked_model.__setitem__(0, m))
        builder.start()

        # Wait for build to complete
        qtbot.wait(500)

        timer.stop()

        assert chunked_model[0] is not None
        # Timer should have fired multiple times during the build
        assert timer_count[0] >= 2, f"Timer only fired {timer_count[0]} times"


class TestChunkedTreeBuilderNoPartialModel:
    """Tests ensuring no partial model is exposed before completion."""

    def test_model_not_finished_until_complete(self, qtbot):
        """Model is not emitted until build is complete."""
        data = {"items": [{"id": i} for i in range(100)]}

        finished_called = [False]
        progress_updates = []

        def on_finished(model):
            finished_called[0] = True
            # Verify the model is complete
            assert model.root_item.child_count() == 1
            items_child = model.root_item.child(0)
            assert items_child.child_count() == 100

        def on_progress(done, total):
            progress_updates.append((done, total))
            # Model should not be finished yet
            assert not finished_called[0]

        builder = ChunkedTreeBuilder(data)
        builder.finished.connect(on_finished)
        builder.progress.connect(on_progress)
        builder.start()

        qtbot.wait(300)

        assert finished_called[0]
        assert len(progress_updates) > 0


class TestCountItems:
    """Tests for the _count_items helper function."""

    def test_count_empty_object(self):
        """Empty object has 0 items."""
        assert _count_items({}) == 0

    def test_count_empty_array(self):
        """Empty array has 0 items."""
        assert _count_items([]) == 0

    def test_count_scalar(self):
        """Scalar value has 0 items."""
        assert _count_items(42) == 0
        assert _count_items("string") == 0

    def test_count_simple_object(self):
        """Simple object counts its keys."""
        assert _count_items({"a": 1, "b": 2}) == 2

    def test_count_simple_array(self):
        """Simple array counts its elements."""
        assert _count_items([1, 2, 3]) == 3

    def test_count_nested_structure(self):
        """Nested structure counts all items recursively."""
        data = {"a": [1, 2], "b": {"c": 3}}
        # a: 1 + 2 items = 3
        # b: 1 + 1 item = 2
        # Total: 5
        assert _count_items(data) == 5


class TestBuildModelSync:
    """Tests for the build_model_sync convenience function."""

    def test_build_model_sync_creates_model(self):
        """build_model_sync creates a JsonTreeModel."""
        data = {"key": "value"}
        model = build_model_sync(data)
        assert isinstance(model, JsonTreeModel)
        assert model.root_item.child_count() == 1

    def test_build_model_sync_with_show_root(self):
        """build_model_sync respects show_root parameter."""
        data = {"key": "value"}
        model = build_model_sync(data, show_root=True)
        assert model.show_root is True
