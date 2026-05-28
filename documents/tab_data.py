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
    affix_mru: AffixMRU = field(default=None)
    mutations: DocumentMutationGateway = field(default=None)
    _diff_applier: Any = field(default=None)
