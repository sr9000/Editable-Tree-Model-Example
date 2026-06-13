"""Chunked cooperative model/tree builder.

This module provides a builder that constructs the item tree/model off to
the side using an explicit work stack and yields control after each time
slice. The view receives no model until the build result is complete.
"""

from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal

from app.loading.progress import STAGE_BUILDING_TREE, ProgressReporter
from core.raw_numeric import RawNumericValue
from tree.item import JsonTreeItem, SecretNamePredicate, _default_secret_name_predicate
from tree.item_coercion import compute_editable
from tree.model import JsonTreeModel
from tree.types import SECRET_FAMILY, TEXT_FAMILY, JsonType, parse_json_type

# Target time slice for each batch (16ms for ~60fps responsiveness)
TARGET_SLICE_MS = 16
# Maximum time before yielding (for tests)
MAX_SLICE_MS = 50


class ChunkedTreeBuilder(QObject):
    """Builds a JsonTreeModel incrementally in time-sliced batches.

    The builder processes work items from an explicit stack and yields
    control after each time slice. The model is not bound to any view
    until the build is complete.

    Signals
    -------
    finished(model)
        Emitted when the build is complete with the finished model.
    progress(done, total)
        Emitted to report progress within the building stage.
    """

    finished = Signal(object)
    progress = Signal(int, int)

    def __init__(
        self,
        data: Any,
        *,
        show_root: bool = False,
        reporter: ProgressReporter | None = None,
        icon_provider=None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._data = data
        self._show_root = show_root
        self._reporter = reporter
        self._icon_provider = icon_provider
        self._model: JsonTreeModel | None = None
        self._total_items = 0
        self._built_items = 0
        self._latest_path = ""
        self._root_item: JsonTreeItem | None = None
        self._work_stack: list[tuple[JsonTreeItem, list[tuple[str | int | None, Any]], int, str]] = []
        self._secret_name_predicate: SecretNamePredicate = _default_secret_name_predicate

    def start(self) -> None:
        """Start the chunked build process.

        Uses a QTimer to schedule work slices, allowing the event loop
        to process other events between slices.
        """
        if self._reporter is not None:
            self._reporter.stage(STAGE_BUILDING_TREE)

        # Keep progress indeterminate for real loads. A full pre-count is also
        # a recursive walk of the whole document, which would reintroduce a GUI
        # freeze before chunked construction starts.
        self._total_items = 0
        self._built_items = 0
        self._latest_path = ""

        self._root_item = _make_shallow_item(
            None,
            self._data,
            None,
            secret_name_predicate=self._secret_name_predicate,
        )
        self._push_children(self._root_item, self._data, "")

        # Schedule the first work slice
        QTimer.singleShot(0, self._do_work_slice)

    def _do_work_slice(self) -> None:
        """Process a time slice of work items."""
        start_time = time.monotonic()
        slice_ms = 0

        while slice_ms < TARGET_SLICE_MS:
            if not self._build_one_item():
                self._on_build_complete()
                return

            self._built_items += 1
            if self._reporter is not None:
                self._reporter.detail(self._built_items, self._latest_path)
                self._reporter.tick(0, 0)
            self.progress.emit(self._built_items, self._total_items)

            slice_ms = (time.monotonic() - start_time) * 1000

        if slice_ms > MAX_SLICE_MS:
            # Defensive cap for unusually slow item construction. The next
            # slice is still scheduled through the event loop below.
            pass

        if not self._work_stack:
            self._on_build_complete()
            return

        # Schedule the next work slice
        QTimer.singleShot(0, self._do_work_slice)

    def _on_build_complete(self) -> None:
        """Called when the build is complete."""
        if self._model is None:
            assert self._root_item is not None
            self._model = JsonTreeModel(
                None,
                show_root=self._show_root,
                icon_provider=self._icon_provider,
                root_item=self._root_item,
            )
        if self._reporter is not None:
            self._reporter.tick(0, 0)
        self.progress.emit(self._total_items, self._total_items)
        self.finished.emit(self._model)

    def _push_children(self, item: JsonTreeItem, value: Any, parent_path: str) -> None:
        """Push a child-iteration frame for a container item."""
        if isinstance(value, dict):
            entries = list(value.items())
        elif isinstance(value, list):
            entries = [(None, child_value) for child_value in value]
        else:
            return
        if entries:
            self._work_stack.append((item, entries, 0, parent_path))

    def _build_one_item(self) -> bool:
        """Build one pending child item.

        Returns False when no work remains.
        """
        while self._work_stack:
            parent_item, entries, index, parent_path = self._work_stack[-1]
            if index >= len(entries):
                self._work_stack.pop()
                continue

            self._work_stack[-1] = (parent_item, entries, index + 1, parent_path)
            name, value = entries[index]
            path_segment: str | int | None = index if name is None else name
            self._latest_path = _append_json_pointer(parent_path, path_segment)
            child = _make_shallow_item(
                parent_item,
                value,
                name,
                secret_name_predicate=self._secret_name_predicate,
            )
            parent_item.append_child(child)
            self._push_children(child, value, self._latest_path)
            return True

        return False


def _make_shallow_item(
    parent_item: JsonTreeItem | None,
    value: Any,
    name: str | int | None,
    *,
    secret_name_predicate: SecretNamePredicate,
) -> JsonTreeItem:
    """Create an item without recursively constructing descendants."""
    json_type = parse_json_type(value)

    if isinstance(value, RawNumericValue) and json_type not in TEXT_FAMILY and json_type not in SECRET_FAMILY:
        json_type = JsonType.RAW_FLOAT

    if json_type not in (JsonType.ARRAY, JsonType.OBJECT):
        return JsonTreeItem(
            parent_item,
            value,
            name,
            secret_name_predicate=secret_name_predicate,
        )

    item = JsonTreeItem.__new__(JsonTreeItem)
    item.parent_item = parent_item
    item._secret_name_predicate = secret_name_predicate
    item.name = name
    item.child_items = []
    item.explicit_type = False
    item._row_in_parent = -1
    item._children_dirty = True
    item.json_type = json_type
    item.value = [] if json_type is JsonType.ARRAY else {}
    item.editable = compute_editable(item.json_type, item.value, item.EDITABLE_BLOB_LIMIT)
    return item


def _count_items(data: Any) -> int:
    """Count the total number of items in the data structure."""
    if isinstance(data, dict):
        count = 0
        for value in data.values():
            count += 1 + _count_items(value)
        return count
    elif isinstance(data, list):
        count = 0
        for value in data:
            count += 1 + _count_items(value)
        return count
    return 0


def _append_json_pointer(parent_path: str, segment: str | int | None) -> str:
    """Append one segment to a JSON Pointer-style path."""
    if segment is None:
        return parent_path
    token = _escape_json_pointer_token(str(segment))
    if not parent_path:
        return f"/{token}"
    return f"{parent_path}/{token}"


def _escape_json_pointer_token(token: str) -> str:
    """Escape a JSON Pointer token."""
    return token.replace("~", "~0").replace("/", "~1")


def build_model_sync(
    data: Any,
    *,
    show_root: bool = False,
) -> JsonTreeModel:
    """Build a JsonTreeModel synchronously.

    This is a convenience function for tests and simple use cases.
    """
    return JsonTreeModel(data, show_root=show_root)


__all__ = [
    "ChunkedTreeBuilder",
    "build_model_sync",
    "TARGET_SLICE_MS",
    "MAX_SLICE_MS",
]
