"""P8-07 — Zero-Input Pantry belief-inference unit tests.

Every test drives the pure `compute_belief` with a fixture `BeliefInputs`
— no DB, no HTTP — so the inference rules can be pinned in isolation. The
`gather_*` layer is a thin repo walk; browser-verify + the e2e suite cover
it end-to-end.

Coverage mirrors the P8-07 DONE-WHEN list:
  • belief updates from each signal (purchases, cooking, time)
  • time-decay of confidence
  • override precedence (a fresh check wins)
  • coarse bands, never a confident wrong answer on thin data
"""
from datetime import date, timedelta

from dora_api.domain.stock_status import (LOW_STOCK_SEQUENCE,
                                          OUT_OF_STOCK_SEQUENCE,
                                          STOCKED_SEQUENCE)
from dora_api.features.stock_items.pantry_belief import (BeliefInputs,
                                                         compute_belief)


_TODAY = date(2026, 7, 3)


def _d(days_ago: int) -> date:
    return _TODAY - timedelta(days=days_ago)


def _fortnightly_purchases(last_bought_days_ago: int, n: int = 6) -> list[date]:
    """n purchases spaced ~14 days apart, most recent `last_bought_days_ago`."""
    return sorted(_d(last_bought_days_ago + 14 * i) for i in range(n))


def _inputs(**overrides) -> BeliefInputs:
    base = BeliefInputs(
        recorded_sequence=STOCKED_SEQUENCE,
        stock_level_last_updated=_d(30),
        last_checked_at=None,
        purchase_dates=_fortnightly_purchases(30),
        consumption_dates=[],
        today=_TODAY,
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


# ── Purchase cadence drives the band ────────────────────────────────────

def test__fresh_purchase__believed_stocked():
    # Bought 2 days ago on a ~14-day cadence → well within a cycle. The
    # level itself hasn't been touched recently (updated 30d ago, default),
    # so this exercises the cadence inference path — not the fresh-hard-read
    # override.
    belief = compute_belief(_inputs(
        purchase_dates=_fortnightly_purchases(2),
    ))
    assert belief.believed_sequence == STOCKED_SEQUENCE
    assert belief.believed_band == "stocked"
    assert belief.is_inferred is True


def test__near_cycle_end__believed_low():
    # ~12 days into a ~14-day cycle → past the low cut (0.75) but not out.
    belief = compute_belief(_inputs(
        purchase_dates=_fortnightly_purchases(12),
        stock_level_last_updated=_d(60),
    ))
    assert belief.believed_sequence == LOW_STOCK_SEQUENCE
    assert belief.believed_band == "low"


def test__well_past_cycle__believed_out():
    # ~20 days into a ~14-day cycle → past the out cut (1.15).
    belief = compute_belief(_inputs(
        purchase_dates=_fortnightly_purchases(20),
        stock_level_last_updated=_d(60),
    ))
    assert belief.believed_sequence == OUT_OF_STOCK_SEQUENCE
    assert belief.believed_band == "out"


# ── Cooking accelerates depletion (the P6-07 signal) ────────────────────

def test__cooking_shifts_prediction_earlier():
    # Same purchase history; cooking with it since the last buy should push
    # the belief to a more-depleted band than buying alone would.
    bought_only = compute_belief(_inputs(
        purchase_dates=_fortnightly_purchases(8),
        consumption_dates=[],
        stock_level_last_updated=_d(60),
    ))
    also_cooked = compute_belief(_inputs(
        purchase_dates=_fortnightly_purchases(8),
        consumption_dates=[_d(6), _d(4), _d(1)],  # cooked 3× since the buy
        stock_level_last_updated=_d(60),
    ))
    # Run-out prediction demonstrably shifts when cooked vs only bought.
    assert also_cooked.believed_sequence >= bought_only.believed_sequence
    assert also_cooked.believed_sequence > bought_only.believed_sequence
    assert "cooked with" in also_cooked.reason


# ── Override precedence: a fresh check wins ─────────────────────────────

def test__recent_check_pins_to_recorded_high_confidence():
    # The purchase history alone would say "out"; a check today overrides.
    belief = compute_belief(_inputs(
        recorded_sequence=STOCKED_SEQUENCE,
        last_checked_at=_TODAY,
        purchase_dates=_fortnightly_purchases(40),  # long overdue on cadence
    ))
    assert belief.believed_sequence == STOCKED_SEQUENCE
    assert belief.confidence_band == "high"
    assert belief.is_inferred is False
    assert belief.differs_from_recorded is False
    assert "confirmed" in belief.reason.lower()


def test__stale_check_does_not_override():
    # A check 40 days ago is not "fresh" — inference takes over again.
    belief = compute_belief(_inputs(
        recorded_sequence=STOCKED_SEQUENCE,
        last_checked_at=_d(40),
        purchase_dates=_fortnightly_purchases(20),
        stock_level_last_updated=_d(40),
    ))
    assert belief.is_inferred is True
    assert belief.believed_sequence == OUT_OF_STOCK_SEQUENCE


# ── Time decay of confidence ────────────────────────────────────────────

def test__confidence_decays_with_extrapolation():
    near = compute_belief(_inputs(purchase_dates=_fortnightly_purchases(2)))
    far = compute_belief(_inputs(purchase_dates=_fortnightly_purchases(26)))
    assert near.confidence > far.confidence


# ── Coarse + honest on thin data ────────────────────────────────────────

def test__thin_history__low_confidence_never_confident_wrong():
    # A single purchase → no cadence to project; lean on recorded, but stay
    # humble.
    belief = compute_belief(_inputs(
        purchase_dates=[_d(45)],
        stock_level_last_updated=_d(45),
        recorded_sequence=STOCKED_SEQUENCE,
    ))
    assert belief.is_inferred is True
    assert belief.confidence_band in ("low", "medium")
    assert belief.confidence < 0.66


def test__no_data_at_all__not_sure():
    belief = compute_belief(BeliefInputs(
        recorded_sequence=None,
        stock_level_last_updated=None,
        last_checked_at=None,
        purchase_dates=[],
        consumption_dates=[],
        today=_TODAY,
    ))
    assert belief.confidence_band == "low"
    assert "not sure" in belief.reason.lower()


def test__inference_disagreeing_with_recorded_flags_differs():
    # Recorded says stocked, cadence says out → differs flag drives the
    # nudge + quick-check.
    belief = compute_belief(_inputs(
        recorded_sequence=STOCKED_SEQUENCE,
        purchase_dates=_fortnightly_purchases(20),
        stock_level_last_updated=_d(60),
        last_checked_at=None,
    ))
    assert belief.believed_sequence == OUT_OF_STOCK_SEQUENCE
    assert belief.differs_from_recorded is True


# ── Bands are coarse — output is always one of the three ────────────────

def test__believed_band_is_always_coarse():
    for days in range(0, 60, 3):
        belief = compute_belief(_inputs(
            purchase_dates=_fortnightly_purchases(days),
            stock_level_last_updated=_d(60),
        ))
        assert belief.believed_band in ("out", "low", "stocked")
        assert 0.0 <= belief.confidence <= 1.0


def test__as_date__buckets_a_stored_utc_instant_in_the_household_zone():
    """Finalisation 07-R1 (R-021, the FU-525 class): a level changed at 22:00
    UTC is 08:00 *tomorrow* in Sydney — "Updated today", not "1 day ago". Naive
    values are stored UTC."""
    from datetime import date as _date, datetime as _dt, timezone as _tz
    from zoneinfo import ZoneInfo as _Zone
    from dora_api.features.stock_items.pantry_belief import _household_date

    sydney = _Zone("Australia/Sydney")
    aware = _dt(2026, 1, 1, 22, 0, tzinfo=_tz.utc)
    naive = _dt(2026, 1, 1, 22, 0)

    assert _household_date(aware, sydney) == _date(2026, 1, 2)
    assert _household_date(naive, sydney) == _date(2026, 1, 2)
    assert _household_date(naive, _Zone("UTC")) == _date(2026, 1, 1)
    assert _household_date(_date(2026, 1, 1), sydney) == _date(2026, 1, 1)
    assert _household_date(None, sydney) is None
