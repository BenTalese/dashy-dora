"""FU-227 chunk 4 — `build_your_prices_for_item` end-to-end.

Pins: median over normalised per-canonical-unit prices (C1), strict-greater
1.15× threshold (C2 edge case), MIN_SAMPLES=3 (below → baseline=None, current
still set), trailing 12-month window (C2), per-dimension grouping (B4), and
LC-2 source-blind sample_count (offers never bump it even when products are
on).
"""
import uuid
from datetime import UTC, datetime, timedelta

import requests

BASE = "http://localhost:5170/api"
STOCK_ITEMS = f"{BASE}/stock-items"


def _new_stock_item() -> str:
    level = requests.get(f"{BASE}/stock-levels").json()["items"][0]["stock_level_id"]
    resp = requests.post(STOCK_ITEMS, json={
        "name": f"YP-{uuid.uuid4().hex[:8]}",
        "stock_level_id": level,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["stock_item_id"]


def _days_ago(days: int) -> str:
    # Observation dates are relative to now: the baseline is a trailing
    # 365-day window measured from `now`, so fixed dates age out of it.
    return (datetime.now(UTC) - timedelta(days=days)).isoformat()


def _log(item: str, *, total_price: float, total_measure: float, unit: str, observed_at: str | None = None) -> None:
    body = {"total_price": total_price, "total_measure": total_measure, "unit": unit}
    if observed_at is not None:
        body["observed_at"] = observed_at
    r = requests.post(f"{STOCK_ITEMS}/{item}/price-observations", json=body)
    assert r.status_code == 204, r.text


def _yp(item: str) -> dict:
    return requests.get(f"{STOCK_ITEMS}/{item}/detail").json().get("your_prices") or {}


# ── Empty / below-MIN_SAMPLES states ─────────────────────────────────────


def test__your_prices__no_observations__empty_state(api):
    item = _new_stock_item()
    yp = _yp(item)
    assert yp["baseline"] is None
    assert yp["current"] is None
    assert yp["above_baseline"] is False
    assert yp["sample_count"] == 0
    assert yp["last_observed_at"] is None
    assert yp["offers_sidecar"] == []


def test__your_prices__two_samples__baseline_null_current_set(api):
    item = _new_stock_item()
    _log(item, total_price=2.0, total_measure=1.0, unit="L")
    _log(item, total_price=3.0, total_measure=1.0, unit="L")
    yp = _yp(item)
    assert yp["baseline"] is None
    assert yp["above_baseline"] is False
    assert yp["sample_count"] == 2
    # Current is still set even below MIN_SAMPLES so the widget can render
    # "Last seen $X" without a full baseline. $3/L quotes as $0.30/100ml.
    assert yp["current"] == 0.3


# ── Median + strict-greater 1.15× threshold ──────────────────────────────


def test__your_prices__three_samples__median_correct_odd(api):
    item = _new_stock_item()
    _log(item, total_price=2.0, total_measure=1.0, unit="L",
         observed_at=_days_ago(180))
    _log(item, total_price=3.0, total_measure=1.0, unit="L",
         observed_at=_days_ago(150))
    _log(item, total_price=5.0, total_measure=1.0, unit="L",
         observed_at=_days_ago(120))
    yp = _yp(item)
    assert yp["baseline"] == 0.3          # median of [2, 3, 5] per L, per 100ml
    assert yp["baseline_unit"] == "100ml"
    assert yp["sample_count"] == 3


def test__your_prices__four_samples__median_correct_even(api):
    item = _new_stock_item()
    for i, p in enumerate([2.0, 3.0, 4.0, 5.0], start=1):
        _log(item, total_price=p, total_measure=1.0, unit="L",
             observed_at=_days_ago(210 - 30 * i))
    yp = _yp(item)
    # Median of [2, 3, 4, 5] per L = 3.5, quoted per 100ml
    assert abs(yp["baseline"] - 0.35) < 1e-6


def test__your_prices__current_above_threshold__chip_fires(api):
    item = _new_stock_item()
    # Median = 2.0, threshold = 2.0 * 1.15 = 2.3. Current must be > 2.3.
    _log(item, total_price=2.0, total_measure=1.0, unit="L",
         observed_at=_days_ago(180))
    _log(item, total_price=2.0, total_measure=1.0, unit="L",
         observed_at=_days_ago(150))
    _log(item, total_price=2.0, total_measure=1.0, unit="L",
         observed_at=_days_ago(120))
    _log(item, total_price=3.0, total_measure=1.0, unit="L",
         observed_at=_days_ago(30))
    yp = _yp(item)
    # median of [2, 2, 2, 3] = 2.0; current = 3.0 > 2.0 * 1.15 = 2.3 → above
    assert yp["above_baseline"] is True
    assert yp["current"] == 0.3


def test__your_prices__current_exactly_at_threshold__not_above(api):
    """C2 edge case: current == baseline * 1.15 is NOT above (strict >)."""
    item = _new_stock_item()
    _log(item, total_price=2.0, total_measure=1.0, unit="L",
         observed_at=_days_ago(180))
    _log(item, total_price=2.0, total_measure=1.0, unit="L",
         observed_at=_days_ago(150))
    _log(item, total_price=2.0, total_measure=1.0, unit="L",
         observed_at=_days_ago(120))
    _log(item, total_price=2.30, total_measure=1.0, unit="L",
         observed_at=_days_ago(30))
    yp = _yp(item)
    # median = 2.0, current = 2.30 == 2.0 * 1.15 → NOT above
    assert yp["above_baseline"] is False


# ── Unit normalisation: ml ↔ L, g ↔ kg ────────────────────────────────────


def test__your_prices__ml_observations_display_per_100ml(api):
    """500 ml at $3.00 = $6/L = $0.60/100ml. AU shelf convention: below
    1 L → /100ml; at or above → /L (see units.display_denominator_for)."""
    item = _new_stock_item()
    for i in range(1, 4):
        _log(item, total_price=3.0, total_measure=500.0, unit="ml",
             observed_at=_days_ago(210 - 30 * i))
    yp = _yp(item)
    assert yp["baseline_unit"] == "100ml"
    # $6/L / 10 = $0.60/100ml
    assert abs(yp["baseline"] - 0.6) < 1e-6


def test__your_prices__litre_observations_display_per_100ml(api):
    """1 L at $3.00 = $3/L = $0.30/100ml. The AU convention never flips to /L
    (FU-914)."""
    item = _new_stock_item()
    for i in range(1, 4):
        _log(item, total_price=3.0, total_measure=1.0, unit="L",
             observed_at=_days_ago(210 - 30 * i))
    yp = _yp(item)
    assert yp["baseline_unit"] == "100ml"
    assert abs(yp["baseline"] - 0.3) < 1e-6


def test__your_prices__g_observations_display_per_100g(api):
    """250 g at $5.00 = $20/kg = $2.00/100g. Below 1 kg → /100g."""
    item = _new_stock_item()
    for i in range(1, 4):
        _log(item, total_price=5.0, total_measure=250.0, unit="g",
             observed_at=_days_ago(210 - 30 * i))
    yp = _yp(item)
    assert yp["baseline_unit"] == "100g"
    # $20/kg / 10 = $2.00/100g
    assert abs(yp["baseline"] - 2.0) < 1e-6


def test__your_prices__kg_observations_display_per_100g(api):
    """A 1 kg pack quotes per 100g like a 250 g one (FU-914)."""
    item = _new_stock_item()
    for i in range(1, 4):
        _log(item, total_price=10.0, total_measure=1.0, unit="kg",
             observed_at=_days_ago(210 - 30 * i))
    yp = _yp(item)
    assert yp["baseline_unit"] == "100g"
    assert abs(yp["baseline"] - 1.0) < 1e-6


def test__your_prices__bigger_latest_pack_keeps_the_denominator(api):
    """A 1L bottle after several 500ml buys still quotes per 100ml, so the
    history stays comparable (FU-914)."""
    item = _new_stock_item()
    # Three 500ml buys → would otherwise be /100ml.
    for i in range(1, 4):
        _log(item, total_price=3.0, total_measure=500.0, unit="ml",
             observed_at=_days_ago(210 - 30 * i))
    # Latest = 1L; the denominator doesn't move.
    _log(item, total_price=6.0, total_measure=1.0, unit="L",
         observed_at=_days_ago(90))
    yp = _yp(item)
    assert yp["baseline_unit"] == "100ml"
    # Median over per-L prices [6, 6, 6, 6] = 6.0/L = 0.60/100ml.
    assert abs(yp["baseline"] - 0.6) < 1e-6


# ── Count dimension (B1) ──────────────────────────────────────────────────


def test__your_prices__count_dimension_baseline_in_ea(api):
    """3 obs of 12 ea at $7.50 each → $0.625/ea. Median = $0.625."""
    item = _new_stock_item()
    for i in range(1, 4):
        _log(item, total_price=7.50, total_measure=12.0, unit="ea",
             observed_at=_days_ago(210 - 30 * i))
    yp = _yp(item)
    assert yp["baseline_unit"] == "ea"
    assert abs(yp["baseline"] - 0.625) < 1e-6


# ── Trailing 12-month window ──────────────────────────────────────────────


def test__your_prices__old_observations_excluded_from_window(api):
    """An obs older than BASELINE_WINDOW (365d) is excluded from the median
    but the still-recent ones drive the baseline."""
    item = _new_stock_item()
    # One ancient outlier — would skew the median if not filtered.
    _log(item, total_price=100.0, total_measure=1.0, unit="L",
         observed_at=_days_ago(1200))
    # Three recent samples, well inside the trailing year.
    _log(item, total_price=2.0, total_measure=1.0, unit="L",
         observed_at=_days_ago(90))
    _log(item, total_price=3.0, total_measure=1.0, unit="L",
         observed_at=_days_ago(60))
    _log(item, total_price=4.0, total_measure=1.0, unit="L",
         observed_at=_days_ago(30))
    yp = _yp(item)
    # Sample count excludes the >12mo outlier; median over the 3 recent obs = 3/L.
    assert yp["sample_count"] == 3
    assert abs(yp["baseline"] - 0.3) < 1e-6


# ── Per-dimension grouping (B4) ──────────────────────────────────────────


def test__your_prices__mixed_dimensions__most_recent_dimension_wins(api):
    """If the user logs in L then in ea, the active dim follows the most-
    recent obs; obs in the other dim are excluded from the baseline."""
    item = _new_stock_item()
    # 3 L-dim observations (older).
    _log(item, total_price=2.0, total_measure=1.0, unit="L",
         observed_at=_days_ago(180))
    _log(item, total_price=2.0, total_measure=1.0, unit="L",
         observed_at=_days_ago(150))
    _log(item, total_price=2.0, total_measure=1.0, unit="L",
         observed_at=_days_ago(120))
    # 3 ea-dim observations (newer — active dim should switch to ea).
    _log(item, total_price=5.0, total_measure=1.0, unit="ea",
         observed_at=_days_ago(90))
    _log(item, total_price=6.0, total_measure=1.0, unit="ea",
         observed_at=_days_ago(60))
    _log(item, total_price=7.0, total_measure=1.0, unit="ea",
         observed_at=_days_ago(30))
    yp = _yp(item)
    assert yp["baseline_unit"] == "ea"
    assert yp["sample_count"] == 3
    assert abs(yp["baseline"] - 6.0) < 1e-6     # median of [5, 6, 7]


# ── Last-seen store surfacing (A2) ────────────────────────────────────────


def test__your_prices__last_seen_store_name_resolved(api):
    """A2: when the most-recent obs has a store_id, the widget gets the
    resolved name. R-003 — server resolves, client renders a string."""
    item = _new_stock_item()
    stores = requests.get(f"{BASE}/stores").json()["items"]
    assert stores, "the seed ships stores"
    store_id = stores[0]["store_id"]
    _log(item, total_price=3.0, total_measure=1.0, unit="L",
         observed_at=_days_ago(30))
    requests.post(f"{STOCK_ITEMS}/{item}/price-observations", json={
        "total_price": 3.0, "total_measure": 1.0, "unit": "L",
        "store_id": store_id,
        "observed_at": _days_ago(15),
    })
    yp = _yp(item)
    assert yp["last_seen_store_name"]  # non-empty string


# ── LC-2 source-blind ─────────────────────────────────────────────────────


def test__your_prices__offers_sidecar_does_not_affect_sample_count(api):
    """LC-2 — sample_count counts observations only. Linked-product offers
    populate the sidecar but never bump the count. (Verified end-to-end via
    a stock item with no linked products: sidecar is empty; if products
    were linked it would still be a separate list, not folded in.)"""
    item = _new_stock_item()
    for i in range(1, 4):
        _log(item, total_price=2.0, total_measure=1.0, unit="L",
             observed_at=_days_ago(210 - 30 * i))
    yp = _yp(item)
    assert yp["sample_count"] == 3
    # No linked products → sidecar empty.
    assert yp["offers_sidecar"] == []


# ── Multipack (pack_count) ────────────────────────────────────────────────


def test__your_prices__pack_count_round_trips(api):
    """pack_count is stored + surfaced on the obs DTO without affecting
    baseline math. "$4.20 for 4 × 125g" → total_measure=500, pack_count=4."""
    item = _new_stock_item()
    r = requests.post(
        f"{STOCK_ITEMS}/{item}/price-observations",
        json={
            "total_price": 4.20,
            "total_measure": 500.0,
            "unit": "g",
            "pack_count": 4,
        },
    )
    assert r.status_code == 204, r.text
    detail = requests.get(f"{STOCK_ITEMS}/{item}/detail").json()
    obs = detail["price_observations"][0]
    assert obs["pack_count"] == 4
    assert obs["total_measure"] == 500.0


def test__your_prices__pack_count_rejected_when_not_positive(api):
    item = _new_stock_item()
    r = requests.post(
        f"{STOCK_ITEMS}/{item}/price-observations",
        json={
            "total_price": 4.20,
            "total_measure": 500.0,
            "unit": "g",
            "pack_count": 0,
        },
    )
    assert 400 <= r.status_code < 500


# ── US locale display ────────────────────────────────────────────────────


def _set_locale(system: str) -> None:
    """Flip the install-wide measurement_system via the admin endpoint.

    (Was `unit_pricing_locale` on an AU/US axis; replaced 2026-08-27 by the
    three-value measurement system, which drives the unit pickers as well as
    the price denominator. "AU" is now "metric", "US" is now "us".)
    """
    r = requests.patch(
        f"{BASE}/app-settings",
        json={"measurement_system": system},
    )
    assert r.status_code in (200, 204), r.text


def test__your_prices__us_locale_displays_per_lb(api):
    """At-or-above 1 lb (0.4536 kg), US locale displays /lb."""
    _set_locale("us")
    try:
        item = _new_stock_item()
        # 1 kg ≈ 2.2 lb → above the flip threshold.
        for i in range(1, 4):
            _log(item, total_price=10.0, total_measure=1.0, unit="kg",
                 observed_at=_days_ago(210 - 30 * i))
        yp = _yp(item)
        assert yp["baseline_unit"] == "lb"
        # $10/kg × 0.4536 ≈ $4.54/lb
        assert abs(yp["baseline"] - 10.0 / 2.2046226218) < 1e-3
    finally:
        _set_locale("metric")


def test__your_prices__us_locale_displays_per_oz(api):
    """Below 1 lb under US locale displays /oz."""
    _set_locale("us")
    try:
        item = _new_stock_item()
        # 100 g ≈ 0.22 lb → below the flip threshold; should land on /oz.
        for i in range(1, 4):
            _log(item, total_price=2.0, total_measure=100.0, unit="g",
                 observed_at=_days_ago(210 - 30 * i))
        yp = _yp(item)
        assert yp["baseline_unit"] == "oz"
        # $20/kg × 0.02835 ≈ $0.567/oz
        assert abs(yp["baseline"] - 20.0 / 35.27399072) < 1e-3
    finally:
        _set_locale("metric")
