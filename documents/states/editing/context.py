"""Shared immutable context for editing collaborators."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class EditingContext:
    tab: Any
    move_view_state: Any | None
    history_provider: Callable[[], Any | None]


__all__ = ["EditingContext"]
