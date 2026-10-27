"""FU-519 item 2 — reports router e2e (`dora_api/features/reports/`).

One test per report pinning the response shape plus at least one computed
value against data seeded through the API:

  spend-by-store · most-bought-items ·
  savings-captured · price-drops ·
  meals-cooked · spend-by-category · spend-year-over-year

`range=all` is used wherever ranges apply so assertions aren't sensitive to
the 30d default window; the actual→picked price ladder for spend-by-store is
already pinned by `test_spend_by_store.py` and not re-tested here.
"""
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
import requests

from tests.e2e.dora_api._spend_seeding import seed_purchase
from tests.support import assert_problem, is_valid_datetime, set_money_enabled

BASE = "http://localhost:5170/api"
REPORTS = f"{BASE}/reports"

# Every report that answers in dollars refuses with 403 when the install has
# money off (FU-816 / R-058), and a fresh install has it off. The gate itself
# is exercised in its own region at the foot of this file.
@pytest.fixture(autouse=True)
def _money_on(api):
    set_money_enabled(True)


def _token() -> str:
    return f"zqr{uuid4().hex[:8]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# The stock-value-over-time region went with its endpoint (finalisation
# 12-R1 — no consumer, and its figure read `noload` relationships).


#region ---------------- spend by store ----------------


def test__spend_by_store__ArchivedPurchase__SpendIsPriceTimesQuantity(api):
    seeded = seed_purchase(price_now=4.5, quantity=2)

    rows = requests.get(f"{REPORTS}/spend-by-store", params={"range": "all"}).json()["rows"]

    row = next(r for r in rows if r["store_id"] == seeded["store_id"])
    assert set(row.keys()) == {
        "store_id", "store", "brand_colour", "spend", "list_count",
    }
    assert row["store"] == seeded["store_name"]
    assert row["spend"] == 9.0  # 4.5 picked × qty 2
    assert row["list_count"] == 1


def test__spend_by_store__Response__ShipsTotalAndStoreCountWithTheRows(api):
    # R-041 — a derived aggregate travels with its coverage. The dashboard's
    # spend card shows only the top 3 stores, so it must be able to say "top 3 of
    # N" and print a total it didn't compute itself. Before this, it summed the
    # fetched rows in the browser and rendered a bare "$X total" under three
    # rows, which reads as the sum of those three.
    seed_purchase(price_now=4.5, quantity=2)

    body = requests.get(f"{REPORTS}/spend-by-store", params={"range": "all"}).json()

    assert {"range", "rows", "total_spend", "store_count"} <= body.keys()
    assert body["store_count"] == len(body["rows"])
    # The total is the sum of every row, not just the ones a client might show.
    assert body["total_spend"] == pytest.approx(
        round(sum(r["spend"] for r in body["rows"]), 2)
    )
    assert body["total_spend"] >= 9.0


def test__spend_by_store__UsualStoreNoProduct__AttributedViaTheStoreLadder(api):
    # FU-815 — the handler used to require `selected_product_id IS NOT NULL`
    # and take the store off that product, i.e. rung five of the five-rung
    # ladder. A household that tags items "I buy this at Aldi" and never
    # touches the products feature therefore saw a populated store breakdown on
    # its receipt and an EMPTY card in Reports, off the same finished list.
    suffix = uuid4().hex[:8]
    store_name = f"LadderStore-{suffix}"
    assert requests.post(f"{BASE}/stores", json={"name": store_name}).status_code == 201
    stores = requests.get(f"{BASE}/stores").json()["items"]
    store_id = next(s["store_id"] for s in stores if s["name"] == store_name)

    level = requests.get(f"{BASE}/stock-levels").json()["items"][0]["stock_level_id"]
    item_resp = requests.post(f"{BASE}/stock-items", json={
        "name": f"LadderItem-{suffix}",
        "stock_level_id": level,
        "usual_store_id": store_id,
    })
    assert item_resp.status_code == 201, item_resp.text
    item_id = item_resp.json()["stock_item_id"]

    list_id = requests.post(
        f"{BASE}/shopping-lists", json={"name": f"LadderList-{suffix}"},
    ).json()["shopping_list_id"]
    # No `selected_product_id` — this line never touches the products feature.
    assert requests.post(
        f"{BASE}/shopping-lists/{list_id}/lines", json={"stock_item_id": item_id},
    ).status_code in (200, 201)
    line_id = requests.get(
        f"{BASE}/shopping-lists/{list_id}"
    ).json()["lines"][0]["line_id"]
    assert requests.patch(
        f"{BASE}/shopping-lists/{list_id}/lines/{line_id}",
        json={"is_ticked": True, "actual_unit_price": 7.25},
    ).status_code == 204
    assert requests.post(f"{BASE}/shopping-lists/{list_id}/finish").status_code == 200

    rows = requests.get(
        f"{REPORTS}/spend-by-store", params={"range": "all"},
    ).json()["rows"]

    row = next(r for r in rows if r["store_id"] == store_id)
    assert row["store"] == store_name
    assert row["spend"] == 7.25


def test__spend_by_store__TickedLineWithNoPrice__CountedAsUnpricedNotDropped(api):
    # R-041 — the total states what it was built from. Lines with no price at
    # all were (and still are) excluded from the money, but they used to vanish
    # without trace, so the card undercounted in silence while the shopping
    # list's own card said "12 items unpriced, not counted".
    seeded = seed_purchase(price_now=4.5)
    suffix = uuid4().hex[:8]
    level = requests.get(f"{BASE}/stock-levels").json()["items"][0]["stock_level_id"]
    item_id = requests.post(f"{BASE}/stock-items", json={
        "name": f"UnpricedItem-{suffix}", "stock_level_id": level,
    }).json()["stock_item_id"]
    list_id = requests.post(
        f"{BASE}/shopping-lists", json={"name": f"UnpricedList-{suffix}"},
    ).json()["shopping_list_id"]
    requests.post(
        f"{BASE}/shopping-lists/{list_id}/lines", json={"stock_item_id": item_id},
    )
    line_id = requests.get(
        f"{BASE}/shopping-lists/{list_id}"
    ).json()["lines"][0]["line_id"]
    requests.patch(
        f"{BASE}/shopping-lists/{list_id}/lines/{line_id}", json={"is_ticked": True},
    )
    requests.post(f"{BASE}/shopping-lists/{list_id}/finish")

    body = requests.get(f"{REPORTS}/spend-by-store", params={"range": "all"}).json()

    assert body["unpriced_lines"] >= 1
    assert body["counted_lines"] >= 1
    # The unpriced line contributes nothing to the money.
    assert seeded["store_id"] in {r["store_id"] for r in body["rows"]}


#endregion spend by store

#region ---------------- most-bought items ----------------


def test__most_bought_items__ItemOnTwoArchivedLists__CountsDistinctLists(api):
    first = seed_purchase()
    # Same stock item on a second archived list → appearances = 2 (distinct
    # lists, not line edits).
    seed_purchase(stock_item_id=first["stock_item_id"])

    rows = requests.get(
        f"{REPORTS}/most-bought-items", params={"range": "all", "limit": 50},
    ).json()["rows"]

    row = next(r for r in rows if r["stock_item_id"] == first["stock_item_id"])
    assert set(row.keys()) == {"stock_item_id", "name", "appearances"}
    assert row["name"] == first["stock_item_name"]
    assert row["appearances"] == 2


def test__most_bought_items__UntickedLineOnArchivedList__DoesNotCount(api):
    """'Bought most' counts purchases, not list membership: a line added and
    never ticked before the list was finished is not a purchase
    (finalisation 12-R4; the FU-768 "on the list != bought" class)."""
    seeded = seed_purchase(tick=False, finish=True, actual_unit_price=None, price_unrecorded=True)

    rows = requests.get(
        f"{REPORTS}/most-bought-items", params={"range": "all", "limit": 500},
    ).json()["rows"]

    assert seeded["stock_item_id"] not in {r["stock_item_id"] for r in rows}


#endregion most-bought items

#region ---------------- savings captured ----------------


def test__savings_captured__PickedBelowRrpSnapshot__SavingsIsDelta(api):
    # picked_offer_price=4.5 / list_price_at_pick=10.5 snapshotted at add time.
    seeded = seed_purchase(price_now=4.5, price_was=10.5)

    body = requests.get(
        f"{REPORTS}/savings-captured", params={"range": "all"},
    ).json()

    assert set(body.keys()) == {"total_savings", "total_spent", "lists", "range"}
    entry = next(
        l for l in body["lists"]
        if l["shopping_list_id"] == seeded["shopping_list_id"]
    )
    assert entry["picked_total"] == 4.5
    assert entry["list_total"] == 10.5
    assert entry["savings"] == 6.0
    assert is_valid_datetime(entry["completed_at"])
    assert body["total_savings"] >= 6.0
    assert body["total_spent"] >= 4.5


#endregion savings captured

#region ---------------- price drops ----------------


def test__price_drops__CurrentOfferBelowAllHistory__ReportedAsNewLow(api):
    seeded = seed_purchase(price_now=10.0, price_was=12.0, finish=False, tick=False)
    # A price update archives the prior offer → historic low = 10.0.
    patch = requests.patch(f"{BASE}/products/{seeded['product_id']}", json={
        "price_now": 8.0, "price_was": 12.0,
    })
    assert patch.status_code in (200, 204), patch.text

    rows = requests.get(f"{REPORTS}/price-drops", params={"limit": 20}).json()["rows"]

    row = next(r for r in rows if r["product_id"] == seeded["product_id"])
    assert set(row.keys()) == {
        "product_id", "name", "store_id", "store_name", "has_image",
        "price_now", "previous_low", "drop_amount", "drop_percent",
        "linked_stock_item_id", "linked_stock_item_name",
    }
    assert row["price_now"] == 8.0
    assert row["previous_low"] == 10.0
    assert row["drop_amount"] == 2.0
    assert row["drop_percent"] == 20
    assert row["store_name"] == seeded["store_name"]


def test__price_drops__ProductWithNoHistory__NeverANewLow(api):
    # Only one price ever seen → "new low" would be dishonest (Honesty §2.4).
    seeded = seed_purchase(price_now=1.0, price_was=2.0, finish=False, tick=False)

    rows = requests.get(f"{REPORTS}/price-drops", params={"limit": 20}).json()["rows"]

    assert seeded["product_id"] not in {r["product_id"] for r in rows}


def _seed_drop(price_from: float, price_to: float) -> str:
    """One tracked product whose current offer is a new low: created at
    ``price_from`` (archived to history by the PATCH), now ``price_to``.
    Returns the product id."""
    seeded = seed_purchase(price_now=price_from, price_was=price_from + 2.0,
                           finish=False, tick=False)
    patch = requests.patch(f"{BASE}/products/{seeded['product_id']}", json={
        "price_now": price_to, "price_was": price_from + 2.0,
    })
    assert patch.status_code in (200, 204), patch.text
    return seeded["product_id"]


def test__price_drops__Ranking__PercentDescThenAmountDesc(api):
    # 50% off ranks over 20% off; between the two 20%s, the bigger dollar
    # drop ($4 on 20→16) ranks over the smaller ($2 on 10→8).
    big_pct = _seed_drop(10.0, 5.0)      # 50%, $5
    tie_small = _seed_drop(10.0, 8.0)    # 20%, $2
    tie_big = _seed_drop(20.0, 16.0)     # 20%, $4

    rows = requests.get(f"{REPORTS}/price-drops", params={"limit": 20}).json()["rows"]

    ours = [r["product_id"] for r in rows
            if r["product_id"] in {big_pct, tie_small, tie_big}]
    assert ours == [big_pct, tie_big, tie_small]


def test__price_drops__InactiveProduct__Excluded(api):
    product_id = _seed_drop(10.0, 8.0)
    rows = requests.get(f"{REPORTS}/price-drops", params={"limit": 20}).json()["rows"]
    assert product_id in {r["product_id"] for r in rows}

    patch = requests.patch(f"{BASE}/products/{product_id}", json={"is_active": False})
    assert patch.status_code in (200, 204), patch.text

    rows = requests.get(f"{REPORTS}/price-drops", params={"limit": 20}).json()["rows"]
    assert product_id not in {r["product_id"] for r in rows}


def test__price_drops__LimitClampsToOneThroughTwenty__DefaultFive(api):
    # Six genuine drops on the board so the default-5 slice is observable.
    for i in range(6):
        _seed_drop(10.0 + i, 5.0)

    assert len(requests.get(f"{REPORTS}/price-drops", params={"limit": "0"}).json()["rows"]) == 1
    assert len(requests.get(f"{REPORTS}/price-drops", params={"limit": "-3"}).json()["rows"]) == 1
    assert len(requests.get(f"{REPORTS}/price-drops", params={"limit": "999"}).json()["rows"]) <= 20
    # Missing or unparseable limit → the default 5.
    assert len(requests.get(f"{REPORTS}/price-drops").json()["rows"]) == 5
    assert len(requests.get(f"{REPORTS}/price-drops", params={"limit": "abc"}).json()["rows"]) == 5


#endregion price drops

#region ---------------- meals cooked ----------------


def test__meals_cooked__RecipeCookedTwice__CountsEventsAndPortionsSeparately(api):
    token = _token()
    recipe = requests.post(f"{BASE}/recipes", json={"name": f"{token} stew"})
    assert recipe.status_code == 201, recipe.text
    recipe_id = recipe.json()["recipe_id"]
    for meals in (3, 2):
        cook = requests.post(
            f"{BASE}/recipes/{recipe_id}/cook", json={"meals_cooked": meals},
        )
        assert cook.status_code == 200, cook.text

    body = requests.get(
        f"{REPORTS}/meals-cooked", params={"range": "all", "limit": 50},
    ).json()

    assert set(body.keys()) == {
        "range", "cook_count", "meals_total", "distinct_recipes",
        "total_recipes", "uncooked_recipes", "top_recipes", "timeline",
    }
    top = next(r for r in body["top_recipes"] if r["recipe_id"] == recipe_id)
    assert top["recipe_name"] == f"{token} stew"
    assert top["cook_count"] == 2      # two cooking sessions...
    assert top["meals_total"] == 5     # ...feeding five meals total
    assert body["cook_count"] >= 2
    assert body["meals_total"] >= 5
    assert sum(p["cook_count"] for p in body["timeline"]) == body["cook_count"]


def test__meals_cooked__Repertoire__CountsDistinctRecipesAndTheUntouchedTail(api):
    # §3.8 — "14 cooks" and "9 different recipes" are different facts, and only
    # the second one sends you back to the cookbook. Two cooks of ONE recipe is
    # the case that separates them.
    token = _token()
    recipe_id = requests.post(
        f"{BASE}/recipes", json={"name": f"{token} laksa"},
    ).json()["recipe_id"]
    for meals in (2, 2):
        requests.post(f"{BASE}/recipes/{recipe_id}/cook", json={"meals_cooked": meals})
    # A second recipe that is never cooked — it must land in the untouched tail.
    requests.post(f"{BASE}/recipes", json={"name": f"{token} never made"})

    body = requests.get(
        f"{REPORTS}/meals-cooked", params={"range": "all", "limit": 50},
    ).json()

    assert body["distinct_recipes"] < body["cook_count"]
    assert body["total_recipes"] >= 2
    # The uncooked tail is a fact about the cookbook, NOT about the range — it
    # is always measured over the last 365 days, so a 30-day view doesn't report
    # that you've abandoned almost everything you own.
    assert body["uncooked_recipes"] >= 1
    assert body["uncooked_recipes"] <= body["total_recipes"]


def test__meals_cooked__BoundedRange__TimelineSpansTheWindowIncludingQuietBuckets(api):
    # Only buckets that HAD a cook used to be emitted, so ten scattered cooking
    # days came back as ten evenly-spaced points and the quiet days between them
    # disappeared — a month that was mostly quiet drew as an unbroken run of
    # activity. The gaps are the point of the chart.
    token = _token()
    recipe_id = requests.post(
        f"{BASE}/recipes", json={"name": f"{token} congee"},
    ).json()["recipe_id"]
    requests.post(f"{BASE}/recipes/{recipe_id}/cook", json={"meals_cooked": 2})

    body = requests.get(f"{REPORTS}/meals-cooked", params={"range": "30d"}).json()

    timeline = body["timeline"]
    # 30 daily buckets plus today's.
    assert len(timeline) == 31
    assert [p["date"] for p in timeline] == sorted(p["date"] for p in timeline)
    assert any(p["cook_count"] == 0 for p in timeline)
    # Filling the gaps must not invent or lose any cooks.
    assert sum(p["cook_count"] for p in timeline) == body["cook_count"]
    assert sum(p["meals_total"] for p in timeline) == body["meals_total"]


#endregion meals cooked

#region ---------------- spend by category ----------------


def test__spend_by_category__ItemWithStockGroup__BucketsUnderGroupName(api):
    token = _token()
    group = requests.post(f"{BASE}/stock-groups", json={"name": f"{token} snacks"})
    assert group.status_code == 201, group.text
    seed_purchase(price_now=4.5, stock_group_id=group.json()["stock_group_id"])

    body = requests.get(
        f"{REPORTS}/spend-by-category", params={"range": "all"},
    ).json()

    assert set(body.keys()) == {"range", "total_spent", "rows"}
    row = next(r for r in body["rows"] if r["category"] == f"{token} snacks")
    assert set(row.keys()) == {"category", "spent", "item_count", "share_pct"}
    assert row["spent"] == 4.5
    assert row["item_count"] == 1
    assert 0 < row["share_pct"] <= 100
    assert body["total_spent"] >= 4.5


#endregion spend by category

#region ---------------- spend year-over-year ----------------


def test__spend_year_over_year__NewCategoryThisWindow__NoRateOfChangeClaimed(api):
    token = _token()
    group = requests.post(f"{BASE}/stock-groups", json={"name": f"{token} treats"})
    assert group.status_code == 201, group.text
    seed_purchase(price_now=4.5, stock_group_id=group.json()["stock_group_id"])

    body = requests.get(f"{REPORTS}/spend-year-over-year").json()

    assert set(body.keys()) == {
        "range", "window_days", "current_total", "previous_total",
        "delta", "delta_pct", "rows",
    }
    assert body["range"] == "1y"
    assert body["window_days"] == 365
    row = next(r for r in body["rows"] if r["category"] == f"{token} treats")
    assert row["current"] == 4.5
    assert row["previous"] == 0.0
    assert row["delta"] == 4.5
    # No prior spend → delta_pct is None, never "+∞%" (P3 Honest).
    assert row["delta_pct"] is None


def test__spend_year_over_year__RangeAll__RejectedAsUnbounded(api):
    resp = requests.get(f"{REPORTS}/spend-year-over-year", params={"range": "all"})

    assert_problem(resp, 400, title="range=all is not supported")


#endregion spend year-over-year

#region ---------------- item price movers ----------------


def _stock_item(name: str) -> str:
    level = requests.get(f"{BASE}/stock-levels").json()["items"][0]["stock_level_id"]
    resp = requests.post(f"{BASE}/stock-items", json={
        "name": name, "stock_level_id": level,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["stock_item_id"]


def _observe(item_id: str, *, price: float, measure: float, unit: str, on: str) -> None:
    resp = requests.post(f"{BASE}/stock-items/{item_id}/price-observations", json={
        "total_price": price, "total_measure": measure, "unit": unit,
        "observed_at": on,
    })
    assert resp.status_code == 204, resp.text


def _row_for(body: dict, item_id: str) -> dict | None:
    return next((r for r in body["rows"] if r["stock_item_id"] == item_id), None)


def test__item_price_movers__TwoObservations__ReportsTheDriftPerCanonicalUnit(api):
    # REPORTS_PAGE_REVIEW.md section 5 - "which of MY items got more
    # expensive?", the largest missing widget on the page and the only price
    # report an install with no product catalogue can have (FU-703 D3).
    token = _token()
    item = _stock_item(f"{token} rolled oats")
    # $4 for 2kg = $0.20/100g, then $6 for 2kg = $0.30/100g. The comparison is
    # per-unit, so the pack size is not allowed to look like a price change.
    _observe(item, price=4.0, measure=2.0, unit="kg", on="2026-01-05T00:00:00+00:00")
    _observe(item, price=6.0, measure=2.0, unit="kg", on="2026-02-05T00:00:00+00:00")

    body = requests.get(f"{REPORTS}/item-price-movers", params={"range": "all"}).json()

    assert set(body.keys()) == {
        "range", "rows", "items_with_movement", "items_with_one_observation",
        "items_with_mixed_units", "items_unchanged",
    }
    row = _row_for(body, item)
    assert row is not None
    assert row["unit"] == "100g"
    assert row["first_price"] == 0.2
    assert row["last_price"] == 0.3
    assert row["delta"] == 0.1
    assert row["delta_pct"] == 50.0
    assert row["observation_count"] == 2
    assert row["first_observed_on"] == "2026-01-05"
    assert row["last_observed_on"] == "2026-02-05"


def test__item_price_movers__SamePricePaidForABiggerPack__ReadsAsAFall(api):
    # The per-unit normalisation earning its keep: paying the same $6 for twice
    # as much is a 50% fall, and a report comparing totals would call it flat.
    token = _token()
    item = _stock_item(f"{token} flour")
    _observe(item, price=6.0, measure=1.0, unit="kg", on="2026-01-05T00:00:00+00:00")
    _observe(item, price=6.0, measure=2.0, unit="kg", on="2026-02-05T00:00:00+00:00")

    body = requests.get(f"{REPORTS}/item-price-movers", params={"range": "all"}).json()

    row = _row_for(body, item)
    assert row["first_price"] == 0.6
    assert row["last_price"] == 0.3
    assert row["delta_pct"] == -50.0


def test__item_price_movers__SmallPack__QuotesTheShelfDenominatorTheChartUses(api):
    # The bug this pins was found by driving it: the report said "$24.00/L" for
    # an item whose own chart, one click away, said "$2.40/100ml". Same price,
    # two languages. The per-unit maths runs in the canonical unit, but the
    # shelf convention flips below a full litre, and `display_denominator_for`
    # is the one authority on that flip — the widget, the chart and now this
    # report all resolve it the same way (R-003).
    token = _token()
    item = _stock_item(f"{token} vanilla essence")
    _observe(item, price=4.0, measure=100.0, unit="ml", on="2026-01-05T00:00:00+00:00")
    _observe(item, price=6.0, measure=100.0, unit="ml", on="2026-02-05T00:00:00+00:00")

    body = requests.get(f"{REPORTS}/item-price-movers", params={"range": "all"}).json()

    row = _row_for(body, item)
    assert row["unit"] == "100ml"
    # $4 per 100ml — NOT $40.00/L, which is the same fact in a denominator this
    # household never sees on a shelf.
    assert row["first_price"] == 4.0
    assert row["last_price"] == 6.0
    assert row["delta"] == 2.0
    assert row["delta_pct"] == 50.0


def test__item_price_movers__OneObservation__IsCountedNotReported(api):
    # One reading is a price, not a movement - and R-041 says an aggregate
    # states what it was built from, so it is counted rather than dropped in
    # silence.
    token = _token()
    item = _stock_item(f"{token} saffron")
    _observe(item, price=9.0, measure=1.0, unit="kg", on="2026-02-05T00:00:00+00:00")

    body = requests.get(f"{REPORTS}/item-price-movers", params={"range": "all"}).json()

    assert _row_for(body, item) is None
    assert body["items_with_one_observation"] >= 1


def test__item_price_movers__SamePriceTwice__IsSteadyNotAMover(api):
    # Two readings at the same price is an answer, not a change. Counting it as
    # a mover is what made the card claim "7 of your items changed price" and
    # then render four of them — the flat ones belonged to neither the dearer
    # nor the cheaper list, so they vanished between the headline and the rows.
    token = _token()
    item = _stock_item(f"{token} bicarb")
    _observe(item, price=3.0, measure=1.0, unit="kg", on="2026-01-05T00:00:00+00:00")
    _observe(item, price=3.0, measure=1.0, unit="kg", on="2026-02-05T00:00:00+00:00")

    body = requests.get(f"{REPORTS}/item-price-movers", params={"range": "all"}).json()

    assert _row_for(body, item) is None
    assert body["items_unchanged"] >= 1
    # Every returned row really moved, in one direction or the other.
    assert all(r["delta"] != 0 for r in body["rows"])


def test__item_price_movers__MixedDimensions__ComparesOnlyTheActiveOne(api):
    # A litre of something and an each-of-something cannot be compared
    # per-unit. The row is built from the observations sharing the item's
    # *active* dimension - the dimension of its latest reading, the same rule
    # the buy verdict's baseline uses - and the mismatch is reported.
    token = _token()
    item = _stock_item(f"{token} yoghurt")
    _observe(item, price=8.0, measure=4.0, unit="ea", on="2026-01-05T00:00:00+00:00")
    _observe(item, price=4.0, measure=1.0, unit="L", on="2026-02-05T00:00:00+00:00")
    _observe(item, price=6.0, measure=1.0, unit="L", on="2026-03-05T00:00:00+00:00")

    body = requests.get(f"{REPORTS}/item-price-movers", params={"range": "all"}).json()

    row = _row_for(body, item)
    assert row["unit"] == "100ml"
    assert row["observation_count"] == 2      # the "ea" reading is not in it
    assert row["first_price"] == 0.4 and row["last_price"] == 0.6
    assert body["items_with_mixed_units"] >= 1


def test__item_price_movers__Range__ExcludesObservationsOutsideTheWindow(api):
    # The bounded-range branch, which is where FU-813's naive-vs-aware crash
    # lived on a sibling report: an old reading plus a recent one is not a
    # movement inside a 30-day window.
    token = _token()
    item = _stock_item(f"{token} rice")
    _observe(item, price=4.0, measure=2.0, unit="kg", on="2020-01-05T00:00:00+00:00")
    _observe(item, price=9.0, measure=1.0, unit="kg", on=_now_iso())

    windowed = requests.get(f"{REPORTS}/item-price-movers", params={"range": "30d"})
    assert windowed.status_code == 200, windowed.text
    assert _row_for(windowed.json(), item) is None

    all_time = requests.get(f"{REPORTS}/item-price-movers", params={"range": "all"}).json()
    assert _row_for(all_time, item) is not None


def test__item_price_movers__Ranking__BiggestMovementFirstEitherDirection(api):
    # "What changed" is the question, so a big fall outranks a small rise: the
    # card takes risers from the top and fallers from the bottom without a
    # second sort.
    token = _token()
    riser = _stock_item(f"{token} a riser")
    faller = _stock_item(f"{token} b faller")
    _observe(riser, price=1.0, measure=1.0, unit="kg", on="2026-01-05T00:00:00+00:00")
    _observe(riser, price=1.1, measure=1.0, unit="kg", on="2026-02-05T00:00:00+00:00")
    _observe(faller, price=10.0, measure=1.0, unit="kg", on="2026-01-05T00:00:00+00:00")
    _observe(faller, price=2.0, measure=1.0, unit="kg", on="2026-02-05T00:00:00+00:00")

    body = requests.get(
        f"{REPORTS}/item-price-movers", params={"range": "all", "limit": 50},
    ).json()

    ranks = [r["stock_item_id"] for r in body["rows"]]
    assert ranks.index(faller) < ranks.index(riser)


def test__item_price_movers__Limit__CapsTheRowsButNotTheCounts(api):
    body = requests.get(
        f"{REPORTS}/item-price-movers", params={"range": "all", "limit": 1},
    ).json()

    assert len(body["rows"]) <= 1
    # The coverage counts describe the whole pantry, not the page of rows -
    # otherwise "1 of 1" would be a lie told by a limit.
    assert body["items_with_movement"] >= len(body["rows"])
    assert requests.get(
        f"{REPORTS}/item-price-movers", params={"limit": "abc"},
    ).status_code == 200


#endregion item price movers

#region ---------------- money gate ----------------


# FU-816 / R-058 — every report that answers in dollars refuses outright when
# the install has money off. Gating the render alone was the state this page
# was in before: `ReportsPage.vue` imported no feature flag at all, so an
# install that had opted out still got spend by store, savings, spend by
# category, year-over-year and two dollar-formatted chart axes.
_MONEY_GATED = [
    ("spend-by-store", {}),
    ("savings-captured", {}),
    ("spend-by-category", {}),
    ("spend-year-over-year", {}),
    ("item-price-movers", {}),
]


@pytest.mark.parametrize("path,params", _MONEY_GATED)
def test__money_reports__MoneyDisabled__Forbidden(api, path, params):
    set_money_enabled(False)

    resp = requests.get(f"{REPORTS}/{path}", params=params)

    assert_problem(resp, 403, detail="money features are turned off")


# The counting reports are deliberately NOT gated: they are what keeps
# `/reports` worth a nav entry on a money-off install, which is why the nav
# entry stays unconditional.
@pytest.mark.parametrize(
    "path", ["most-bought-items", "meals-cooked"],
)
def test__counting_reports__MoneyDisabled__StillAnswer(api, path):
    set_money_enabled(False)

    resp = requests.get(f"{REPORTS}/{path}")

    assert resp.status_code == 200, resp.text


#endregion money gate

#region ---------------- range window ----------------


@pytest.mark.parametrize("token,days", [("30d", 30), ("90d", 90), ("1y", 365)])
def test__range_window__BoundedToken__NamesItsDatesAndLength(api, token, days):
    # FU-845 #2 — the picker said "30 days" and left the reader to guess which
    # thirty. The dates come from here so the client never re-derives them.
    body = requests.get(f"{REPORTS}/range-window", params={"range": token}).json()

    assert set(body.keys()) == {"range", "start", "end", "days"}
    assert body["range"] == token
    assert body["days"] == days
    start = date.fromisoformat(body["start"])
    end = date.fromisoformat(body["end"])
    assert (end - start).days == days


def test__range_window__AllTime__StartsAtTheEarliestRecord(api):
    # "All time" names real dates too (2026-09-27), from the oldest record any
    # report reads. A shopping list guarantees there is one.
    assert requests.post(f"{BASE}/shopping-lists", json={"name": "window probe"}).status_code == 201

    body = requests.get(f"{REPORTS}/range-window", params={"range": "all"}).json()

    assert body["start"] is not None
    assert date.fromisoformat(body["start"]) <= date.fromisoformat(body["end"])
    assert body["days"] is None


def test__range_window__MoneyDisabled__StillAnswers(api):
    # Page chrome, not a money surface — the range control exists on a
    # money-off install, so this must not be gated.
    set_money_enabled(False)

    resp = requests.get(f"{REPORTS}/range-window", params={"range": "30d"})

    assert resp.status_code == 200, resp.text


#endregion range window


def test__spend_by_store__OfferPickedButNoPriceEntered__RecordsNoSpend(api):
    """An advertised price is never recorded as money you spent.

    Until 2026-09-17 finishing a list froze the chosen offer's price onto every
    ticked line, so a shop where the user typed nothing still reported spend —
    built entirely from what shops were asking that day. The owner's call was
    to make pricing explicit: "yes this means you can have no spend recorded if
    you don't record anything. That's up to the user."

    Pinned because the failure mode is silent and flattering: the numbers would
    simply reappear, and a bigger spend figure is not something anyone
    investigates.
    """
    seeded = seed_purchase(price_now=4.5, quantity=2, price_unrecorded=True)

    body = requests.get(f"{REPORTS}/spend-by-store", params={"range": "all"}).json()
    row = next((r for r in body["rows"] if r["store_id"] == seeded["store_id"]), None)

    assert row is None, "an offer price must not be recorded as spend"
    # Not dropped in silence either — it is counted as unpriced coverage.
    assert body["unpriced_lines"] >= 1
