from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from documents.tab_data_facade import JsonTabDataFacade

if TYPE_CHECKING:
    from PySide6.QtWidgets import QLineEdit

    from delegates.name_delegate import NameDelegate
    from delegates.type_delegate import JsonTypeDelegate
    from delegates.value import ValueDelegate
    from documents.json_tab_ui import Ui_JsonTab
    from documents.mutation_gateway import DocumentMutationGateway
    from state.affix_mru import AffixMRU
    from themes.icon_provider import IconProvider
    from themes.spec import ThemeSpec
    from tree.model import JsonTreeModel
    from tree.view import JsonTreeView
    from tree_filter_proxy import TreeFilterProxy


@dataclass
class JsonTabData(JsonTabDataFacade):
    ui: Ui_JsonTab | None = None
    view: JsonTreeView | None = None
    search_edit: QLineEdit | None = None
    model: JsonTreeModel = field(default=None)
    proxy: TreeFilterProxy = field(default=None)
    name_delegate: NameDelegate = field(default=None)
    type_delegate: JsonTypeDelegate = field(default=None)
    value_delegate: ValueDelegate = field(default=None)
    _default_font_pt: int = 10
    _font_pt: int = 10
    _user_sized_columns: set[int] = field(default_factory=set)
    _programmatic_column_resize: bool = False
    _theme: ThemeSpec | None = None
    _icon_provider: IconProvider | None = None
    _monospace_fields_enabled: bool = False
    _regular_font_family: str | None = None
    _monospace_font_family: str | None = None
    affix_mru: AffixMRU = field(default=None)
    mutations: DocumentMutationGateway = field(default=None)
    _diff_applier: Any = field(default=None)
    _editable_view_edit_triggers: Any = None
    _editable_drag_enabled: Any = None
    _editable_accept_drops: Any = None
    _editable_drag_drop_mode: Any = None
