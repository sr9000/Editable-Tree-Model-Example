"""Progress reporting protocol for loading operations.

This module defines the ``ProgressEvent`` dataclass and ``ProgressReporter``
protocol used to communicate progress between the coordinator, worker,
builder, and UI components without coupling them directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

# Required progress stages in order (when applicable)
STAGE_READING_PARSING = "reading/parsing file"
STAGE_DECODING_AFFIXES = "decoding number affixes"
STAGE_BUILDING_TREE = "building item tree"
STAGE_BINDING_UI = "binding UI"
STAGE_APPLYING_RELOAD = "applying reload"  # Used instead of BINDING_UI for reload
STAGE_DISCOVERING_SCHEMA = "discovering schema"
STAGE_VALIDATING_DOCUMENT = "validating document"
STAGE_COMPLETE = "complete"

# Ordered list of stages for open operations
OPEN_STAGES = (
    STAGE_READING_PARSING,
    STAGE_DECODING_AFFIXES,
    STAGE_BUILDING_TREE,
    STAGE_BINDING_UI,
    STAGE_DISCOVERING_SCHEMA,
    STAGE_VALIDATING_DOCUMENT,
    STAGE_COMPLETE,
)

# Ordered list of stages for reload operations
RELOAD_STAGES = (
    STAGE_READING_PARSING,
    STAGE_DECODING_AFFIXES,
    STAGE_BUILDING_TREE,
    STAGE_APPLYING_RELOAD,
    STAGE_DISCOVERING_SCHEMA,
    STAGE_VALIDATING_DOCUMENT,
    STAGE_COMPLETE,
)


@dataclass(frozen=True)
class ProgressEvent:
    """A progress event emitted during loading operations.

    Attributes
    ----------
    task_id : str
        Unique identifier for the loading task.
    stage : str
        The current stage name (e.g., "reading/parsing file").
    done : int
        Number of items completed in the current stage.
    total : int
        Total number of items in the current stage.
        When unknown, both done and total are 0.
    processed : int
        Number of fields/values processed for detail reporting.
    path : str
        Current JSON-Pointer-style path for detail reporting.
    """

    task_id: str
    stage: str
    done: int = 0
    total: int = 0
    processed: int = 0
    path: str = ""

    @property
    def is_indeterminate(self) -> bool:
        """True if progress is indeterminate (total unknown)."""
        return self.total <= 0


@runtime_checkable
class ProgressReporter(Protocol):
    """Protocol for reporting progress during loading operations.

    Implementations receive stage and tick notifications without
    coupling to specific UI components.
    """

    def stage(self, name: str) -> None:
        """Report a new stage.

        Parameters
        ----------
        name : str
            The stage name (e.g., "reading/parsing file").
        """
        ...

    def tick(self, done: int, total: int) -> None:
        """Report progress within a stage.

        Parameters
        ----------
        done : int
            Number of items completed.
        total : int
            Total number of items. Use 0 for both when unknown.
        """
        ...

    def detail(self, processed: int, path: str) -> None:
        """Report detailed progress metadata.

        Parameters
        ----------
        processed : int
            Number of fields/values processed so far.
        path : str
            Current JSON-Pointer-style path.
        """
        ...


class NullProgressReporter:
    """A no-op progress reporter for testing or when progress is not needed."""

    def stage(self, name: str) -> None:
        pass

    def tick(self, done: int, total: int) -> None:
        pass

    def detail(self, processed: int, path: str) -> None:
        pass


__all__ = [
    "ProgressEvent",
    "ProgressReporter",
    "NullProgressReporter",
    "STAGE_READING_PARSING",
    "STAGE_DECODING_AFFIXES",
    "STAGE_BUILDING_TREE",
    "STAGE_BINDING_UI",
    "STAGE_APPLYING_RELOAD",
    "STAGE_DISCOVERING_SCHEMA",
    "STAGE_VALIDATING_DOCUMENT",
    "STAGE_COMPLETE",
    "OPEN_STAGES",
    "RELOAD_STAGES",
]
