from __future__ import annotations

from jsontream import StreamingJSONEncoderWrapper
from tree_actions.clipboard import MIME_JSON_TREE, copy_selection
from tree_actions.context_menu import show_context_menu
from tree_actions.paste import paste_from_clipboard
from tree_actions.structure import (
    collapse_all,
    cut_selection,
    delete_selection,
    duplicate_selection,
    expand_all,
    insert_child_current,
    insert_sibling_after,
    insert_sibling_before,
    move_selection_down,
    move_selection_up,
    sort_selection_keys,
)


def to_json(item):
    encoder = StreamingJSONEncoderWrapper(separators=(",", ":"), indent=2)
    source = item.to_json() if hasattr(item, "to_json") else item
    return "".join(encoder.iterencode(source))
