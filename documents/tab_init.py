"""Bootstrap a :class:`documents.tab.JsonTab` widget.

Encapsulates the dense ``__init__`` body — controller wiring, view layout,
delegate setup, validation/history setup, signal connections — so the tab
class itself stays narrative.
"""

from __future__ import annotations

from typing import Any, Callable

from documents.mutation_gateway import DocumentMutationGateway
from documents.states.io_controller import IoController
from documents.states.validation_state import ValidationState
from documents.tab_appearance import JsonTabAppearanceController
from documents.tab_data import JsonTabData
from documents.tab_demo_data import build_demo_data
from documents.tab_dependencies import JsonTabServices, build_legacy_json_tab_services
from documents.tab_editability import JsonTabEditabilityController
from documents.tab_history import TabHistoryController
from documents.tab_navigation import JsonTabNavigationController
from documents.tab_setup import (
    init_delegates_and_connections,
    init_layout,
    init_model,
    init_search_filter,
    init_shortcuts,
    init_validation_state,
)
from documents.tab_validation_view import JsonTabValidationViewController
from documents.view_controller import ViewController
from state.affix_mru import AffixMRU
from themes.icon_provider import IconProvider
from themes.spec import ThemeSpec

_DEFAULT_DATA = object()


def bootstrap(
    tab: "JsonTab",
    *,
    update_actions_callback: Callable[[], None] | None,
    status_message_callback: Callable[[str, int], None] | None,
    permanent_message_callback: Callable[[str], None] | None,
    data: Any,
    file_path: str | None,
    show_root: bool,
    theme: ThemeSpec | None,
    icon_provider: IconProvider | None,
    save_format: str | None,
    services: JsonTabServices | None,
) -> None:
    """Populate *tab* with controllers, model, view, delegates and validation."""

    tab.data_store = JsonTabData()
    tab._appearance = JsonTabAppearanceController(tab.data_store)
    tab.data_store.appearance = tab._appearance
    tab._navigation = JsonTabNavigationController(tab.data_store, tab.edit_name_or_value_from_enter)
    tab._editability = JsonTabEditabilityController(tab.data_store)
    tab.data_store.editability = tab._editability
    tab._validation_view = JsonTabValidationViewController(tab)

    resolved_services = services or build_legacy_json_tab_services(
        update_actions_callback=update_actions_callback,
        status_message_callback=status_message_callback,
        permanent_message_callback=permanent_message_callback,
        theme=theme,
        icon_provider=icon_provider,
    )
    if services is not None and (theme is not None or icon_provider is not None):
        resolved_services = JsonTabServices(
            host=services.host,
            theme=theme if theme is not None else services.theme,
            icon_provider=icon_provider if icon_provider is not None else services.icon_provider,
        )

    tab.data_store._host = resolved_services.host
    tab._appearance.initialize(resolved_services.theme, resolved_services.icon_provider)

    init_layout(tab)
    tab._editability.capture_editable_view_state()
    tab._sync_icon_size_with_font()

    if data is _DEFAULT_DATA:
        model_data = build_demo_data()
    else:
        model_data = data if data is not None else {}

    tab.data_store.affix_mru = AffixMRU()

    tab.data_store.io = IoController(tab, file_path=file_path, save_format=save_format)
    tab.data_store.io.dirtyChanged.connect(tab.dirtyChanged.emit)

    init_model(tab, model_data, show_root=show_root)

    tab.data_store.history = TabHistoryController(tab)
    tab.data_store.affix_mru.bootstrap_from_tree(tab.data_store.model.root_item)
    tab.data_store.mutations = DocumentMutationGateway(tab)

    tab.data_store.validation = ValidationState(
        tab,
        tab.data_store.model,
        on_schema_changed=lambda ref: tab.schemaChanged.emit(ref),
        on_validation_changed=lambda idx: tab.validationChanged.emit(idx),
        initial_data=model_data,
    )

    init_delegates_and_connections(tab)
    tab.set_monospace_fields_enabled(tab.data_store._monospace_fields_enabled)
    init_shortcuts(tab)
    init_search_filter(tab)

    # Phase D: viewport controller. Created after the QTreeView exists
    # (init_layout) and after the proxy/model are wired (init_model)
    # because apply_request resolves source-paths through the proxy.
    view_controller = ViewController(tab)
    tab._view_controller = view_controller
    view_controller.viewportRequested.connect(view_controller.apply_request)
    # Plug the severity provider before init_validation_state so the first
    # revalidate() → dataChanged repaint already has the provider ready.
    tab.data_store.model.set_issue_index_provider(tab._severity_provider)
    tab.validationChanged.connect(tab._on_validation_changed)
    init_validation_state(tab, model_data)

    tab.data_store.undo_stack.cleanChanged.connect(tab._on_clean_changed)
    tab.data_store.undo_stack.indexChanged.connect(tab._on_undo_index_changed)
    tab.data_store.undo_stack.setClean()
    tab._set_dirty(False)
