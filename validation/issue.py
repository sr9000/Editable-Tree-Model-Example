from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    severity: Literal["error", "warning"]
    message: str
    instance_path: tuple[str | int, ...]
    schema_path: tuple[str | int, ...]
    kind: str
