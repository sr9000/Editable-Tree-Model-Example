"""Passive container for per-tab UI widgets and delegates."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QLineEdit

from delegates.name_delegate import NameDelegate
from delegates.type_delegate import JsonTypeDelegate
from delegates.value import ValueDelegate
from documents.json_tab_ui import Ui_JsonTab
from tree.view import JsonTreeView
from tree.filter_proxy import TreeFilterProxy


@dataclass
class ViewState:
    """Per-tab UI references."""

    ui: Ui_JsonTab | None = None
    view: JsonTreeView | None = None
    search_edit: QLineEdit | None = None
    proxy: TreeFilterProxy | None = None
    name_delegate: NameDelegate | None = None
    type_delegate: JsonTypeDelegate | None = None
    value_delegate: ValueDelegate | None = None


__all__ = ["ViewState"]
