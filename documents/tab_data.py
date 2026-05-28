from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from documents.tab_data_facade import JsonTabDataFacade


@dataclass
class JsonTabData(JsonTabDataFacade):
    ui: Any = None
    view: Any = None
    search_edit: Any = None
    model: Any = field(default=None)
    proxy: Any = field(default=None)
    name_delegate: Any = field(default=None)
    type_delegate: Any = field(default=None)
    value_delegate: Any = field(default=None)
    affix_mru: Any = field(default=None)
    mutations: Any = field(default=None)
    _diff_applier: Any = field(default=None)
