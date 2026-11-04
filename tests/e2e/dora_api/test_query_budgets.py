"""FU-534 — query-count / N+1 budget guards on the hot read endpoints.

The single most recurrent defect class in this codebase is noload / N+1
(cookbook filters, reports counts, stock-group counts, the FU-533 PATCH
bugs). Functional tests can't catch these: a page returns *correct data*
while issuing 10x the queries, then a refactor silently makes it 100x.
Rule R-032 (noload include-discipline) is the standing fix; these tests are
its automated net.

Approach — the ratio test (per `test_recipes_query_count.py`, FU-138):
seed N more of the entity an endpoint fans out over, and assert the SELECT
count grows by a small CONSTANT, not by ~N. A hard ceiling would be brittle
as new batched lookups land; "adding N rows must not add ~N SELECTs" pins
the actual invariant (no per-row query) and survives benign query-shape
shifts. Each new IN-list shard is a handful of extra SELECTs, well under
the per-entity budget below.

If one of these fails, an endpoint's hot path went from a batched lookup to
a per-row one — look for a new `for x in items: repository.get(...)` loop or
a relationship read on an un-`.include`d load (R-032) in that feature.
"""
import requests

from tests.e2e.dora_api._query_counter import SelectCounter
from tests.factories import make_stock_item


BASE = "http://localhost:5170/api"

# Big enough that an honest N+1 (one extra SELECT per row) is loud above the
# per-call constant overhead; small enough to stay well under a second.
EXTRA = 10

# Per-entity ceiling for the (loaded - baseline) SELECT delta. An N+1
# regression pushes this to >=1.0 per entity; the batched handlers sit near 0.
# Set generously so a benign extra IN-load shard doesn't flake.
PER_ENTITY_BUDGET = 0.5
BUDGET = EXTRA * PER_ENTITY_BUDGET


def _stock_level_id() -> str:
    return requests.get(f"{BASE}/stock-levels").json()["items"][0]["stock_level_id"]


def _selects(url: str) -> int:
    with SelectCounter() as qc:
        resp = requests.get(url)
        assert resp.status_code == 200, resp.text
    return qc.count


def _assert_flat(baseline: int, loaded: int, endpoint: str, hint: str) -> None:
    delta = loaded - baseline
    assert delta < BUDGET, (
        f"{endpoint} looks N+1: adding {EXTRA} rows grew the SELECT count by "
        f"{delta} (baseline {baseline} -> {loaded}); per-entity budget is "
        f"{PER_ENTITY_BUDGET} (total {BUDGET}). {hint}"
    )


# ── GET /api/stock-items — the highest fan-out read (stock_level / location /
#    group / products per row); the noload family's home turf. ──────────────
def test__stock_items_list__select_count_flat_as_items_grow(api):
    url = f"{BASE}/stock-items?limit=500"
    baseline = _selects(url)

    level = _stock_level_id()
    for i in range(EXTRA):
        make_stock_item(stock_level_id=level, name=f"_fu534_item_{i}")

    loaded = _selects(url)
    _assert_flat(
        baseline, loaded, "GET /stock-items",
        "Check get_stock_items.py for a per-item relationship read off an "
        "un-included load (R-032).",
    )


# ── GET /api/dashboard/summary — aggregates across every entity; top noload
#    risk. Adding stock items must not scale its query count. ────────────────
def test__dashboard_summary__select_count_flat_as_stock_grows(api):
    url = f"{BASE}/dashboard/summary"
    baseline = _selects(url)

    level = _stock_level_id()
    for i in range(EXTRA):
        make_stock_item(stock_level_id=level, name=f"_fu534_dash_{i}")

    loaded = _selects(url)
    _assert_flat(
        baseline, loaded, "GET /dashboard/summary",
        "A summary card started fetching per-item instead of aggregating.",
    )


# ── GET /api/shopping-lists/<id> — the line -> product -> offer -> store
#    chain is a classic per-line N+1. Adding lines to ONE list must not scale
#    its detail query count. ─────────────────────────────────────────────────
def test__shopping_list_detail__select_count_flat_as_lines_grow(api):
    list_id = requests.post(
        f"{BASE}/shopping-lists", json={"name": "_fu534_list"}
    ).json()["shopping_list_id"]
    url = f"{BASE}/shopping-lists/{list_id}"
    baseline = _selects(url)

    level = _stock_level_id()
    for i in range(EXTRA):
        item = make_stock_item(stock_level_id=level, name=f"_fu534_line_{i}")
        resp = requests.post(
            f"{BASE}/shopping-lists/{list_id}/lines",
            json={"stock_item_id": item["stock_item_id"], "quantity": 2},
        )
        assert resp.status_code in (200, 201), resp.text

    loaded = _selects(url)
    _assert_flat(
        baseline, loaded, "GET /shopping-lists/<id>",
        "The line detail is fetching product/offer/store per line instead of "
        "batching.",
    )


# ── GET /api/recipes?cookable=true — locks the 2026-07-10 identity-map fix
#    (the cookability/expiring maps must stay batched). ─────────────────────
def test__recipes_cookable_filter__select_count_flat_as_recipes_grow(api):
    url = f"{BASE}/recipes?cookable=true&limit=500"
    baseline = _selects(url)

    for i in range(EXTRA):
        resp = requests.post(
            f"{BASE}/recipes", json={"name": f"_fu534_recipe_{i}", "ingredients": []}
        )
        assert resp.status_code in (200, 201), resp.text

    loaded = _selects(url)
    _assert_flat(
        baseline, loaded, "GET /recipes?cookable=true",
        "The cookability/expiring maps regressed to per-recipe loads — see the "
        "identity-map trap documented in get_recipes.py _restrict_query.",
    )


# ── GET /api/meal-plans — FU-908: a plan read grades only the recipes the plans
#    reference, never the whole cookbook. The planner refetches after every edit,
#    so an unbounded cookability load here is paid on each servings tap. ───────
def test__meal_plans__cookability_scoped_to_planned_recipes(api, monkeypatch):
    from dora_api.features.meal_plans import get_meal_plans as module

    seen: list[set | None] = []
    real = module.load_recipe_cookability

    def _spy(repository, recipe_ids=None):
        seen.append(None if recipe_ids is None else set(recipe_ids))
        return real(repository, recipe_ids)

    monkeypatch.setattr(module, "load_recipe_cookability", _spy)

    def _recipe(name: str) -> str:
        resp = requests.post(f"{BASE}/recipes", json={"name": name, "ingredients": []})
        assert resp.status_code in (200, 201), resp.text
        return resp.json()["recipe_id"]

    today = requests.get(f"{BASE}/meal-plans/today").json()["today"]
    slot = requests.get(f"{BASE}/meal-slots").json()[0]["name"]
    planned = _recipe("_fu908_planned")
    plan = requests.post(f"{BASE}/meal-plans", json={
        "name": "_fu908_plan", "start_date": today,
        "entries": [{"recipe_id": planned, "scheduled_for": today, "slot": slot}],
    })
    assert plan.status_code == 201, plan.text
    plan_id = plan.json()["meal_plan_id"]
    unplanned = {_recipe(f"_fu908_unplanned_{i}") for i in range(EXTRA)}

    seen.clear()
    for url in (f"{BASE}/meal-plans", f"{BASE}/meal-plans?filter=meal_plan_id:eq:{plan_id}"):
        resp = requests.get(url)
        assert resp.status_code == 200, resp.text

    assert len(seen) == 2, seen
    for ids in seen:
        assert ids is not None, "a meal-plan read loaded the whole cookbook's cookability"
        assert planned in {str(i) for i in ids}
        assert not unplanned & {str(i) for i in ids}
