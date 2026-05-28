from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from PySide6.QtWidgets import QLineEdit

from delegates.name_delegate import NameDelegate
from delegates.type_delegate import JsonTypeDelegate
from delegates.value import ValueDelegate
from documents.json_tab_ui import Ui_JsonTab
from documents.mutation_gateway import DocumentMutationGateway
from documents.tab_data_facade import JsonTabDataFacade
from state.affix_mru import AffixMRU
from tree.model import JsonTreeModel
from tree.view import JsonTreeView
from tree_filter_proxy import TreeFilterProxy


@dataclass
class JsonTabData(JsonTabDataFacade):
    ui: Ui_JsonTab = None
    view: JsonTreeView = None
    search_edit: QLineEdit = None
    model: JsonTreeModel = None
    proxy: TreeFilterProxy = None
    name_delegate: NameDelegate = None
    type_delegate: JsonTypeDelegate = None
    value_delegate: ValueDelegate = None
    affix_mru: AffixMRU = None
    mutations: DocumentMutationGateway = None
