from state.affix_mru import AffixMRU
from units.number_affix import AffixKind, NumberAffix


def test_push_evicts_oldest_per_kind() -> None:
    mru = AffixMRU(max_size=2)
    mru.push(AffixKind.CURRENCY, "$")
    mru.push(AffixKind.CURRENCY, "EUR")
    mru.push(AffixKind.CURRENCY, "GBP")
    assert mru.items(AffixKind.CURRENCY) == ["GBP", "EUR"]


def test_bootstrap_deduplicates_and_preserves_recency() -> None:
    tree = {
        "a": NumberAffix(AffixKind.CURRENCY, "$", False, 1),
        "b": NumberAffix(AffixKind.UNITS, "%", False, 2),
        "c": [
            NumberAffix(AffixKind.CURRENCY, "EUR", False, 3),
            NumberAffix(AffixKind.CURRENCY, "$", False, 4),
        ],
    }
    mru = AffixMRU(max_size=10)
    mru.bootstrap_from_tree(tree)

    assert mru.items(AffixKind.CURRENCY) == ["$", "EUR"]
    assert mru.items(AffixKind.UNITS) == ["%"]


def test_prefix_suffix_lists_are_independent() -> None:
    mru = AffixMRU(max_size=3)
    mru.push(AffixKind.CURRENCY, "$")
    mru.push(AffixKind.UNITS, "kg")
    mru.push(AffixKind.UNITS, "%")

    assert mru.items(AffixKind.CURRENCY) == ["$"]
    assert mru.items(AffixKind.UNITS) == ["%", "kg"]
