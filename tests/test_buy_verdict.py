"""P8-05 — buy-verdict composer unit tests.

Every test drives `compose_verdict` with a fixture `VerdictInputs` — no
DB, no HTTP, so the composition rules can be pinned in isolation. The
data-gathering layer (`_gather_inputs`) is a thin repo walk; browser-
verify covers it end-to-end.
"""
from datetime import date, datetime, time, timedelta, timezone

from dora_api.features.stock_items.get_buy_verdict import (
    VerdictInputs, compose_verdict,
)
from dora_api.features.stock_items.pantry_belief import PantryBelief


def _today() -> date:
    return date.today()


def _dt(days_ago: int) -> datetime:
    # Aware (the composer compares against an aware horizon), but anchored
    # to local-today's calendar date at noon so `ts.date()` inside the
    # composer always equals `_today() - days_ago`. The previous
    # `datetime.now(timezone.utc) - timedelta(...)` was a flake: on any
    # UTC+n morning the UTC calendar day is one behind the local
    # `date.today()`, shifting every derived low-date by a day and breaking
    # the wait-hint expectation (seen 2026-07-10, AEST before 10am).
    return datetime.combine(
        _today() - timedelta(days=days_ago), time(12, 0), tzinfo=timezone.utc
    )


def _rich_history_inputs(**overrides) -> VerdictInputs:
    """A middle-of-the-road history: 8 price samples over 6 months at
    around $3.80 with the most-recent shop at $3.85 (usual price band),
    buying every ~14 days, no waste events, stocked. Individual
    tests override the axes they care about."""
    base = VerdictInputs(
        price_samples=[
            (3.85, _dt(6)),
            (3.90, _dt(20)),
            (3.75, _dt(34)),
            (3.80, _dt(48)),
            (3.95, _dt(62)),
            (3.70, _dt(76)),
            (3.85, _dt(90)),
            (3.80, _dt(104)),
        ],
        unique_purchase_dates=sorted([
            _today() - timedelta(days=d)
            for d in (6, 20, 34, 48, 62, 76, 90, 104)
        ]),
        waste_events_12mo=0,
        purchases_12mo=8,
        stock_level_band="stocked",
        is_on_open_list=False,
        today=_today(),
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


# ── Need axis trumps price ────────────────────────────────────────────

def test__out_of_stock__is_buy_with_high_confidence():
    """Charter §2.3.1: `need = out_of_stock` overrides everything —
    even if price is above usual and the user has wasted this before,
    the shelf is empty and the item needs replacing."""
    verdict = compose_verdict(_rich_history_inputs(stock_level_band="out"))
    assert verdict.verdict == "buy"
    assert verdict.confidence == "high"
    assert any(r.axis == "need" and r.signal == "out_of_stock" for r in verdict.reasons)
    assert verdict.one_tap_action.kind == "add_to_list"


def test__out_of_stock_and_above_usual_price__still_buy():
    """The price axis still contributes a reason, but the verdict
    doesn't flip. Users need to see the price warning without the
    verdict lying about the underlying need."""
    inputs = _rich_history_inputs(
        stock_level_band="out",
        # Make the last shop the priciest so `above_usual` fires.
        price_samples=[
            (4.50, _dt(6)),
            (3.80, _dt(20)),
            (3.75, _dt(34)),
            (3.80, _dt(48)),
            (3.85, _dt(62)),
        ],
    )
    verdict = compose_verdict(inputs)
    assert verdict.verdict == "buy"
    assert any(r.axis == "price" and r.signal == "above_usual" for r in verdict.reasons)


# ── Low stock branches ────────────────────────────────────────────────

def test__low_stock_plus_cheapest_3mo__is_buy_high():
    inputs = _rich_history_inputs(
        stock_level_band="low",
        # Steep drop on the most recent shop.
        price_samples=[
            (3.10, _dt(6)),
            (3.90, _dt(20)),
            (3.85, _dt(34)),
            (3.80, _dt(48)),
            (3.90, _dt(62)),
            (3.85, _dt(76)),
            (3.90, _dt(90)),
        ],
    )
    verdict = compose_verdict(inputs)
    assert verdict.verdict == "buy"
    assert verdict.confidence == "high"
    assert any(r.signal == "cheapest_3mo" for r in verdict.reasons)


def test__low_stock_plus_above_usual__is_wait():
    inputs = _rich_history_inputs(
        stock_level_band="low",
        price_samples=[
            (4.60, _dt(6)),         # ~120% of usual ($3.85)
            (3.80, _dt(20)),
            (3.85, _dt(34)),
            (3.80, _dt(48)),
            (3.85, _dt(62)),
        ],
    )
    verdict = compose_verdict(inputs)
    assert verdict.verdict == "wait"
    assert verdict.one_tap_action.kind == "skip"


def test__non_essential_low_plus_usual_price__is_the_weakest_buy():
    """The 2026-08-24 owner call. Marking a *non-essential* item low used to
    produce "Worth buying now", which said the opposite of `stock_attention`'s
    rule that a non-essential shortage isn't even worth a notification. It's
    still a buy — you are low — but it's the bottom of the scale, and the
    confidence stays high because the history behind it is rich."""
    verdict = compose_verdict(_rich_history_inputs(stock_level_band="low"))
    assert verdict.verdict == "buy"
    assert verdict.strength == 1
    assert verdict.confidence == "high"


def test__essential_low__outranks_the_same_item_unflagged():
    """The flag is the whole point of the grading: same history, same band,
    one step further up the scale because you said you always want it."""
    normal = compose_verdict(_rich_history_inputs(stock_level_band="low"))
    essential = compose_verdict(
        _rich_history_inputs(stock_level_band="low", is_essential=True)
    )
    assert normal.strength == 1
    assert essential.strength == 2
    assert essential.verdict == normal.verdict == "buy"


def test__essential_out_of_stock__is_the_top_of_the_scale():
    verdict = compose_verdict(
        _rich_history_inputs(stock_level_band="out", is_essential=True)
    )
    assert verdict.verdict == "buy"
    assert verdict.strength == 3


def test__essential_flag__does_not_lift_a_stocked_item():
    """Essential grades a *shortage*. An essential you have plenty of is no
    more worth buying than any other stocked item."""
    stocked = compose_verdict(_rich_history_inputs(is_essential=True))
    assert stocked.strength == 0


def test__strength_and_confidence_are_independent():
    """The two dials answer different questions, which is why they were split:
    a strong need on thin evidence has to be sayable."""
    verdict = compose_verdict(VerdictInputs(
        price_samples=[(3.80, _dt(6))],        # 1 sample → thin price axis
        unique_purchase_dates=[_today() - timedelta(days=6)],
        waste_events_12mo=0,
        purchases_12mo=1,
        stock_level_band="out",
        is_essential=True,
        today=_today(),
    ))
    assert verdict.strength == 3               # you're out of an essential
    assert verdict.confidence == "medium"      # off one price sample


# ── Stocked branches (waste + price interplay) ───────────────────

def test__stocked_plus_frequent_waste__is_skip_high():
    """Charter §2.3.3: 'wastes often' should trump a cheap price — you
    do not want to buy more of what you throw away."""
    inputs = _rich_history_inputs(
        stock_level_band="stocked",
        waste_events_12mo=4,
        purchases_12mo=8,          # 50% waste rate → wastes_often
        # And it happens to be the cheapest in 3 months too.
        price_samples=[
            (3.00, _dt(6)),
            (3.85, _dt(20)),
            (3.90, _dt(34)),
            (3.80, _dt(48)),
        ],
    )
    verdict = compose_verdict(inputs)
    assert verdict.verdict == "skip"
    assert verdict.confidence == "high"
    assert any(r.signal == "wastes_often" for r in verdict.reasons)
    assert verdict.one_tap_action.kind == "mark_stocked"


def test__stocked_plus_waste_and_on_open_list__action_is_remove():
    """If we're saying skip *and* the item is already on an open list,
    the sensible one-tap is 'remove from list', not 'mark stocked'."""
    inputs = _rich_history_inputs(
        stock_level_band="stocked",
        waste_events_12mo=4,
        purchases_12mo=8,
        is_on_open_list=True,
    )
    verdict = compose_verdict(inputs)
    assert verdict.verdict == "skip"
    assert verdict.one_tap_action.kind == "remove_from_list"


def test__stocked_plus_cheapest__is_the_weakest_buy():
    inputs = _rich_history_inputs(
        stock_level_band="stocked",
        price_samples=[
            (3.10, _dt(6)),
            (3.90, _dt(20)),
            (3.85, _dt(34)),
            (3.80, _dt(48)),
            (3.85, _dt(62)),
        ],
    )
    verdict = compose_verdict(inputs)
    assert verdict.verdict == "buy"
    # Nothing but the price is arguing for it — a "might", not a "now".
    assert verdict.strength == 1
    assert verdict.confidence == "high"


def test__stocked_plus_above_usual__is_wait():
    inputs = _rich_history_inputs(
        stock_level_band="stocked",
        price_samples=[
            (4.60, _dt(6)),
            (3.85, _dt(20)),
            (3.80, _dt(34)),
            (3.90, _dt(48)),
        ],
    )
    verdict = compose_verdict(inputs)
    assert verdict.verdict == "wait"


def test__stocked_plus_usual_price__is_unsure():
    """No axis is arguing either way. `confidence` stays high — the evidence
    is rich, it just doesn't point anywhere; that separation is the point of
    splitting strength out of confidence."""
    verdict = compose_verdict(_rich_history_inputs(stock_level_band="stocked"))
    assert verdict.verdict == "unsure"
    assert verdict.strength == 0
    assert verdict.confidence == "high"
    assert verdict.one_tap_action.kind == "none"


# ── Thin data collapses honestly ──────────────────────────────────────

def test__all_axes_thin__collapses_to_single_not_enough_history():
    """Charter §2.3.4: three thin axes ⇒ one honest reason, not three
    absent-signal messages.

    Waste-axis nuance: `waste_events_12mo=0` would branch to
    `no_waste_history` (a meaningful positive signal — "you've never
    wasted this"), NOT to `thin_data`. To truly get three thin axes
    we need a waste event PLUS fewer purchases than
    `_MIN_PURCHASES_FOR_WASTE_RATE` — i.e. "waste has happened but we
    can't yet compute a rate".
    """
    inputs = VerdictInputs(
        price_samples=[(3.80, _dt(4))],   # 1 sample → thin
        unique_purchase_dates=[_today() - timedelta(days=4)],
        waste_events_12mo=1,              # some waste seen…
        purchases_12mo=1,                 # …but too few purchases to compute a rate → thin
        stock_level_band="unknown",       # thin on need
        is_on_open_list=False,
        today=_today(),
    )
    verdict = compose_verdict(inputs)
    assert verdict.verdict == "unsure"
    assert verdict.confidence == "low"
    assert len(verdict.reasons) == 1
    assert verdict.reasons[0].signal == "thin_data"
    assert verdict.one_tap_action.kind == "none"


def test__thin_price_only__drops_confidence_a_step_but_keeps_verdict():
    """Low-stock with thin price data: verdict stays `buy` (need still argues
    for it), and the one thin axis costs a step of confidence."""
    inputs = VerdictInputs(
        price_samples=[(3.80, _dt(6))],        # 1 sample → thin
        unique_purchase_dates=[_today() - timedelta(days=6)],
        waste_events_12mo=0,
        purchases_12mo=1,
        stock_level_band="low",
        is_on_open_list=False,
        today=_today(),
    )
    verdict = compose_verdict(inputs)
    assert verdict.verdict == "buy"
    assert verdict.confidence == "medium"   # one thin axis, stepped from high


def test__waste_thin_but_no_events__signals_no_waste_history_not_thin():
    """Purchase history is too shallow to compute a waste rate, but
    zero events + a fresh account is not the same as 'unknown'. The
    axis contributes no reason but confidence doesn't drop from it."""
    inputs = VerdictInputs(
        price_samples=[
            (3.80, _dt(6)),
            (3.85, _dt(20)),
            (3.75, _dt(34)),
            (3.80, _dt(48)),
        ],
        unique_purchase_dates=sorted([
            _today() - timedelta(days=d) for d in (6, 20, 34, 48)
        ]),
        waste_events_12mo=0,
        purchases_12mo=2,   # under the min-for-waste-rate threshold
        stock_level_band="stocked",
        is_on_open_list=False,
        today=_today(),
    )
    verdict = compose_verdict(inputs)
    # Stocked + usual price + no-waste-history → unsure (no positive reason
    # for a buy either). But not the 3-axis collapse; there are still price +
    # need reasons, and neither of those axes is thin — so confidence, which
    # only measures the evidence, stays high.
    assert verdict.verdict == "unsure"
    assert verdict.strength == 0
    assert verdict.confidence == "high"


# ── Data-used transparency ────────────────────────────────────────────

def test__data_used_reflects_the_actual_inputs():
    """The `data_used` block is the SPA's 'why?' tooltip source — must
    match what the composer saw or the UI lies (Charter P7 preview /
    explain)."""
    inputs = _rich_history_inputs()
    verdict = compose_verdict(inputs)
    data = verdict.data_used
    assert data.price_samples == 8
    assert data.stock_level_band == "stocked"
    assert data.purchases_last_12mo == 8
    assert data.waste_events_last_12mo == 0
    assert data.average_days_between_purchase is not None
    assert data.days_since_last_purchase is not None


def test__observation_dates_bucket_in_household_zone__not_utc():
    """FU-525 — a UTC observation timestamp is bucketed into a calendar day in
    the *household* zone so it agrees with `today` (R-021). 23:00 UTC on Jun 1
    is already Jun 2 in Sydney (AEST, UTC+10); the surfaced `price_last_at` must
    be the Sydney day, not the UTC one — otherwise the wait-hint's dates drift a
    day and can flip its `next_low <= today` staleness check."""
    from zoneinfo import ZoneInfo

    ts = datetime(2026, 6, 1, 23, 0, tzinfo=timezone.utc)  # == 2026-06-02 09:00 AEST
    syd = VerdictInputs(
        price_samples=[(3.50, ts)],
        unique_purchase_dates=[date(2026, 6, 2)],
        stock_level_band="stocked",
        today=date(2026, 6, 2),
        tz=ZoneInfo("Australia/Sydney"),
    )
    assert compose_verdict(syd).data_used.price_last_at == "2026-06-02"

    # Same instant read in UTC (the pre-FU-525 behaviour) buckets a day earlier.
    utc = VerdictInputs(
        price_samples=[(3.50, ts)],
        unique_purchase_dates=[date(2026, 6, 1)],
        stock_level_band="stocked",
        today=date(2026, 6, 1),
        tz=timezone.utc,
    )
    assert compose_verdict(utc).data_used.price_last_at == "2026-06-01"


# ── P8-06 wait-hint (`_wait_hint`) ────────────────────────────────────


def _wait_case(price_samples):
    """Wait-shaped fixture — stocked + samples the caller controls. The
    most recent sample is above the usual band, so the composer lands on
    `wait` and `_wait_hint` gets to run."""
    dates = sorted({ts.date() for _, ts in price_samples})
    return VerdictInputs(
        price_samples=sorted(price_samples, key=lambda s: s[1], reverse=True),
        unique_purchase_dates=dates,
        waste_events_12mo=0,
        purchases_12mo=len(dates),
        stock_level_band="stocked",
        is_on_open_list=False,
        today=_today(),
    )


def test__wait_hint__regular_fortnightly_cycle__predicts_next_low():
    """Two lows 28 days apart with the newest sample above usual → wait
    verdict + wait_hint pointing 28 days after the most recent low (i.e.
    into the future — the whole point of P8-06)."""
    # Trimmed-mean of [3.30, 3.30, 3.85, 3.90, 4.30] drops min+max, giving
    # usual ≈ $3.68; 0.92× = $3.39 → the two $3.30 samples are "lows".
    # $4.30 newest reads as ~117% of usual → above_usual → wait.
    inputs = _wait_case([
        (4.30, _dt(3)),        # newest — above usual → wait
        (3.30, _dt(14)),       # recent low
        (3.85, _dt(28)),
        (3.30, _dt(42)),       # earlier low — 28 days before the recent one
        (3.90, _dt(56)),
    ])
    v = compose_verdict(inputs)
    assert v.verdict == "wait"
    assert v.wait_hint is not None
    expected_next = _today() - timedelta(days=14) + timedelta(days=28)
    assert v.wait_hint.until == expected_next.isoformat()
    assert "~every 28 days" in v.wait_hint.reason


def test__wait_hint__single_low__silent():
    """One low = no gap to measure = no cycle. Stay silent (Charter P3)."""
    inputs = _wait_case([
        (4.30, _dt(6)),        # above usual → wait
        (3.90, _dt(20)),
        (3.95, _dt(34)),
        (3.30, _dt(48)),       # only one low across the window
        (3.90, _dt(62)),
    ])
    v = compose_verdict(inputs)
    assert v.verdict == "wait"
    assert v.wait_hint is None


def test__wait_hint__wildly_varying_gaps__silent():
    """Two gaps of vastly different sizes (2 days vs 100+ days) trip the
    CV guard — the cadence is too erratic to time. Stay silent."""
    inputs = _wait_case([
        (4.30, _dt(4)),        # newest — above usual → wait
        (3.30, _dt(14)),       # low
        (3.30, _dt(16)),       # low, 2 days after the previous one
        (3.85, _dt(60)),
        (3.90, _dt(120)),
        (3.30, _dt(180)),      # low, 164 days earlier
    ])
    v = compose_verdict(inputs)
    assert v.verdict == "wait"
    assert v.wait_hint is None


def test__wait_hint__overdue_prediction__silent():
    """Two lows early in the window → the predicted next low is well in
    the past. The cycle has broken; don't surface a stale date (Charter
    P3). Prices tuned so the two ancient $3.20 samples survive the
    trimmed-mean cheap-band as genuine lows."""
    inputs = _wait_case([
        (5.00, _dt(4)),        # newest — above usual → wait
        (4.80, _dt(30)),
        (4.60, _dt(60)),
        (4.90, _dt(100)),
        (3.20, _dt(300)),      # low
        (3.20, _dt(350)),      # low, 50 days earlier → predicted next ≈ 250d ago
    ])
    v = compose_verdict(inputs)
    assert v.verdict == "wait"
    assert v.wait_hint is None


def test__wait_hint__not_wait__is_none():
    """Non-wait verdicts must not carry a wait_hint — the field is a
    verdict-specific extension, not general noise."""
    v = compose_verdict(_rich_history_inputs())
    # Baseline rich fixture lands on `unsure` (stocked + usual price + no
    # waste history) — the important assertion is `wait_hint is None`.
    assert v.verdict != "wait"
    assert v.wait_hint is None


# ── FU-450 — fake-markdown demotion ───────────────────────────────────

def test__fake_markdown__costs_the_price_axis_its_strength():
    """Low stock + cheapest_3mo is normally strength 2. A fake markdown on a
    linked product takes the point back and surfaces the honesty reason — Dora
    won't celebrate an inflated 'special'. It doesn't argue you out of the
    shortage itself, so the verdict stays `buy`, one rung lower."""
    inputs = _rich_history_inputs(
        stock_level_band="low",
        fake_markdown=True,
        price_samples=[
            (3.10, _dt(6)),
            (3.90, _dt(20)),
            (3.85, _dt(34)),
            (3.80, _dt(48)),
            (3.90, _dt(62)),
        ],
    )
    verdict = compose_verdict(inputs)
    assert verdict.verdict == "buy"
    assert verdict.strength == 1
    honest = compose_verdict(_rich_history_inputs(
        stock_level_band="low",
        price_samples=inputs.price_samples,
    ))
    assert honest.strength == 2
    assert any(r.signal == "fake_markdown" for r in verdict.reasons)


def test__fake_markdown__never_overrides_out_of_stock_need():
    """You're out — you need it, real special or not. The verdict stays
    `buy`, but the inflated-markdown reason still surfaces (honesty)."""
    inputs = _rich_history_inputs(
        stock_level_band="out",
        fake_markdown=True,
    )
    verdict = compose_verdict(inputs)
    assert verdict.verdict == "buy"
    assert any(r.signal == "fake_markdown" for r in verdict.reasons)


def test__no_fake_markdown__reason_absent():
    verdict = compose_verdict(_rich_history_inputs(stock_level_band="low"))
    assert not any(r.signal == "fake_markdown" for r in verdict.reasons)


# -- D-11: the need axis reasons from pantry belief ---------------------
# `IMPL_PLAN_STOCK_SIGNAL_CONSOLIDATION.md` D-11 folded belief into this
# composer so the two surfaces can't state contradictory versions of the same
# cadence fact. Belief wins when it has signal; the recorded level is the
# floor; an inference that disagrees with the recorded level hedges both its
# wording and the verdict's confidence.


def _belief(band: str, confidence_band: str, *, is_inferred: bool = True,
            reason: str = "~Out — bought 20 days ago; your usual ~14-day supply should be gone.",
            differs: bool = True) -> PantryBelief:
    return PantryBelief(
        believed_sequence={"out": 2, "low": 1, "stocked": 0}[band],
        believed_band=band,
        confidence={"high": 0.8, "medium": 0.5, "low": 0.2}[confidence_band],
        confidence_band=confidence_band,
        reason=reason,
        is_inferred=is_inferred,
        differs_from_recorded=differs,
    )


def test__confident_belief_overrides_the_recorded_level():
    """Recorded says stocked, belief says out with confidence. The user
    hasn't logged a level in a while; Dora's evidence is the better answer,
    so `need` follows it."""
    verdict = compose_verdict(_rich_history_inputs(
        stock_level_band="stocked",
        belief=_belief("out", "high"),
    ))
    assert any(r.axis == "need" and r.signal == "out_of_stock" for r in verdict.reasons)
    assert verdict.verdict == "buy"


def test__inferred_need__hedges_the_label_and_carries_beliefs_reason():
    """Charter P3 — "You're out of stock" is an assertion; an inference gets
    "Probably out of stock" and belief's own explanation as the detail (one
    voice for the cadence story, not two phrasings of it)."""
    belief = _belief("out", "high")
    verdict = compose_verdict(_rich_history_inputs(
        stock_level_band="stocked",
        belief=belief,
    ))
    need = next(r for r in verdict.reasons if r.axis == "need")
    assert need.label == "Probably out of stock"
    assert need.detail == belief.reason


def test__inferred_need__steps_the_confidence_down():
    """A recorded out-of-stock is `buy/high`; the same call built on an
    inference that disagrees with the recorded level is `buy/medium`. Belief
    has no quantity awareness, so it must not produce the composer's
    strongest verdict on its own."""
    recorded = compose_verdict(_rich_history_inputs(stock_level_band="out"))
    inferred = compose_verdict(_rich_history_inputs(
        stock_level_band="stocked",
        belief=_belief("out", "high"),
    ))
    assert recorded.confidence == "high"
    assert inferred.verdict == "buy"
    assert inferred.confidence == "medium"


def test__low_confidence_belief__defers_to_the_recorded_level():
    """The thin-data / no-history path. A guess Dora wouldn't show the user
    as a chip has no business overruling a level they set by hand."""
    verdict = compose_verdict(_rich_history_inputs(
        stock_level_band="stocked",
        belief=_belief("out", "low"),
    ))
    assert any(r.axis == "need" and r.signal == "stocked" for r in verdict.reasons)
    assert not any(r.label.startswith("Probably") for r in verdict.reasons)


def test__belief_echoing_a_fresh_check__is_not_treated_as_an_inference():
    """`is_inferred=False` is belief repeating a level the user just
    confirmed. That's the recorded level wearing a different hat — it neither
    hedges the label nor costs the verdict confidence."""
    verdict = compose_verdict(_rich_history_inputs(
        stock_level_band="out",
        belief=_belief("out", "high", is_inferred=False, differs=False,
                       reason="You confirmed this today."),
    ))
    need = next(r for r in verdict.reasons if r.axis == "need")
    assert need.label == "You're out of stock"
    assert verdict.confidence == "high"


def test__belief_agreeing_with_the_recorded_level__keeps_the_plain_label():
    """Inferred, confident, and it happens to agree. Nothing to hedge about -
    but belief's reason is still the better detail."""
    belief = _belief(
        "low", "high", differs=False,
        reason="~Low — bought 12 days ago; you usually finish in about 14 days.",
    )
    verdict = compose_verdict(_rich_history_inputs(
        stock_level_band="low",
        belief=belief,
    ))
    need = next(r for r in verdict.reasons if r.axis == "need")
    assert need.label == "Running low"
    assert need.detail == belief.reason


def test__no_belief__composes_exactly_as_before():
    """Every pre-D-11 call site (and the gather path before beliefs are
    available) passes no belief. That must stay a no-op, using the recorded
    band and this module's own cadence prose."""
    verdict = compose_verdict(_rich_history_inputs(stock_level_band="low"))
    need = next(r for r in verdict.reasons if r.axis == "need")
    assert need.label == "Running low"
    assert need.detail is not None
    assert "Bought every ~14 days" in need.detail


def test__unknown_recorded_band_plus_confident_belief__is_no_longer_thin():
    """An item with no level at all used to make `need` thin-data outright.
    With purchase history behind it, belief can still answer."""
    verdict = compose_verdict(_rich_history_inputs(
        stock_level_band="unknown",
        belief=_belief("low", "medium"),
    ))
    assert any(r.axis == "need" and r.signal == "low_stock" for r in verdict.reasons)


def test__price_reasons__carry_amounts_not_a_formatted_string():
    """D-006 — the server never formats currency. The price axis used to bake
    `f"${x:.2f}"` into `detail`, which rendered a dollar sign to a household
    on EUR; it now emits the two raw amounts and the SPA formats them."""
    verdict = compose_verdict(_rich_history_inputs(stock_level_band="low"))
    price = next(r for r in verdict.reasons if r.axis == "price")
    assert price.detail is None
    assert price.amount_last == 3.85
    # Trimmed mean of the 8 samples, rounded — the same figure `data_used`
    # publishes, so the sub-line and the transparency payload can't disagree.
    assert price.amount_usual == verdict.data_used.price_average


def test__no_reason_string_anywhere__contains_a_currency_symbol():
    """Guards the whole reason set, not just the price axis: any future prose
    that hardcodes a symbol should fail here rather than in a EUR household."""
    for band in ("out", "low", "stocked"):
        verdict = compose_verdict(_rich_history_inputs(stock_level_band=band))
        for reason in verdict.reasons:
            assert "$" not in reason.label
            assert "$" not in (reason.detail or "")


def test__non_price_reasons__carry_no_amounts():
    verdict = compose_verdict(_rich_history_inputs(
        stock_level_band="stocked", waste_events_12mo=4,
    ))
    for reason in verdict.reasons:
        if reason.axis == "price":
            continue
        assert reason.amount_last is None
        assert reason.amount_usual is None


# ── Planned demand joins the verdict (owner 2026-10-15) ────────────────

def _demand(urgency: str, planned: int = 3, covered: int = 0):
    from dora_api.features.stock_items.planned_demand import PlannedDemand
    return PlannedDemand(
        planned_meals=planned, covered_meals=covered, needed_meals=planned - covered,
        earliest_needed=_today() + timedelta(days=2), recipe_names=["Fried rice"],
        urgency=urgency, reason="3 planned meals coming up need this: Fried rice.",
    )


def test__planned_meals__are_a_reason_and_come_first():
    verdict = compose_verdict(_rich_history_inputs(planned_demand=_demand("none")))
    assert verdict.reasons[0].axis == "plan"
    assert verdict.reasons[0].label == "3 planned meals use it"
    assert verdict.reasons[0].detail.startswith("3 planned meals")


def test__planned_meals_against_a_stocked_item__change_nothing_else():
    plain = compose_verdict(_rich_history_inputs())
    planned = compose_verdict(_rich_history_inputs(planned_demand=_demand("none")))
    assert (planned.verdict, planned.strength, planned.confidence) == (
        plain.verdict, plain.strength, plain.confidence,
    )


def test__planned_meals_against_a_low_item__lift_the_buy():
    plain = compose_verdict(_rich_history_inputs(stock_level_band="low"))
    planned = compose_verdict(_rich_history_inputs(
        stock_level_band="low", planned_demand=_demand("watch"),
    ))
    assert planned.strength == plain.strength + 1
    assert planned.reasons[0].label == "3 planned meals need it, and you're low"


def test__planned_meals_against_an_out_item__name_the_blocker():
    planned = compose_verdict(_rich_history_inputs(
        stock_level_band="out", planned_demand=_demand("blocking", planned=1),
    ))
    assert planned.verdict == "buy"
    assert planned.reasons[0].label == "1 planned meal can't be cooked without it"


def test__planned_meals_survive_thin_history():
    thin = VerdictInputs(today=_today(), planned_demand=_demand("none"))
    verdict = compose_verdict(thin)
    assert verdict.verdict == "unsure"
    assert verdict.reasons[0].axis == "plan"


def test__planned_shortfall_already_on_a_list__adds_no_strength():
    """FU-776 — the planner's add-to-list already handled it; lifting the buy
    again would count the same need twice."""
    plain = compose_verdict(_rich_history_inputs(stock_level_band="low"))
    listed = compose_verdict(_rich_history_inputs(
        stock_level_band="low", planned_demand=_demand("watch"), is_on_open_list=True,
    ))
    assert listed.strength == plain.strength
    assert listed.reasons[0].axis == "plan"
    assert listed.reasons[0].detail.endswith("Already on a shopping list.")


def test__planned_meal_tips_an_unsure_low_item_to_buy():
    """FU-774 — a planned meal changes the verdict, not just the prose."""
    plain = compose_verdict(_rich_history_inputs(
        stock_level_band="low", waste_events_12mo=1,
    ))
    planned = compose_verdict(_rich_history_inputs(
        stock_level_band="low", waste_events_12mo=1, planned_demand=_demand("watch"),
    ))
    assert planned.strength > plain.strength
    assert planned.verdict == "buy"
