"""EditingState -- back-compat alias for :class:`EditingController`.

Plan 21 Phase N (N1) promoted the editing axis from a passive substate
to an active controller.  The substate name is retained as an alias so
existing references keep working until the Plan 21 closeout.
"""

from __future__ import annotations

from documents.states.editing_controller import EditingController as EditingState

__all__ = ["EditingState"]
