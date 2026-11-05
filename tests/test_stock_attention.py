"""Unit tests for the canonical attention rule
(`features/stock_items/stock_attention.py`).

This is the rule Chunk 3b made single-source: the stock row's outline, the
overview's "Needs attention" count and filter, and the bell's three per-item
alert kinds all read it. It's pure and load-bearing for all of those, so it's
pinned here directly rather than re-derived from each caller's tests.

Every case below is a defect the plan named. The B-numbers are from
`IMPL_PLAN_STOCK_SIGNAL_CONSOLIDATION.md` §1.1.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest

from dora_api.domain.entities.stock_level import StockLevel
from dora_api.features.stock_items.stock_attention import (RANK_ESSENTIAL_LOW,
                                                           RANK_ESSENTIAL_OUT,
                                                           RANK_EXPIRED,
                                                           RANK_EXPIRING_SOON,
                                                           RANK_NONE,
                                                           attention_for,
                                                           resolve_attention_map)

TODAY = date(2026, 8, 20)
DEFAULT_WINDOW = 7

STOCKED = StockLevel(name="Stocked", sequence=0)
LOW = StockLevel(name="Low Stock", sequence=1)
OUT = StockLevel(name="Out of Stock", sequence=2)


@dataclass
class _Item:
    """Duck-typed StockItem — the rule reads exactly these four attributes,
    and the real entity needs five unrelated constructor arguments that say
    nothing about attention."""
    stock_level: StockLevel = field(default_factory=lambda: STOCKED)
    is_essential: bool = False
    expiry_date: date | None = None
    id: UUID = field(default_factory=uuid4)


def _item(*, level=STOCKED, essential=False, expiry=None) -> _Item:
    return _Item(stock_level=level, is_essential=essential, expiry_date=expiry)


def _attention(item, *, window=DEFAULT_WINDOW, disabled=frozenset()):
    return attention_for(
        item, item.stock_level, today=TODAY, window_days=window, disabled_kinds=disabled,
    )


# ── what fires ──────────────────────────────────────────────────────────

def test__healthy_item__no_attention():
    assert _attention(_item()).needs_attention is False


def test__expired__is_high():
    a = _attention(_item(expiry=TODAY - timedelta(days=1)))
    assert a.needs_attention is True
    assert a.severity == "high"
    assert a.kinds == ("expired",)


def test__expiring_within_window__is_medium():
    a = _attention(_item(expiry=TODAY + timedelta(days=3)))
    assert a.severity == "medium"
    assert a.kinds == ("expiring_soon",)


def test__expires_today__still_counts_as_expiring_not_expired():
    """The boundary the two predicates share. Off-by-one here means an item
    flips between two different messages on its last usable day."""
    assert _attention(_item(expiry=TODAY)).kinds == ("expiring_soon",)


def test__expiry_beyond_window__is_silent():
    assert _attention(
        _item(expiry=TODAY + timedelta(days=8))
    ).needs_attention is False


@pytest.mark.parametrize("level", [LOW, OUT])
def test__essential_low_or_out__is_high(level):
    """One kind for both bands: the user flagged the item, so low and out
    both mean 'go and restock'."""
    a = _attention(_item(level=level, essential=True))
    assert a.severity == "high"
    assert a.kinds == ("essential_low",)


@pytest.mark.parametrize("level", [LOW, OUT])
def test__non_essential_low_or_out__is_NOT_attention(level):
    """Step-0 Q1 + B4. This is the case that used to be an actionable alert
    server-side while the row dimmed it — 'act on this' and 'ignore this' at
    once. The level band already says it; attention stays quiet."""
    assert _attention(_item(level=level)).needs_attention is False


# ── the configurable window (B1) ────────────────────────────────────────

def test__window_is_the_households_not_a_hardcoded_seven():
    """B1: the client hardcoded 7 days while the server read the setting, so
    changing it moved the bell and left the row outlines behind. A 10-day-out
    item is silent at the default and loud at a 14-day window."""
    item = _item(expiry=TODAY + timedelta(days=10))
    assert _attention(item).needs_attention is False
    assert _attention(item, window=14).kinds == ("expiring_soon",)


# ── per-user disabled kinds (B2) ────────────────────────────────────────

def test__disabled_kind__stops_firing_for_that_user():
    """B2: `AlertPreference` was honoured by the bell and ignored by the rows.
    The rule takes the disabled set, so one answer holds everywhere."""
    item = _item(expiry=TODAY - timedelta(days=1))
    assert _attention(item, disabled=frozenset({"expired"})).needs_attention is False


def test__disabling_one_of_two_kinds__leaves_the_other():
    item = _item(level=OUT, essential=True, expiry=TODAY - timedelta(days=1))
    assert set(_attention(item).kinds) == {"expired", "essential_low"}

    remaining = _attention(item, disabled=frozenset({"expired"}))
    assert remaining.kinds == ("essential_low",)
    assert remaining.severity == "high"


# ── severity roll-up ────────────────────────────────────────────────────

def test__several_kinds__severity_is_the_worst_one():
    """The overview sorts on this within the outlined band (D-9), so it has to
    be the worst firing kind, not the first or last one evaluated."""
    item = _item(level=LOW, essential=True, expiry=TODAY + timedelta(days=2))
    a = _attention(item)
    assert set(a.kinds) == {"expiring_soon", "essential_low"}
    assert a.severity == "high"  # essential_low outranks expiring_soon


def test__expired_and_expiring__are_never_both_emitted():
    """They're points on one axis; emitting both would double-count the item
    in any per-kind tally."""
    a = _attention(_item(expiry=TODAY - timedelta(days=30)))
    assert a.kinds == ("expired",)


# ── bulk form ───────────────────────────────────────────────────────────

def test__resolve_attention_map__keys_every_item_including_the_quiet_ones():
    """A missing key would read as a KeyError at the DTO hydration site, not
    as 'no attention' — every item gets an entry."""
    quiet = _item()
    loud = _item(expiry=TODAY - timedelta(days=1))
    result = resolve_attention_map(
        [quiet, loud], {i.id: i.stock_level for i in (quiet, loud)},
        today=TODAY, window_days=DEFAULT_WINDOW,
    )
    assert set(result) == {quiet.id, loud.id}
    assert result[quiet.id].needs_attention is False
    assert result[loud.id].needs_attention is True


# ── urgency rank ────────────────────────────────────────────────────────
#
# Added 2026-08-21. Severity ties `expired` with `essential_low` (both "high"),
# so the overview's "Needs attention" sort fell through to the alphabet and
# read as random. `rank` is what orders the outlined band.

def test__rank__orders_most_urgent_first():
    """The whole ordering, in one assertion, because the ORDER is the contract
    — any one rank in isolation says nothing."""
    expired = _attention(_item(expiry=TODAY - timedelta(days=1)))
    essential_out = _attention(_item(level=OUT, essential=True))
    expiring = _attention(_item(expiry=TODAY + timedelta(days=2)))
    essential_low = _attention(_item(level=LOW, essential=True))

    assert [
        expired.rank, essential_out.rank, expiring.rank, essential_low.rank,
    ] == [RANK_EXPIRED, RANK_ESSENTIAL_OUT, RANK_EXPIRING_SOON, RANK_ESSENTIAL_LOW]
    assert expired.rank < essential_out.rank < expiring.rank < essential_low.rank


def test__rank__splits_essential_low_by_out_vs_low():
    """One kind, two urgencies: `essential_low` covers both bands, and an
    essential you have NONE of is worse than one you're merely low on. This is
    why the rank can't be derived from the kind alone."""
    out = _attention(_item(level=OUT, essential=True))
    low = _attention(_item(level=LOW, essential=True))
    assert out.kinds == low.kinds == ("essential_low",)
    assert out.rank < low.rank


def test__rank__is_the_worst_of_several_firing_kinds():
    item = _item(level=LOW, essential=True, expiry=TODAY - timedelta(days=1))
    a = _attention(item)
    assert set(a.kinds) == {"expired", "essential_low"}
    assert a.rank == RANK_EXPIRED


def test__rank__ignores_a_kind_the_user_disabled():
    """Same rule as severity: a muted kind isn't allowed to set the order of a
    row it no longer contributes to."""
    item = _item(level=LOW, essential=True, expiry=TODAY - timedelta(days=1))
    a = _attention(item, disabled=frozenset({"expired"}))
    assert a.rank == RANK_ESSENTIAL_LOW


def test__rank__sorts_quiet_items_below_every_firing_rank():
    a = _attention(_item())
    assert a.needs_attention is False
    assert a.rank == RANK_NONE
    assert RANK_NONE > RANK_ESSENTIAL_LOW
