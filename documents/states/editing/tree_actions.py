"""Tree action enum and dispatch table for editing operations."""

from __future__ import annotations

from enum import Enum, auto
from typing import Callable

from tree_actions.clipboard import copy_selection
from tree_actions.paste import (paste_auto, paste_insert_after_zip,
                                paste_replace_zip)
from tree_actions.structure import (cut_selection, delete_selection,
                                    duplicate_selection, move_selection_down,
                                    move_selection_out_down,
                                    move_selection_out_up, move_selection_up,
                                    sort_selection_keys)


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


ACTIONS: tuple[tuple[TreeAction, Callable[..., bool]], ...] = (
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


__all__ = ["TreeAction", "ACTIONS"]
