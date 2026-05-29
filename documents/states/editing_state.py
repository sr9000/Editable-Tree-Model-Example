"""EditingState -- per-tab editing substate.

Per Plan 20 Phase I (I3): groups the tree model, mutation gateway,
undo-history controller, affix MRU and move-view caches that a
:class:`documents.tab.JsonTab` uses to mediate edits.

This is a passive container.  The owned objects are still constructed
in :mod:`documents.tab_init` / :mod:`documents.tab_setup` and reach
the substate through :class:`JsonTabData`'s forwarding properties.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from documents.mutation_gateway import DocumentMutationGateway
from documents.tab_history import TabHistoryController
from state.affix_mru import AffixMRU
from tree.model import JsonTreeModel


@dataclass
class EditingState:
    """Per-tab editing substate."""

    model: JsonTreeModel | None = None
    mutations: DocumentMutationGateway | None = None
    affix_mru: AffixMRU | None = None
    history: TabHistoryController | None = None
    last_move_placed: list[tuple[tuple[int, ...], int]] = field(default_factory=list)


__all__ = ["EditingState"]
