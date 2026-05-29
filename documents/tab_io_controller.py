"""Back-compat re-export of :class:`documents.states.io_state.IoState`.
Phase I (I1) moved the IO substate to ``documents/states/io_state.py``
and renamed the class to :class:`IoState`.  This module keeps the
historical ``TabIOController`` symbol importable for tests and any
not-yet-migrated production callers.
"""
from __future__ import annotations
from documents.states.io_state import IoState as TabIOController
__all__ = ["TabIOController"]
