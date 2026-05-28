"""Tree-mutation action dispatch used by :class:`documents.tab.JsonTab`.

Keeps the kwarg-driven dispatcher and the small ``insert_sibling_*`` /
``insert_child`` helpers out of the tab class itself.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Callable

from documents.tab_protocols import TabTreeActionsProtocol
from tree_actions.clipboard import copy_selection
from tree_actions.paste import paste_auto, paste_insert_after_zip, paste_replace_zip
from tree_actions.structure import (
    cut_selection,
    delete_selection,
    duplicate_selection,
    insert_child_current,
    insert_sibling_after,
    insert_sibling_before,
    move_selection_down,
    move_selection_out_down,
    move_selection_out_up,
    move_selection_up,
    sort_selection_keys,
)


class TreeAction(Enum):
    COPY_ONLY = auto()
    CUT = auto()
    PASTE = auto()
    PASTE_ZIP = auto()
    REPLACE_ZIP = auto()
    DELETE = auto()
    DUPLICATE = auto()
    MOVE_UP = auto()
    MOVE_DOWN = auto()
    MOVE_OUT_UP = auto()
    MOVE_OUT_DOWN = auto()
    SORT_KEYS = auto()


# Order matches the historical ``elif`` chain inside ``JsonTab._run_tree_action``.
_ACTIONS: tuple[tuple[TreeAction, Callable[..., bool]], ...] = (
    (TreeAction.COPY_ONLY, copy_selection),
    (TreeAction.CUT, cut_selection),
    (TreeAction.PASTE, paste_auto),
    (TreeAction.PASTE_ZIP, paste_insert_after_zip),
    (TreeAction.REPLACE_ZIP, paste_replace_zip),
    (TreeAction.DELETE, delete_selection),
    (TreeAction.DUPLICATE, duplicate_selection),
    (TreeAction.MOVE_UP, move_selection_up),
    (TreeAction.MOVE_DOWN, move_selection_down),
    (TreeAction.MOVE_OUT_UP, move_selection_out_up),
    (TreeAction.MOVE_OUT_DOWN, move_selection_out_down),
    (TreeAction.SORT_KEYS, lambda view: sort_selection_keys(view, recursive=False)),
)


def run_tree_action(tab: TabTreeActionsProtocol, success_message: str, actions: set[TreeAction]) -> None:
    if tab.data_store.is_read_only:
        return
    view = tab.data_store.view
    for tree_action, action in _ACTIONS:
        if tree_action in actions:
            if action(view):
                tab.show_status(success_message, 1500)
            return


def do_insert_sibling_before(tab: TabTreeActionsProtocol) -> bool:
    if tab.data_store.is_read_only:
        return False
    return insert_sibling_before(tab.data_store.view)


def do_insert_sibling_after(tab: TabTreeActionsProtocol) -> bool:
    if tab.data_store.is_read_only:
        return False
    return insert_sibling_after(tab.data_store.view)


def do_insert_child(tab: TabTreeActionsProtocol) -> bool:
    if tab.data_store.is_read_only:
        return False
    return insert_child_current(tab.data_store.view)
