"""Canonical stock-status authority.

The single server-side source of truth for what a stock level *means* and the
related freshness windows. Status is keyed to the level's ordinal ``sequence``,
**never** its display name — renaming a level's label in the UI must not change
behaviour. Every feature that buckets, derives, or assigns stock status consumes
this module; no other code may compare a stock-level name or hardcode a bare
sequence literal.

Seeded sequences (see ``persistence/seed.py`` / the initial migration):
0 Stocked, 1 Low Stock, 2 Out of Stock.

The middle "Sufficient Stock" band was axed 2026-07-02 — it was semantically
dead (no predicate discriminated it) and clashed with P8-07 Zero-Input Pantry's
charter-mandated three-band inference (Out/Low/Stocked). Data migration in
alembic revision ``a1c7d9e42be0`` collapses any Sufficient rows into Stocked
and reseries Low/Out. Downstream code always used ``level_for_status`` /
``needs_restock`` / ``is_low_stock`` / ``is_missing`` predicates, so nothing
functional was lost.

"Missing" semantics (used for ingredient cookability): out-of-stock **only** — a
low-stock ingredient you can usually still cook with.

Freshness window: ``EXPIRING_SOON_WINDOW_DAYS`` colocates here because the
contract owns thresholds, not only level→bucket mapping (impl plan §1 Chunk 1).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable, Optional


class StockStatus(IntEnum):
    """Stock-level roles, ordered worst-last by ``sequence``."""
    STOCKED = 0
    LOW_STOCK = 1
    OUT_OF_STOCK = 2


# Readable aliases for the canonical sequence values. Prefer the predicates
# below to bare comparisons; these exist for the few ordinal cases.
STOCKED_SEQUENCE = int(StockStatus.STOCKED)
LOW_STOCK_SEQUENCE = int(StockStatus.LOW_STOCK)
OUT_OF_STOCK_SEQUENCE = int(StockStatus.OUT_OF_STOCK)

# Days from "today" within which an item is considered "expiring soon" for alerts,
# location attention scores, and the assistant's expiring-soon filter. Single
# source — do not redeclare a 7 elsewhere. Since C-9.2 this is the *default*;
# an admin can override it household-wide via AppSetting.expiring_soon_window_days
# (resolve through `effective_expiring_soon_window`, never a second literal).
EXPIRING_SOON_WINDOW_DAYS = 7


def effective_expiring_soon_window(app_setting) -> int:  # noqa: ANN001 — duck-typed AppSetting
    """The configured expiring-soon window (days), falling back to
    ``EXPIRING_SOON_WINDOW_DAYS`` when unset/invalid (C-9.2).

    Single source (R-003): callers pass the already-fetched ``AppSetting`` (or
    ``None``) so this module stays repository-free, and the constant above
    remains the one default the override layers on top of.
    """
    if app_setting is not None:
        value = getattr(app_setting, "expiring_soon_window_days", None)
        if isinstance(value, int) and value > 0:
            return value
    return EXPIRING_SOON_WINDOW_DAYS


@dataclass(frozen=True, slots=True)
class ObservedUnitCost:
    """A per-unit cost together with the unit it is *per*.

    ``item_price`` is the price of one countable thing in the purchase, when
    the observation says how many there were ("$5.50 for 12 eggs, 700 g").
    """
    amount: float
    unit: str
    item_price: float | None = None


def get_stock_item_unit_cost_with_unit_at(observations, when=None):  # noqa: ANN001 — duck-typed observations
    """The single server-owned per-unit cost for a stock item (R-003): the
    folded ``total_price / total_measure`` of the most recent observation at
    or before ``when`` (default: latest), with the unit it is per. ``None``
    when there's no usable observation. Pure: the caller passes
    already-fetched observations.

    The unit travels with the amount because the recipe cost estimator has to
    know whether "$4.20" means per litre or per bottle before it multiplies an
    ingredient quantity by it; dropping it is what produced a $1590
    two-ingredient recipe. For a normalised baseline across mixed units use
    ``build_your_prices_for_item``.
    """
    candidates = [
        o for o in observations
        if getattr(o, "total_measure", 0) and (when is None or o.observed_at <= when)
    ]
    if not candidates:
        return None
    latest = max(candidates, key=lambda o: o.observed_at)
    if not latest.total_measure:
        return None
    pack_count = getattr(latest, "pack_count", None)
    return ObservedUnitCost(
        amount=latest.total_price / latest.total_measure,
        unit=latest.unit,
        item_price=latest.total_price / pack_count if pack_count else None,
    )


def _sequence_of(level) -> Optional[int]:
    if level is None:
        return None
    return getattr(level, "sequence", None)


def status_for(level) -> Optional[StockStatus]:
    """The :class:`StockStatus` for a stock level, or ``None`` if unknown.

    A sequence at or beyond the worst defined value clamps to OUT_OF_STOCK so a
    future-inserted level never silently reads as "no status".
    """
    seq = _sequence_of(level)
    if seq is None:
        return None
    if seq >= OUT_OF_STOCK_SEQUENCE:
        return StockStatus.OUT_OF_STOCK
    try:
        return StockStatus(seq)
    except ValueError:
        return None


def is_out_of_stock(level) -> bool:
    seq = _sequence_of(level)
    return seq is not None and seq >= OUT_OF_STOCK_SEQUENCE


def is_low_stock(level) -> bool:
    """Exactly the Low-Stock band — not out-of-stock."""
    return _sequence_of(level) == LOW_STOCK_SEQUENCE


def needs_restock(level) -> bool:
    """At or below the low-stock threshold (low **or** out)."""
    seq = _sequence_of(level)
    return seq is not None and seq >= LOW_STOCK_SEQUENCE


def is_missing(level) -> bool:
    """Whether an ingredient counts as missing for cookability.

    A ``None`` level (no stock record) counts as missing; otherwise out-of-stock
    only — see the module "Missing semantics" note.
    """
    return is_missing_sequence(_sequence_of(level))


def is_missing_sequence(sequence: Optional[int]) -> bool:
    """`is_missing` for a recorded level known only by its sequence."""
    return sequence is None or sequence >= OUT_OF_STOCK_SEQUENCE


def level_for_status(levels: Iterable, status: StockStatus):
    """Return the level in ``levels`` whose sequence matches ``status``, else ``None``.

    Pure: the caller owns the DB round-trip and passes the already-fetched levels.
    Use this instead of looking a level up by name to assign it.
    """
    target = int(status)
    for level in levels:
        if getattr(level, "sequence", None) == target:
            return level
    return None
