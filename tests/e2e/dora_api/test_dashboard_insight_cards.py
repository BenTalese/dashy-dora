"""Owner feedback 2026-09-04 — the endpoints behind the reworked dashboard.

`/dashboard/use-it-up` and `/dashboard/restock-radar`.

**Two of the original four are gone** (owner batch, 2026-09-08). He axed the
*Shopping lists* card outright (*"useless, axe it"*) and folded *Before you
shop* into Restock radar (*"a lot of crossover … I'm inclined to axe before you
shop"*), so `/dashboard/lists` and `/dashboard/before-you-shop` were deleted
with their only consumers and their tests went with them. The one rule this
file loses in that trade is *Before you shop*'s list-membership filter, which
was not carried over — see `DORA_FOLLOWUPS.md` FU-897.

**Why these have tests when the verification stance is manual-first**
(`DORA_VERIFY_TRIAGE.md`): the stance says automate only what pins a *stable,
low-churn contract that is expensive to re-check by hand*. The card layouts are
neither — they will churn, and they are trivial to eyeball. But each of these
endpoints has exactly one rule that is invisible in a browser and expensive to
set up by hand:

  use-it-up        a recipe is listed only if it *requires* an expiring item —
                   an optional ingredient must not pull it in.
  restock-radar    only items *currently* in the band — an item that went out
                   and was restocked must drop off — and only ones that changed
                   band *recently*, which is a clock you cannot wind forward in
                   a browser.

Get any of those wrong and the card still renders plausibly, which is precisely
the failure a manual walk misses.

Delta-style like `test_dashboard_router.py`: create through the real endpoints
and assert on the rows we created, so the seeded dataset never leaks into an
expectation.
"""
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import requests

from dora_api.app import app
from dora_api.domain.entities.stock_item import StockItem
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

BASE = "http://localhost:5170/api"
USE_IT_UP = f"{BASE}/dashboard/use-it-up"
RESTOCK_RADAR = f"{BASE}/dashboard/restock-radar"
STOCK_ITEMS = f"{BASE}/stock-items"
SHOPPING_LISTS = f"{BASE}/shopping-lists"
RECIPES = f"{BASE}/recipes"
MEAL_PLANS = f"{BASE}/meal-plans"

#region ---------------- helpers ----------------


def _today():
    from datetime import date
    return date.fromisoformat(requests.get(f"{MEAL_PLANS}/today").json()["today"])


def _stock_level_id(sequence: int) -> str:
    levels = requests.get(f"{BASE}/stock-levels").json()["items"]
    return next(l["stock_level_id"] for l in levels if l["sequence"] == sequence)


def _make_item(**body) -> dict:
    """Create a stock item. `stock_level_id` is required by the endpoint, so it
    defaults to Stocked here — the expiry tests care about dates, not levels.

    ⚠️ Every card under test shows a **top-N slice** of a seeded dataset that
    already fills it (6 restock rows, 4 use-it-up items). A freshly created item
    is therefore only observable if it out-ranks the seed under that card's own
    sort. Each test below says how it does that; an assertion that "my item is
    in the list" without that consideration is the trap this note exists to
    stop.
    """
    payload = {
        "name": f"Insight Item {uuid4().hex[:8]}",
        "stock_level_id": _stock_level_id(0),
        **body,
    }
    resp = requests.post(STOCK_ITEMS, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _names(rows) -> set[str]:
    return {r["name"] for r in rows}

#endregion helpers

#region ---------------- use-it-up ----------------


def test__use_it_up__ResponseShape__CarriesItemsRecipesAndWindow(api):
    body = requests.get(USE_IT_UP).json()
    assert body.keys() == {"items", "recipes", "window_days"}
    # The window is the household's own `expiring_soon_window_days`, so the card
    # can name it rather than hardcoding "this week" over a setting that might
    # say 3 or 30.
    assert isinstance(body["window_days"], int) and body["window_days"] >= 1


def test__use_it_up__ItemExpiringInsideWindow__IsListedWithDaysRemaining(api):
    # Dated today so it sorts near the front of the seeded set (which runs from
    # 3 days expired to 4 days out) and can't be pushed off the 5-row slice.
    # Today is also the interesting boundary: still usable, no days left.
    due = _today()
    item = _make_item(expiry_date=due.isoformat())

    rows = requests.get(USE_IT_UP).json()["items"]
    mine = next(r for r in rows if r["stock_item_id"] == item["stock_item_id"])
    assert mine["days_remaining"] == 0
    # `is_expired` is strictly *past* its date — an item due today has not
    # expired, and rendering it as a loss would be wrong by a day.
    assert mine["is_expired"] is False


def test__use_it_up__ItemExpiringBeyondWindow__IsNotListed(api):
    window = requests.get(USE_IT_UP).json()["window_days"]
    far = _today() + timedelta(days=window + 30)
    item = _make_item(expiry_date=far.isoformat())

    rows = requests.get(USE_IT_UP).json()["items"]
    assert item["stock_item_id"] not in {r["stock_item_id"] for r in rows}


def test__use_it_up__OptionalIngredient__DoesNotPullTheRecipeIn(api):
    """The rule a browser can't show you.

    "Recipes that use it up" has to mean *require*. A recipe that lists the
    expiring item as optional does not use it up — you'd cook it and the
    spinach would still be there — so suggesting it would be a lie in exactly
    the situation the card exists for.
    """
    # Expired a week ago: sorts to the very front, so both probe recipes are
    # certain to be evaluated against a listed item.
    item = _make_item(expiry_date=(_today() - timedelta(days=7)).isoformat())
    required = requests.post(RECIPES, json={
        "name": f"Requires It {uuid4().hex[:8]}",
        "ingredients": [
            {"raw_text": item["name"], "stock_item_id": item["stock_item_id"]},
        ],
    })
    assert required.status_code == 201, required.text
    optional = requests.post(RECIPES, json={
        "name": f"Optional Only {uuid4().hex[:8]}",
        "ingredients": [
            {
                "raw_text": item["name"],
                "stock_item_id": item["stock_item_id"],
                "is_optional": True,
            },
        ],
    })
    assert optional.status_code == 201, optional.text

    listed = _names(requests.get(USE_IT_UP).json()["recipes"])
    assert required.json()["name"] in listed
    assert optional.json()["name"] not in listed

#endregion use-it-up

#region ---------------- restock radar ----------------


def test__restock_radar__ResponseShape__CarriesOneListAndItsWindow(api):
    """One list since the 2026-09-08 batch, not two columns.

    The band it used to sort into is now the level dot at the head of the row,
    so the shape carries `level_sequence` + `level_name` — get those wrong and
    every row renders a grey dot, which looks deliberate.
    """
    body = requests.get(RESTOCK_RADAR).json()
    assert body.keys() == {"rows", "window_days"}
    assert body["window_days"] >= 1
    for row in body["rows"]:
        for field in (
            "stock_item_id", "name", "changed_at", "is_essential",
            "level_sequence", "level_name", "band", "is_planned",
        ):
            assert field in row, f"{field} missing from {row.get('name')}"
        assert row["band"] in ("low", "out")


def test__restock_radar__LowAndOut__ShareOneRecencyOrderedList(api):
    """Both bands, one list, most recent first.

    Two freshly levelled items are the two most recent band changes in the
    dataset by construction, so they take the top two rows whichever band they
    are in — which is the ordering promise, and the thing the old per-column
    sort could not make.
    """
    out_item = _make_item(stock_level_id=_stock_level_id(2))
    low_item = _make_item(stock_level_id=_stock_level_id(1))

    rows = requests.get(RESTOCK_RADAR).json()["rows"]
    top_two = {r["stock_item_id"] for r in rows[:2]}
    assert out_item["stock_item_id"] in top_two
    assert low_item["stock_item_id"] in top_two
    bands = {r["stock_item_id"]: r["band"] for r in rows}
    assert bands[out_item["stock_item_id"]] == "out"
    assert bands[low_item["stock_item_id"]] == "low"


def test__restock_radar__RestockedItem__LeavesTheRadar(api):
    """Present tense, not history.

    "Recently ran out" about something you have since restocked is a diary
    entry, not a restock cue — and it is the failure mode the old lifetime
    ranking had, where the card looked identical week after week.
    """
    item = _make_item(stock_level_id=_stock_level_id(2))
    rows = requests.get(RESTOCK_RADAR).json()["rows"]
    assert item["stock_item_id"] in {r["stock_item_id"] for r in rows}

    restock = requests.patch(
        f"{STOCK_ITEMS}/{item['stock_item_id']}",
        json={"stock_level_id": _stock_level_id(0)},
    )
    assert restock.status_code == 204, restock.text

    rows = requests.get(RESTOCK_RADAR).json()["rows"]
    assert item["stock_item_id"] not in {r["stock_item_id"] for r in rows}


def test__restock_radar__LongStandingLow__IsOutsideTheWindow(api):
    """The 2026-09-08 cutoff: *"don't show stuff that has been low/out for a
    long time"*.

    A clock rule, so a browser walk cannot see it without waiting a month — the
    exact shape this file is for. Driven by back-dating
    `stock_level_last_updated` directly, because no endpoint lets you claim a
    level changed in the past (and none should).
    """
    item = _make_item(stock_level_id=_stock_level_id(2))
    window = requests.get(RESTOCK_RADAR).json()["window_days"]

    with app.app_context():
        repository = SqlAlchemyRepository()
        entity = repository.get(StockItem).by_id(UUID(item["stock_item_id"]))
        assert entity is not None
        entity.stock_level_last_updated = (
            datetime.now(timezone.utc).replace(tzinfo=None)
            - timedelta(days=window + 1)
        )
        repository.save_changes()

    rows = requests.get(RESTOCK_RADAR).json()["rows"]
    assert item["stock_item_id"] not in {r["stock_item_id"] for r in rows}


def test__restock_radar__AwareStoredInstant__ComparesWithoutTypeError(api):
    """Postgres reads `stock_level_last_updated` back aware, SQLite naive; the
    cutoff must compare against either (R-098). The aware value is set on the
    in-session entity so the handler sees exactly what Postgres would hand it.
    """
    from dora_api.features.dashboard.get_restock_radar import GetRestockRadarHandler

    item = _make_item(stock_level_id=_stock_level_id(2))

    with app.app_context():
        repository = SqlAlchemyRepository()
        entity = repository.get(StockItem).by_id(UUID(item["stock_item_id"]))
        assert entity is not None
        entity.stock_level_last_updated = datetime.now(timezone.utc)
        try:
            dto = GetRestockRadarHandler(repository).handle()
        finally:
            repository.session.rollback()

    assert item["stock_item_id"] in {str(r.stock_item_id) for r in dto.rows}


def test__restock_radar__PlannedMeal__FlagsTheRowAsPlanned(api):
    """`is_planned` is what survived the "Before you shop" merge.

    The chip is the only thing on the card that distinguishes "you're out of
    this" from "you're out of this *and Thursday's dinner needs it*", and it is
    invisible in a browser without building a recipe and a plan first.
    """
    item = _make_item(stock_level_id=_stock_level_id(2))
    recipe = requests.post(RECIPES, json={
        "name": f"Planned Radar {uuid4().hex[:8]}",
        "ingredients": [
            {"raw_text": item["name"], "stock_item_id": item["stock_item_id"]},
        ],
    })
    assert recipe.status_code == 201, recipe.text

    rows = requests.get(RESTOCK_RADAR).json()["rows"]
    mine = next(r for r in rows if r["stock_item_id"] == item["stock_item_id"])
    # A recipe alone is not demand — nothing is planned yet.
    assert mine["is_planned"] is False

    plan = requests.post(MEAL_PLANS, json={"start_date": _today().isoformat()})
    assert plan.status_code == 201, plan.text
    entry = requests.patch(
        f"{MEAL_PLANS}/{plan.json()['meal_plan_id']}",
        json={"entries": [{
            "recipe_id": recipe.json()["recipe_id"],
            "scheduled_for": _today().isoformat(),
            "slot": "Dinner",
            "servings": 2,
        }]},
    )
    assert entry.status_code in (200, 204), entry.text

    rows = requests.get(RESTOCK_RADAR).json()["rows"]
    mine = next(r for r in rows if r["stock_item_id"] == item["stock_item_id"])
    assert mine["is_planned"] is True

def test__restock_radar__ItemWithoutLevel__IsSkippedNot500(api):
    """A deleted level nulls `stock_level_id` (`ondelete="SET NULL"`); the card
    must skip such an item like `get_planned_demand` does, not 500 on
    `None.sequence` (finalisation 08-R1). Create requires a level, so the FK
    is nulled by targeted SQL — the sanctioned state-setup escape hatch."""
    from sqlalchemy import text
    from dora_api.app import db
    from tests.support import uuid_bind

    orphan = _make_item(stock_level_id=_stock_level_id(1))
    with app.app_context(), db.engine.begin() as conn:
        conn.execute(
            text('UPDATE "StockItem" SET stock_level_id = NULL WHERE id = :id'),
            {"id": uuid_bind(orphan["stock_item_id"])},
        )

    resp = requests.get(RESTOCK_RADAR)

    assert resp.status_code == 200, resp.text
    assert orphan["stock_item_id"] not in {r["stock_item_id"] for r in resp.json()["rows"]}


#endregion restock radar
