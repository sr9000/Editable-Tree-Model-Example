"""ViewState -- per-tab UI widget/delegate substate.

Per Plan 20 Phase I (I2): groups the QWidget / proxy / delegate
references that a :class:`documents.tab.JsonTab` owns so they can be
populated as a single substate object instead of being scattered as
top-level fields on the former ``JsonTabData`` god-dataclass.

This is a passive container -- it holds references but does not own
construction logic.  The widgets and delegates are still constructed
in :mod:`documents.tab_setup` (``init_layout`` / ``init_model`` /
``init_delegates_and_connections``) and assigned through the
:class:`JsonTabData` forwarding properties.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QLineEdit

from delegates.name_delegate import NameDelegate
from delegates.type_delegate import JsonTypeDelegate
from delegates.value import ValueDelegate
from documents.json_tab_ui import Ui_JsonTab
from tree.view import JsonTreeView
from tree_filter_proxy import TreeFilterProxy


@dataclass
class ViewState:
    """Per-tab UI widget and delegate references."""

    ui: Ui_JsonTab | None = None
    view: JsonTreeView | None = None
    search_edit: QLineEdit | None = None
    proxy: TreeFilterProxy | None = None
    name_delegate: NameDelegate | None = None
    type_delegate: JsonTypeDelegate | None = None
    value_delegate: ValueDelegate | None = None


__all__ = ["ViewState"]
