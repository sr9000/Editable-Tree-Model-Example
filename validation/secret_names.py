import re
from collections.abc import Iterable


def _split_words(name: str) -> list[str]:
    """Split on separators and camelCase boundaries into lowercase words."""
    separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    return [w for w in re.split(r"[_\-\.\s]+", separated.lower()) if w]


def name_looks_secret(name: str, prefixes: Iterable[str]) -> bool:
    """Return True when any split word starts with any configured prefix."""
    if not isinstance(name, str) or not name:
        return False

    words = _split_words(name)
    normalized_prefixes = [p.lower() for p in prefixes if isinstance(p, str) and p]
    if not words or not normalized_prefixes:
        return False

    return any(word.startswith(prefix) for word in words for prefix in normalized_prefixes)
