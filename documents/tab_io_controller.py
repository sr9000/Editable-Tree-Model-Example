"""Back-compat re-export of :class:`documents.states.io_controller.IoController`.

Plan 20 Phase I (I1) moved the IO substate into ``documents/states/`` and
Plan 21 Phase L (L1) promoted it from ``IoState`` to the active
:class:`IoController`.  This module keeps the historical
``TabIOController`` symbol importable for tests and any not-yet-migrated
production callers.
"""

from __future__ import annotations

from documents.states.io_controller import IoController as TabIOController

__all__ = ["TabIOController"]
