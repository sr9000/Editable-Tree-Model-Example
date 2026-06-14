from __future__ import annotations

import os
from typing import Any, Callable

from PySide6.QtCore import QModelIndex, Qt, Signal
from PySide6.QtWidgets import QLineEdit, QWidget

from documents.composition import init as tab_init
from documents.composition.dependencies import JsonTabHost, JsonTabServices
from documents.composition.marker import JsonTabWidgetMarker
from documents.controllers.appearance import JsonTabAppearanceController
from documents.controllers.editability import JsonTabEditabilityController
from documents.controllers.navigation import JsonTabNavigationController
from documents.controllers.validation import TabValidationController
from documents.controllers.view import ViewController
from documents.seams.mutation_gateway import DocumentMutationGateway
from documents.states.editing_controller import EditingController
from documents.states.io_controller import IoController
from documents.states.view_state import ViewState
from state.affix_mru import AffixMRU
from themes.icon_provider import IconProvider
from themes.spec import ThemeSpec
from tree.item import JsonTreeItem
from tree.model import JsonTreeModel
from tree.view import JsonTreeView

_DEFAULT_DATA = tab_init._DEFAULT_DATA


class JsonTab(QWidget, JsonTabWidgetMarker):
    _appearance: JsonTabAppearanceController | None = None
    _navigation: JsonTabNavigationController | None = None
    _editability: JsonTabEditabilityController | None = None
    _view_controller: ViewController | None = None

    _io: IoController | None = None
    _view_state: ViewState | None = None
    _editing: EditingController | None = None
    _validation: TabValidationController | None = None
    _host: JsonTabHost | None = None

    dirtyChanged = Signal(bool)
    schemaChanged = Signal(object)
    validationChanged = Signal(object)

    def eventFilter(self, watched, event):  # type: ignore[override]
        navigation = self._navigation
        if navigation is not None and navigation.handle_event_filter(watched, event):
            return True
        return super().eventFilter(watched, event)

    def __init__(
        self,
        update_actions_callback: Callable[[], None] | None = None,
        status_message_callback: Callable[[str, int], None] | None = None,
        data: Any = _DEFAULT_DATA,
        file_path: str | None = None,
        show_root: bool = False,
        parent=None,
        permanent_message_callback: Callable[[str], None] | None = None,
        theme: ThemeSpec | None = None,
        icon_provider: IconProvider | None = None,
        save_format: str | None = None,
        *,
        services: JsonTabServices | None = None,
        prebuilt_model: JsonTreeModel | None = None,
        defer_validation_init: bool = False,
    ):
        super().__init__(parent)

        tab_init.bootstrap(
            self,
            update_actions_callback=update_actions_callback,
            status_message_callback=status_message_callback,
            permanent_message_callback=permanent_message_callback,
            data=data,
            file_path=file_path,
            show_root=show_root,
            theme=theme,
            icon_provider=icon_provider,
            save_format=save_format,
            services=services,
            prebuilt_model=prebuilt_model,
            defer_validation_init=defer_validation_init,
        )

    @property
    def editability(self) -> JsonTabEditabilityController:
        """Read-only/editable mode controller."""
        assert self._editability is not None, "editability accessed before bootstrap"
        return self._editability

    @property
    def mutations(self) -> DocumentMutationGateway:
        """Typed accessor for the document mutation gateway."""
        return self._editing.mutations

    @property
    def io(self) -> IoController:
        """Return the IO controller."""
        return self._io

    @property
    def view_state(self) -> ViewState:
        """Return the passive view state container."""
        return self._view_state

    @property
    def editing(self) -> EditingController:
        """Return the editing controller."""
        return self._editing

    @property
    def validation(self) -> TabValidationController:
        return self._validation

    @property
    def undo_stack(self):
        return self._editing.history.undo_stack

    @property
    def view(self) -> JsonTreeView:
        """Return the underlying tree view."""
        return self._view_state.view

    @property
    def view_controller(self) -> ViewController:
        """Return the selection, expansion, and scroll controller."""
        assert self._view_controller is not None, "view_controller accessed before bootstrap"
        return self._view_controller

    @property
    def model(self) -> JsonTreeModel:
        """Return the underlying tree model."""
        return self._editing.model

    def root_index(self) -> QModelIndex:
        """Return the index used as the logical root for traversal."""
        model = self._editing.model
        if not model.show_root:
            return QModelIndex()
        return model.index(0, 0, QModelIndex())

    def root_item(self) -> JsonTreeItem:
        """Return the root tree item."""
        return self._editing.model.root_item

    def root_data(self) -> Any:
        """Return a fresh JSON-serializable snapshot of the document root."""
        return self._editing.model.root_item.to_json()

    def row_count(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return the number of children directly under ``parent``."""
        return self._editing.model.rowCount(parent)

    def column_count(self) -> int:
        """Return the number of model columns."""
        return self._editing.model.columnCount()

    @property
    def zoom_pt(self) -> int:
        """Per-tab editor font point-size override."""
        return self._appearance.font_pt

    @property
    def search_edit(self) -> QLineEdit:
        return self._view_state.search_edit

    @property
    def last_move_placed(self) -> list[tuple[tuple, int]]:
        return self._editing.last_move_placed

    @property
    def affix_mru(self) -> AffixMRU:
        return self._editing.affix_mru

    def closeEvent(self, event):  # type: ignore[override]
        self._validation.release()
        super().closeEvent(event)

    @property
    def appearance(self) -> JsonTabAppearanceController:
        """Theme / font / icon-size / key-column appearance controller.

        Plan 21 O3 retired the 14 ``set_theme`` / ``apply_font_profile`` /
        ``zoom_*`` / ``set_*_font_*`` / ``resize_key_columns`` /
        ``_scale_columns_for_font`` / ``_set_font_pt`` /
        ``_sync_icon_size_with_font`` / ``_on_model_reset`` forwarders on
        ``JsonTab``; callers reach the behaviour through ``tab.appearance.*``.
        """
        assert self._appearance is not None, "appearance accessed before bootstrap"
        return self._appearance

    def refresh_actions(self) -> None:
        self._host.refresh_actions()

    def show_status(self, message: str, timeout_ms: int = 3000) -> None:
        """Publish *message* via the injected host."""
        self._host.show_status_message(message, timeout_ms)

    def show_permanent_message(self, message: str) -> None:
        self._host.show_permanent_message(message)

    def edit_name_or_value_from_enter(self) -> None:
        self.editing.inline.edit_name_or_value_from_enter()

    def display_name(self) -> str:
        if self._io.file_path:
            # ``os.path.basename`` is platform-aware on POSIX (only "/") so we
            # also strip "\\" explicitly to handle Windows-style paths produced
            # by ``QFileDialog`` and similar APIs regardless of host OS.
            name = os.path.basename(self._io.file_path.replace("\\", "/")) or "Untitled"
        else:
            name = "Untitled"
        return f"{name} *" if self._io.dirty else name

    def save(self) -> bool:
        return self.io.save()

    def save_as(self, path: str | None = None) -> bool:
        return self.io.save_as(path=path)
