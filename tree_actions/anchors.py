"""Step 9 — Anchor-based move primitives.

A ``MoveAnchor`` describes *where* a block of items should land, by
reference to a non-moving sibling (or end-of-parent sentinel), instead
of a pre-pop / post-pop integer row index. The anchor is **path-based**
so it survives index invalidation across redo/undo cycles.

Translation rule from the legacy pre-pop ``target_row`` (kept for
backwards compatibility):

- ``target_row == rowCount(parent)`` → ``at_end`` of *parent*.
- otherwise → land **before** the sibling currently at ``target_row``.

This is correct because the pre-pop convention places the block in
the gap *just before* whatever currently occupies ``target_row``,
which is exactly what "before that sibling" describes.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QModelIndex


@dataclass(frozen=True)
class MoveAnchor:
    """Stable, path-based description of a destination gap.

    Exactly one of ``before_sibling_path`` or ``is_at_end`` describes
    the gap; the other is left at its default value. Use the
    ``anchor_before_index`` / ``anchor_at_end`` factories instead of
    instantiating this class directly.
    """

    parent_path: tuple[int, ...]
    before_sibling_path: tuple[int, ...] | None = None
    is_at_end: bool = False


def _index_path_from_tab(index: QModelIndex, tab) -> tuple[int, ...]:
    return tab.mutations.index_path(index)


def anchor_at_end(parent_index: QModelIndex, tab) -> MoveAnchor:
    """Anchor pointing at the *end* of ``parent_index``'s children list."""
    return MoveAnchor(parent_path=_index_path_from_tab(parent_index, tab), is_at_end=True)


def anchor_before_index(sibling_index: QModelIndex, tab) -> MoveAnchor:
    """Anchor pointing at the gap *immediately before* ``sibling_index``."""
    if not sibling_index.isValid():
        return anchor_at_end(QModelIndex(), tab)
    sibling_path = _index_path_from_tab(sibling_index, tab)
    parent_path = sibling_path[:-1]
    return MoveAnchor(parent_path=parent_path, before_sibling_path=sibling_path)


def anchor_after_index(sibling_index: QModelIndex, tab) -> MoveAnchor:
    """Anchor pointing at the gap *immediately after* ``sibling_index``.

    If ``sibling_index`` is the last child of its parent, returns
    ``at_end``. Otherwise returns ``before`` the next sibling.
    """
    if not sibling_index.isValid():
        return anchor_at_end(QModelIndex(), tab)
    sibling_path = _index_path_from_tab(sibling_index, tab)
    parent_path = sibling_path[:-1]
    parent_index = tab.mutations.index_from_path(parent_path)
    if sibling_index.row() + 1 >= tab.row_count(parent_index):
        return MoveAnchor(parent_path=parent_path, is_at_end=True)
    next_sibling_path = parent_path + (sibling_index.row() + 1,)
    return MoveAnchor(parent_path=parent_path, before_sibling_path=next_sibling_path)


# ---------------------------------------------------------------------------
# Resolution — anchor → (parent_index, insert_row) AFTER removing sources
# ---------------------------------------------------------------------------


def adjust_path_for_removed_sources(
    path: tuple[int, ...],
    source_paths: list[tuple[tuple[int, ...], int]],
) -> tuple[int, ...]:
    """Shift each index in *path* down by the number of *source_paths*
    that sat in the same ancestor (under the original tree) at a row
    strictly less than the corresponding index in *path*.

    This is required because anchor paths are captured **before** the
    move command detaches its sources. When a source sits in an ancestor
    of the anchor at row ``r`` and the anchor's index at that level is
    ``> r``, that anchor index has effectively shifted by one after the
    source is removed.

    Without this adjustment a drop ``OnItem`` of a sibling that lives
    *after* the dragged source would land in the WRONG container — the
    next sibling whose path slot was vacated by the detach. That bug
    manifests as "dragging element N onto element N+1 puts it into
    element N+2" with object/array drop targets.
    """
    adjusted: list[int] = []
    for depth, row in enumerate(path):
        prefix = tuple(path[:depth])
        shift = sum(1 for sp_parent, sp_row in source_paths if sp_parent == prefix and sp_row < row)
        adjusted.append(row - shift)
    return tuple(adjusted)


def resolve_anchor_target(
    model,
    tab,
    anchor: MoveAnchor,
    detached_source_paths: list[tuple[tuple[int, ...], int]],
) -> tuple[tuple[int, ...], int]:
    """Return the post-pop ``(parent_path, insert_row)`` for ``anchor``.

    Both halves of the anchor (``parent_path`` and ``before_sibling_path``)
    are adjusted via :func:`adjust_path_for_removed_sources` to keep the
    anchor stable across the source-removal step of ``_MoveRowsCmd.redo``.
    """
    adjusted_parent_path = adjust_path_for_removed_sources(anchor.parent_path, detached_source_paths)

    if anchor.is_at_end:
        parent_index = tab.mutations.index_from_path(adjusted_parent_path)
        return adjusted_parent_path, model.rowCount(parent_index)

    assert anchor.before_sibling_path is not None
    adjusted_sibling_path = adjust_path_for_removed_sources(anchor.before_sibling_path, detached_source_paths)
    if not adjusted_sibling_path:
        return adjusted_parent_path, 0
    return adjusted_parent_path, adjusted_sibling_path[-1]


def resolve_anchor_insert_row(
    model,
    tab,
    anchor: MoveAnchor,
    detached_source_paths: list[tuple[tuple[int, ...], int]],
) -> int:
    """Return only the post-pop ``insert_row`` for ``anchor``.

    Kept for backwards compatibility with callers that only need the
    row part. New code should call :func:`resolve_anchor_target` instead.
    """
    _parent_path, insert_row = resolve_anchor_target(model, tab, anchor, detached_source_paths)
    return insert_row


def pre_pop_target_row_to_anchor(
    tab,
    target_parent: QModelIndex,
    target_row: int,
) -> MoveAnchor:
    """Convert legacy ``(target_parent, pre_pop_target_row)`` to a ``MoveAnchor``.

    Used by the back-compat ``push_move_rows(sources, target_parent, target_row)``
    signature.
    """
    parent_path = tab.mutations.index_path(target_parent)
    n = tab.row_count(target_parent)
    if target_row >= n:
        return MoveAnchor(parent_path=parent_path, is_at_end=True)
    sibling_path = parent_path + (target_row,)
    return MoveAnchor(parent_path=parent_path, before_sibling_path=sibling_path)


# ---------------------------------------------------------------------------
# Cycle / no-op detection
# ---------------------------------------------------------------------------


def anchor_is_cycle(
    anchor: MoveAnchor,
    source_paths: list[tuple[tuple[int, ...], int]],
) -> bool:
    """``True`` when any source would become an ancestor of the destination
    parent. Cheap path-prefix check."""
    parent_path = anchor.parent_path
    for src_parent_path, src_row in source_paths:
        full_src_path = src_parent_path + (src_row,)
        if parent_path[: len(full_src_path)] == full_src_path:
            return True
    return False


def anchor_is_no_op(
    anchor: MoveAnchor,
    source_paths: list[tuple[tuple[int, ...], int]],
) -> bool:
    """``True`` when applying ``anchor`` to ``source_paths`` would not
    change the tree layout.

    A move is a no-op iff the resulting (parent, row) of every source
    equals its current (parent, row). The simplest sufficient case is:
    all sources share ``anchor.parent_path`` AND form a contiguous block
    whose final landing slot equals their current slot.
    """
    parent_path = anchor.parent_path
    if not all(p == parent_path for p, _r in source_paths):
        return False

    src_rows_asc = sorted(r for _p, r in source_paths)
    # Detect contiguous block
    is_contiguous = all(b - a == 1 for a, b in zip(src_rows_asc, src_rows_asc[1:]))
    if not is_contiguous:
        return False

    n_sources = len(src_rows_asc)
    first_src = src_rows_asc[0]
    last_src = src_rows_asc[-1]

    if anchor.is_at_end:
        # "at_end" means "after the current last sibling that is NOT a source."
        # Therefore a no-op iff the contiguous block is already the suffix.
        # We don't know rowCount here without the model — handled by caller's
        # post-resolution check.
        return False  # let caller decide via resolved row

    assert anchor.before_sibling_path is not None
    if not anchor.before_sibling_path:
        return False
    sibling_row = anchor.before_sibling_path[-1]
    # If sibling_row is exactly last_src + 1, the block already lands "before"
    # that sibling — no movement.
    if sibling_row == last_src + 1:
        return True
    # If sibling_row equals first_src, also no-op (insertion before "self").
    if sibling_row == first_src:
        return True
    return False
