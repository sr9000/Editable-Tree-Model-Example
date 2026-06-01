"""Typed external protocol exposed by document tabs."""

from __future__ import annotations

from typing import Any, ClassVar, Protocol, runtime_checkable

from PySide6.QtCore import QModelIndex, Signal
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import QLineEdit

from documents.controllers.validation import TabValidationController
from documents.controllers.view import ViewController
from documents.seams.mutation_gateway import DocumentMutationGateway
from documents.states.io_controller import IoController
from state.affix_mru import AffixMRU
from tree.item import JsonTreeItem
from tree.model import JsonTreeModel
from tree.view import JsonTreeView


@runtime_checkable
class Document(Protocol):
    """Stable application-facing surface implemented by :class:`documents.tab.JsonTab`."""

    # IO
    @property
    def io(self) -> IoController: ...
    def display_name(self) -> str: ...
    def save(self) -> bool: ...
    def save_as(self, path: str | None = ...) -> bool: ...

    # Validation
    @property
    def validation(self) -> TabValidationController: ...

    # Editing
    @property
    def editing(self) -> "EditingController": ...
    @property
    def mutations(self) -> DocumentMutationGateway: ...
    @property
    def model(self) -> JsonTreeModel: ...
    @property
    def undo_stack(self) -> QUndoStack: ...
    @property
    def affix_mru(self) -> AffixMRU: ...
    @property
    def last_move_placed(self) -> list[tuple[tuple, int]]: ...

    def root_index(self) -> QModelIndex: ...
    def root_item(self) -> JsonTreeItem: ...
    def root_data(self) -> Any: ...
    def row_count(self, parent: QModelIndex = ...) -> int: ...

    def edit_name_or_value_from_enter(self) -> None: ...

    # View
    @property
    def view(self) -> JsonTreeView: ...
    @property
    def view_controller(self) -> ViewController: ...
    @property
    def search_edit(self) -> QLineEdit: ...

    def resize_key_columns(self, force: bool = ...) -> None: ...

    # Appearance / editability
    @property
    def editability(self) -> "JsonTabEditabilityController": ...

    @property
    def appearance(self) -> "JsonTabAppearanceController": ...
    @property
    def zoom_pt(self) -> int: ...

    # Host messaging
    def show_status(self, message: str, timeout_ms: int = ...) -> None: ...

    # Signals
    dirtyChanged: ClassVar[Signal]
    schemaChanged: ClassVar[Signal]
    validationChanged: ClassVar[Signal]


__all__ = ["Document"]
