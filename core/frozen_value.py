from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FrozenValue:
    """Raw scalar literal that is preserved as-is and treated as read-only."""

    raw: str
    reason: str = "unsafe-mpq-literal"

    def __str__(self) -> str:
        return self.raw
