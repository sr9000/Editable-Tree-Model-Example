from __future__ import annotations
from dataclasses import dataclass, field
from PySide6.QtWidgets import QLineEdit
from delegates.name_delegate import NameDelegate
from delegates.type_delegate import JsonTypeDelegate
from delegates.value import ValueDelegate
from documents.json_tab_ui import Ui_JsonTab
from documents.mutation_gateway import DocumentMutationGateway
from documents.states.view_state import ViewState
from documents.tab_data_facade import JsonTabDataFacade
from state.affix_mru import AffixMRU
from tree.model import JsonTreeModel
from tree.view import JsonTreeView
from tree_filter_proxy import TreeFilterProxy
@dataclass
class JsonTabData(JsonTabDataFacade):
    # Phase I (I2): UI widgets and delegates moved into ViewState.  The
    # individual attributes below remain accessible via property forwards
    # so existing call-sites (tab_setup.py writes, tests' read-only
    # reach-in to ``tab.data_store.view`` etc.) keep working unchanged.
    view_state: ViewState = field(default_factory=ViewState)
    model: JsonTreeModel = None
    affix_mru: AffixMRU = None
    mutations: DocumentMutationGateway | None = None
    # ----- ViewState forwards (read+write) -------------------------------
    @property
    def ui(self) -> Ui_JsonTab | None:
        return self.view_state.ui
    @ui.setter
    def ui(self, value: Ui_JsonTab | None) -> None:
        self.view_state.ui = value
    @property
    def view(self) -> JsonTreeView | None:
        return self.view_state.view
    @view.setter
    def view(self, value: JsonTreeView | None) -> None:
        self.view_state.view = value
    @property
    def search_edit(self) -> QLineEdit | None:
        return self.view_state.search_edit
    @search_edit.setter
    def search_edit(self, value: QLineEdit | None) -> None:
        self.view_state.search_edit = value
    @property
    def proxy(self) -> TreeFilterProxy | None:
        return self.view_state.proxy
    @proxy.setter
    def proxy(self, value: TreeFilterProxy | None) -> None:
        self.view_state.proxy = value
    @property
    def name_delegate(self) -> NameDelegate | None:
        return self.view_state.name_delegate
    @name_delegate.setter
    def name_delegate(self, value: NameDelegate | None) -> None:
        self.view_state.name_delegate = value
    @property
    def type_delegate(self) -> JsonTypeDelegate | None:
        return self.view_state.type_delegate
    @type_delegate.setter
    def type_delegate(self, value: JsonTypeDelegate | None) -> None:
        self.view_state.type_delegate = value
    @property
    def value_delegate(self) -> ValueDelegate | None:
        return self.view_state.value_delegate
    @value_delegate.setter
    def value_delegate(self, value: ValueDelegate | None) -> None:
        self.view_state.value_delegate = value
