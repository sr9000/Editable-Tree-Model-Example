"""Tree-mutation action dispatch used by :class:`documents.tab.JsonTab`.

Keeps the kwarg-driven dispatcher and the small ``insert_sibling_*`` /
``insert_child`` helpers out of the tab class itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

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

if TYPE_CHECKING:
    from documents.tab import JsonTab


# Order matches the historical ``elif`` chain inside ``JsonTab._run_tree_action``.
_ACTIONS: tuple[tuple[str, Callable[..., bool]], ...] = (
    ("copy_only", copy_selection),
    ("cut", cut_selection),
    ("paste", paste_auto),
    ("paste_zip", paste_insert_after_zip),
    ("replace_zip", paste_replace_zip),
    ("delete", delete_selection),
    ("duplicate", duplicate_selection),
    ("move_up", move_selection_up),
    ("move_down", move_selection_down),
    ("move_out_up", move_selection_out_up),
    ("move_out_down", move_selection_out_down),
    ("sort_keys", lambda view: sort_selection_keys(view, recursive=False)),
)


def run_tree_action(tab: JsonTab, success_message: str, **flags: bool) -> None:
    if tab.data_store.is_read_only:
        return
    view = tab.data_store.view
    for flag_name, action in _ACTIONS:
        if flags.get(flag_name):
            if action(view):
                tab.show_status(success_message, 1500)
            return


def do_insert_sibling_before(tab: JsonTab) -> bool:
    if tab.data_store.is_read_only:
        return False
    return insert_sibling_before(tab.data_store.view)


def do_insert_sibling_after(tab: JsonTab) -> bool:
    if tab.data_store.is_read_only:
        return False
    return insert_sibling_after(tab.data_store.view)


def do_insert_child(tab: JsonTab) -> bool:
    if tab.data_store.is_read_only:
        return False
    return insert_child_current(tab.data_store.view)
