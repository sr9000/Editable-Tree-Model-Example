from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    message: str
    instance_path: tuple[str | int, ...]
    schema_path: tuple[str | int, ...]
    kind: str
