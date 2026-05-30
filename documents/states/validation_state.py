"""ValidationState -- per-tab validation substate.

Per Plan 20 Phase I (I4): the validation axis (schema source/ref,
issue index, auto-rescan timer, registry binding) is fully
encapsulated by :class:`documents.tab_validation.TabValidationController`.
This module exposes it under the substate name :class:`ValidationState`
so the four-axis decomposition (IoController / ViewState / EditingState /
ValidationState) is symmetric.  The legacy ``TabValidationController``
symbol remains importable for tests and not-yet-migrated callers.
"""

from __future__ import annotations

from documents.tab_validation import TabValidationController as ValidationState

__all__ = ["ValidationState"]
