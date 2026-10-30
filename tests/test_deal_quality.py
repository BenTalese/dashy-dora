"""FU-450 — deal-quality compute unit tests.

Every test drives the pure :func:`compute_deal_quality` with fixture
lists — no DB, no HTTP. The repo-touching :func:`get_deal_quality` is a
thin walk (product offers + household observations) covered by browser
verify end-to-end.

Design lock: `docs/04_proposals/PROPOSAL_BUDGET_DEFENSE_SWAPS.md` §4a.
"""
from dora_api.features.deals.deal_quality import compute_deal_quality


def test__no_current_price__returns_none():
    assert compute_deal_quality(None, False, [1.0, 2.0], []) is None


def test__no_window_history__returns_none():
    assert compute_deal_quality(3.00, False, [], []) is None


def test__current_is_cheapest_in_window__great_band_is_lowest():
    # Current 2.00 is the min of the window → percentile 1.0 → great.
    dq = compute_deal_quality(
        current_price=2.00,
        offer_claims_saving=False,
        window_prices=[2.00, 3.00, 3.50, 4.00, 3.20],
        household_unit_paid_prices=[],
    )
    assert dq is not None
    assert dq.is_lowest_in_window is True
    assert dq.percentile == 1.0
    assert dq.band == "great"
    assert dq.lowest_price == 2.00
    assert dq.highest_price == 4.00


def test__current_is_most_expensive__poor_band():
    dq = compute_deal_quality(
        current_price=4.00,
        offer_claims_saving=False,
        window_prices=[2.00, 3.00, 3.50, 4.00, 3.20],
        household_unit_paid_prices=[],
    )
    assert dq is not None
    assert dq.is_lowest_in_window is False
    # Only the 4.00 itself is >= 4.00 → 1/5 = 0.2 → poor.
    assert dq.percentile == 0.2
    assert dq.band == "poor"


def test__band_boundaries_track_percentile():
    # Ten evenly-spaced prices 1.0..10.0; pick a current so a known
    # fraction sit at-or-above it.
    window = [float(n) for n in range(1, 11)]
    # current 3.0 → prices >= 3.0 are {3..10} = 8/10 = 0.8 → good.
    good = compute_deal_quality(3.0, False, window, [])
    assert good is not None and good.percentile == 0.8 and good.band == "good"
    # current 5.0 → {5..10} = 6/10 = 0.6 → fair.
    fair = compute_deal_quality(5.0, False, window, [])
    assert fair is not None and fair.percentile == 0.6 and fair.band == "fair"
    # current 7.0 → {7..10} = 4/10 = 0.4 → poor.
    poor = compute_deal_quality(7.0, False, window, [])
    assert poor is not None and poor.percentile == 0.4 and poor.band == "poor"


def test__fake_markdown__claims_saving_but_household_paid_less():
    # Merchant claims a special (was > now), but the household's median
    # paid unit price (1.50) is below the current unit price (2.00) →
    # the "deal" isn't cheaper than what they normally pay → fake.
    dq = compute_deal_quality(
        current_price=2.00,
        offer_claims_saving=True,
        window_prices=[2.00, 3.00, 3.50],  # cheapest in window
        household_unit_paid_prices=[1.40, 1.50, 1.60],
        current_unit_price=2.00,
    )
    assert dq is not None
    assert dq.fake_markdown is True
    # Even though it's the lowest in the window, a fake markdown clamps to poor.
    assert dq.is_lowest_in_window is True
    assert dq.band == "poor"


def test__genuine_special__cheaper_than_household_median_not_fake():
    dq = compute_deal_quality(
        current_price=2.00,
        offer_claims_saving=True,
        window_prices=[2.00, 3.00, 3.50],
        household_unit_paid_prices=[2.50, 2.80, 3.00],
        current_unit_price=2.00,
    )
    assert dq is not None
    assert dq.fake_markdown is False
    assert dq.band == "great"


def test__no_household_history__never_flags_fake_markdown():
    # No ground truth ⇒ can't assert dishonesty (Charter P8 — never invent one).
    dq = compute_deal_quality(
        current_price=2.00,
        offer_claims_saving=True,
        window_prices=[2.00, 3.00, 3.50],
        household_unit_paid_prices=[],
        current_unit_price=2.00,
    )
    assert dq is not None
    assert dq.fake_markdown is False


def test__no_claimed_saving__never_fake_even_if_pricey():
    # Everyday price (no "was") can't be a fake markdown by definition.
    dq = compute_deal_quality(
        current_price=5.00,
        offer_claims_saving=False,
        window_prices=[2.00, 3.00, 5.00],
        household_unit_paid_prices=[1.00, 1.20],
        current_unit_price=5.00,
    )
    assert dq is not None
    assert dq.fake_markdown is False


def test__unit_price_used_for_fake_markdown_comparison():
    # Pack price 8.00 but per-unit 2.00 (4-unit pack); household pays 2.50/unit.
    # Compared per-unit, 2.00 < 2.50 → genuine, not fake.
    dq = compute_deal_quality(
        current_price=8.00,
        offer_claims_saving=True,
        window_prices=[8.00, 9.00, 10.00],
        household_unit_paid_prices=[2.40, 2.50, 2.60],
        current_unit_price=2.00,
    )
    assert dq is not None
    assert dq.fake_markdown is False


# ── Unit basis + window double-count (repo-layer helpers, still pure) ────

from datetime import datetime, timezone
from types import SimpleNamespace

from dora_api.features.deals.deal_quality import (household_unit_prices_like,
                                                  window_offer_prices)
from dora_api.features.stock_items.your_prices import per_unit_in_canonical


def test__no_product_unit_basis__never_flags_fake_markdown():
    # A product whose size can't be put on a per-unit basis used to compare
    # its PACK price (8.00) against the household PER-UNIT median (2.50) and
    # read a genuine special as fake/poor.
    dq = compute_deal_quality(
        current_price=8.00,
        offer_claims_saving=True,
        window_prices=[8.00, 9.00, 10.00],
        household_unit_paid_prices=[2.40, 2.50, 2.60],
        current_unit_price=None,
    )
    assert dq is not None
    assert dq.fake_markdown is False
    assert dq.band == "great"


def test__household_prices_are_converted_to_the_product_canonical_unit():
    # Product: $3.00 for 500 g → $6.00/kg. Household paid $4.00 for 1 kg
    # ($4.00/kg) and $0.90 for 200 g ($4.50/kg) — both comparable once in kg.
    # A 2 L milk observation is another dimension and must be dropped.
    product = per_unit_in_canonical(total_price=3.00, total_measure=500, unit="g")
    assert product is not None and product[1] == "kg"
    observations = [
        SimpleNamespace(total_price=4.00, total_measure=1, unit="kg"),
        SimpleNamespace(total_price=0.90, total_measure=200, unit="g"),
        SimpleNamespace(total_price=3.00, total_measure=2, unit="L"),
    ]
    prices = household_unit_prices_like(product, observations)
    assert sorted(round(p, 2) for p in prices) == [4.00, 4.50]
    # No product basis ⇒ nothing comparable.
    assert household_unit_prices_like(None, observations) == []


def test__window_prices_skip_the_historic_row_that_is_the_current_offer():
    now = datetime(2026, 10, 1, tzinfo=timezone.utc)
    current = SimpleNamespace(price_now=2.00, offered_on=now)
    historic = [
        # Same instant + price as current: the offer-append copy. Read back
        # naive (SQLite) — still the same instant.
        SimpleNamespace(price_now=2.00, offered_on=now.replace(tzinfo=None)),
        SimpleNamespace(price_now=3.00, offered_on=datetime(2026, 9, 1, tzinfo=timezone.utc)),
        # Outside the window.
        SimpleNamespace(price_now=9.00, offered_on=datetime(2025, 1, 1, tzinfo=timezone.utc)),
    ]
    horizon = datetime(2026, 7, 1, tzinfo=timezone.utc)
    assert window_offer_prices(current, historic, horizon) == [2.00, 3.00]
