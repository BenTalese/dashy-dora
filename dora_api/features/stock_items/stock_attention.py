"""The canonical "does this stock item need attention?" rule.

Chunk 3b of `docs/04_proposals/IMPL_PLAN_STOCK_SIGNAL_CONSOLIDATION.md`, built
on the Step-0 answers. **One engine, server-side.** Before this, the rule
existed twice — once here as alert kinds, once in the client's
`useStockFilters.hasAlert` — and the copies disagreed in four documented ways:

  - **B1** the client hardcoded a 7-day expiring-soon window while the server
    read the configurable one, so changing the setting moved the bell and not
    the row outlines;
  - **B2** per-user `AlertPreference` was honoured by the bell and ignored by
    the rows, so disabling a kind half-worked;
  - **B3** the alerts page deep-linked to `/stock?attention=true`, a filter
    running a *different* rule than the count that was tapped;
  - **B4** non-essential out-of-stock was an actionable alert server-side and a
    dimmed row client-side — "act on this" and "ignore this" at once.

All four are the same defect: two rules for one idea. The fix is not to sync
them, it's to have one. This module is it, and `get_alerts.py` emits its three
per-item kinds from the very same predicates below — so a row's outline and the
bell's badge cannot describe different sets.

**What the rule says** (Step-0 Q1; the conditions, in severity order):

    expired          — past its expiry date                          high
    essential_low    — flagged essential AND low or out              high
    expiring_soon    — within the household's configurable window    medium

Nothing else. A non-essential item that is low or out does **not** need
attention: the row's own level band already says so, and the owner's rule for
this whole pass is *"we want people to actually pay attention when there's a
notification."* Non-essential + out still dims and sorts to the bottom (D-8) —
that's a treatment read off the level, not an alert.

The rule is evaluated **for a requesting user**, because a user can disable a
kind (`AlertPreference.enabled`) and that has to hold everywhere, not just in
the bell.

**Urgency rank** (owner call 2026-08-21). `severity` is too coarse to order the
outlined band: `expired` and `essential_low` are both `high`, so the overview's
"Needs attention" sort fell straight through to alphabetical and looked random —
an expired jar could sit below an essential that was merely low, because its
name started later. `rank` is the tiebreak, most urgent first:

    0  expired            — already gone off; the only one you can't undo
    1  essential, OUT     — you said you always want it and there is none
    2  expiring soon      — a deadline, but days of slack
    3  essential, LOW     — you can still cook; buy it on the next shop

Out beats low for essentials, and both halves of `essential_low` straddle
"expiring soon", which is why this can't be derived from the kind alone. Ranking
here rather than in the client keeps it beside the predicates it reads (R-003) —
the client sorts on the number and owns none of the meaning.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable
from uuid import UUID

from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.entities.stock_level import StockLevel
from dora_api.domain.stock_status import is_low_stock, is_out_of_stock
from dora_api.features.alerts.alert_kinds import (SEVERITY_BY_KIND,
                                                  SEVERITY_ORDER)

KIND_EXPIRED = "expired"
KIND_EXPIRING_SOON = "expiring_soon"
KIND_ESSENTIAL_LOW = "essential_low"


def is_expired(item: StockItem, today: date) -> bool:
    return item.expiry_date is not None and item.expiry_date < today


def is_expiring_soon(item: StockItem, today: date, window_days: int) -> bool:
    """Within the window and not already past it. `window_days` is the
    household setting — never a literal at the call site (B1)."""
    if item.expiry_date is None:
        return False
    days_remaining = (item.expiry_date - today).days
    return 0 <= days_remaining <= window_days


def is_essential_low(item: StockItem, level: StockLevel | None) -> bool:
    """Essential and either low or out. One kind, deliberately: the user
    flagged it, so both bands mean the same thing — go and restock.

    The level is passed in, resolved by FK (`_level_access`), never read off
    `item.stock_level`: that relationship is noload and can come back unset
    even after an `.include()` (R-032; FU-684)."""
    if not item.is_essential or level is None:
        return False
    return is_low_stock(level) or is_out_of_stock(level)


# Urgency ranks — see the module docstring. `essential_low` splits in two
# because "out" and "low" are the same kind but not the same urgency.
RANK_EXPIRED = 0
RANK_ESSENTIAL_OUT = 1
RANK_EXPIRING_SOON = 2
RANK_ESSENTIAL_LOW = 3
# Sorts below every firing rank, for items where nothing fired.
RANK_NONE = 9


@dataclass(frozen=True, slots=True)
class Attention:
    """One item's attention state. `severity` is the worst firing kind's;
    `rank` orders the outlined band most-urgent-first (D-9) — severity alone
    ties `expired` with `essential_low`."""
    needs_attention: bool
    severity: str | None
    kinds: tuple[str, ...]
    rank: int = RANK_NONE


_NONE = Attention(needs_attention=False, severity=None, kinds=(), rank=RANK_NONE)


def _rank_for(level: StockLevel | None, kinds: list[str]) -> int:
    """The worst (lowest) rank among the kinds that actually fired."""
    ranks: list[int] = []
    for kind in kinds:
        if kind == KIND_EXPIRED:
            ranks.append(RANK_EXPIRED)
        elif kind == KIND_EXPIRING_SOON:
            ranks.append(RANK_EXPIRING_SOON)
        elif kind == KIND_ESSENTIAL_LOW:
            ranks.append(
                RANK_ESSENTIAL_OUT
                if is_out_of_stock(level)
                else RANK_ESSENTIAL_LOW
            )
    return min(ranks) if ranks else RANK_NONE


def attention_for(
    item: StockItem,
    level: StockLevel | None,
    *,
    today: date,
    window_days: int,
    disabled_kinds: frozenset[str] = frozenset(),
) -> Attention:
    kinds: list[str] = []
    if is_expired(item, today):
        kinds.append(KIND_EXPIRED)
    elif is_expiring_soon(item, today, window_days):
        # `elif`: an expired item is not also "expiring soon". The two are
        # points on one axis, and emitting both would double-count the item in
        # any per-kind tally.
        kinds.append(KIND_EXPIRING_SOON)
    if is_essential_low(item, level):
        kinds.append(KIND_ESSENTIAL_LOW)

    kinds = [k for k in kinds if k not in disabled_kinds]
    if not kinds:
        return _NONE

    worst = min(kinds, key=lambda k: SEVERITY_ORDER[SEVERITY_BY_KIND[k]])
    return Attention(
        needs_attention=True,
        severity=SEVERITY_BY_KIND[worst],
        kinds=tuple(kinds),
        rank=_rank_for(level, kinds),
    )


def resolve_attention_map(
    items: Iterable[StockItem],
    levels_by_item: dict[UUID, StockLevel | None],
    *,
    today: date,
    window_days: int,
    disabled_kinds: frozenset[str] = frozenset(),
) -> dict[UUID, Attention]:
    """Bulk form — one pass, no per-item queries. Mirrors the shape of
    `resolve_overdue_map` so the two bulk resolvers read alike."""
    return {
        item.id: attention_for(
            item, levels_by_item.get(item.id), today=today, window_days=window_days,
            disabled_kinds=disabled_kinds,
        )
        for item in items
    }
