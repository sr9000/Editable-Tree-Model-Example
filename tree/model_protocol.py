"""Protocol describing the surface ``model_actions`` consumes.

Concrete implementation: :class:`tree.model.JsonTreeModel`. Declared as a
``Protocol`` so test doubles can satisfy it without subclassing while the
``model_actions`` helpers consume the contract via direct attribute /
method access (no reflection).
"""

from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import QModelIndex


class TreeModelLike(Protocol):
    """Subset of :class:`tree.model.JsonTreeModel` consumed by ``model_actions``."""

    show_root: bool

    def get_item(self, index: QModelIndex): ...  # pragma: no cover
    def move_row(self, parent: QModelIndex, src_row: int, dst_row: int) -> bool: ...  # pragma: no cover
    def sort_keys(self, index: QModelIndex, recursive: bool = False) -> bool: ...  # pragma: no cover

    @property
    def root_item(self): ...  # pragma: no cover
