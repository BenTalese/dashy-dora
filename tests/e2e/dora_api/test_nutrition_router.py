"""e2e for /api/nutrition — the unified food lookup and source status.

The unit suite (`tests/test_nutrition_lookup.py`) pins ranking and source
fan-out with the network stubbed. What only a real request can prove is the
**repository query path**: `contains` / `Or` / `in_` against real
`NutritionFood` + `NutritionPortion` rows, the auth posture, and that portions
are batch-loaded onto results rather than coming back empty (the mapping has no
relationship object by design, so a missed join fails silently as "no portions"
and would quietly make every recipe ingredient unconvertible).
"""
from datetime import datetime, timezone
from uuid import uuid4

import requests

from dora_api.app import app
from dora_api.domain.entities.nutrition_food import (
    NUTRITION_SOURCE_USDA_SR_LEGACY, NutritionFood,
)
from dora_api.domain.entities.nutrition_portion import NutritionPortion
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from tests.factories import make_stock_item
from tests.support import assert_problem

BASE = "http://localhost:5170/api"
LOOKUP = f"{BASE}/nutrition/lookup"
SOURCES = f"{BASE}/nutrition/sources"
IMPORT = f"{BASE}/nutrition/datasets/import"


def _offline(repo) -> None:  # noqa: ANN001
    """Switch off the live sources for the duration of a test.

    Without this every text lookup reaches Open Food Facts for real — which
    makes the suite network-dependent, slow, and quietly different depending on
    whether the machine is online. The live-source fan-out is pinned with stubs
    in `tests/test_nutrition_lookup.py`; here we're testing the local query
    path, so the network stays out of it.
    """
    from dora_api.features.app_settings.access import get_or_create_app_setting
    setting = get_or_create_app_setting(repo)
    setting.nutrition_off_lookup_enabled = False
    setting.nutrition_usda_api_key = ""
    repo.save_changes()


def _seed_foods() -> dict:
    """Insert a small catalogue directly. Ids are returned so assertions can
    target rows rather than depending on whatever else the seed left behind."""
    ids = {}
    with app.app_context():
        repo = SqlAlchemyRepository()
        _offline(repo)
        now = datetime.now(timezone.utc)

        banana = NutritionFood(
            id=uuid4(), source=NUTRITION_SOURCE_USDA_SR_LEGACY, source_ref=f"b-{uuid4().hex[:8]}",
            name="Bananas, raw", kcal_per_100g=89.0, protein_g_per_100g=1.09,
            imported_at=now,
        )
        powder = NutritionFood(
            id=uuid4(), source=NUTRITION_SOURCE_USDA_SR_LEGACY, source_ref=f"p-{uuid4().hex[:8]}",
            name="Bananas, dehydrated, or banana powder", kcal_per_100g=346.0,
            imported_at=now,
        )
        beans = NutritionFood(
            id=uuid4(), source=NUTRITION_SOURCE_USDA_SR_LEGACY, source_ref=f"c-{uuid4().hex[:8]}",
            name="Baked beans, tomato sauce", kcal_per_100g=80.0,
            barcode="9300675024235", imported_at=now,
        )
        for food in (banana, powder, beans):
            repo.add(food)
        repo.add(NutritionPortion(
            id=uuid4(), nutrition_food_id=banana.id,
            amount=1, measure="medium", gram_weight=118.0,
        ))
        repo.save_changes()
        ids = {
            "banana": str(banana.id),
            "powder": str(powder.id),
            "beans": str(beans.id),
        }
    return ids


#region ---------------- auth posture ----------------


def test__nutrition__Anonymous__401OnLookupAndSources(api):
    anon = requests.Session()
    assert_problem(anon.get(f"{LOOKUP}?q=banana"), 401)
    assert_problem(anon.get(SOURCES), 401)


def test__dataset_import__UnknownDataset__IsRejectedAndNamesWhatWasSent(api):
    """The admin gate itself is pinned by test_route_auth_enforcement; this
    covers the request-shape guard behind it.

    **Asserting the echoed name is the whole point.** The original version of
    this test asserted only "400", and passed for two years' worth of the wrong
    reason: the endpoint never registered a request-body schema, so the body was
    always `None`, every dataset name became `''`, and the *download button was
    dead in production* while the test stayed green. A 400 assertion that
    doesn't check *why* can't tell a working guard from a broken pipe.
    """
    resp = requests.post(IMPORT, json={"source": "not-a-dataset"})
    assert_problem(resp, 400)
    assert "not-a-dataset" in resp.json()["title"], resp.text


def test__dataset_import__ValidBody__ReachesTheHandler(api):
    """A real dataset name must get past the request-shape guard. Sending a
    deliberately unreachable URL keeps the test hermetic: the import starts, the
    worker fails on its own, and what's proven here is that the *body arrived*
    (the failure text names the URL, not an empty dataset)."""
    resp = requests.post(IMPORT, json={
        "source": "usda_sr_legacy",
        "url": "http://127.0.0.1:9/never-served.zip",
    })
    assert resp.status_code == 200, resp.text
    sr_legacy = next(
        s for s in resp.json()["sources"] if s["id"] == "usda_sr_legacy"
    )
    assert sr_legacy["phase"] in {"downloading", "parsing", "error"}


def test__resolve_food__AlreadyLocal__ReturnsTheStoredRow(api):
    """Proves the request body actually reaches this endpoint.

    Same defect class as the import button: `resolve` read its body via
    `get_request_body()` without registering a schema, so every request became
    "source and source_ref are required" and **no live suggestion could ever be
    linked to a stock item**. Resolving an already-local row keeps it hermetic —
    the branch returns before any network call.
    """
    _seed_foods()
    with app.app_context():
        repo = SqlAlchemyRepository()
        food = next(
            f for f in repo.get(NutritionFood).all() if f.name == "Bananas, raw"
        )
        source, source_ref, food_id = food.source, food.source_ref, str(food.id)

    resp = requests.post(f"{BASE}/nutrition/foods/resolve", json={
        "source": source, "source_ref": source_ref,
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == food_id


def test__resolve_food__MissingFields__RejectedByTheSchema(api):
    assert_problem(requests.post(f"{BASE}/nutrition/foods/resolve", json={}), 400)


def test__resolve_food__SourceRefLongerThanTheColumn__RejectedByTheSchema(api):
    # `NutritionFood.source_ref` is String(64); the request used to allow 100,
    # which Postgres refuses on insert (500) instead of a 400 here.
    resp = requests.post(f"{BASE}/nutrition/foods/resolve", json={
        "source": "off", "source_ref": "9" * 65,
    })
    assert_problem(resp, 400, field="source_ref")


#endregion

#region ---------------- sources ----------------


def test__sources__ReportsBothDatasetsWithTheirDefaultUrls(api):
    body = requests.get(SOURCES).json()

    datasets = {s["id"]: s for s in body["sources"] if s["kind"] == "dataset"}
    assert set(datasets) == {"usda_foundation", "usda_sr_legacy"}
    for dataset in datasets.values():
        assert dataset["default_url"].startswith("https://")
        assert dataset["phase"] in {"idle", "downloading", "parsing", "saving", "done", "error"}
    # OFF is a source too, and needs no key — just permission.
    assert any(s["id"] == "off" and s["kind"] == "web" for s in body["sources"])


def test__sources__DatasetAvailability__TracksRowsNotAFlag(api):
    _seed_foods()
    body = requests.get(SOURCES).json()

    sr_legacy = next(s for s in body["sources"] if s["id"] == "usda_sr_legacy")
    assert sr_legacy["available"] is True
    assert sr_legacy["food_count"] >= 3


#endregion

#region ---------------- lookup ----------------


def test__lookup__ShortQuery__ReturnsNothingWithoutAskingAnySource(api):
    _seed_foods()   # also takes the live sources offline
    body = requests.get(f"{LOOKUP}?q=b").json()

    assert body["results"] == []
    assert body["sources_queried"] == []


def test__lookup__NameSubstring__MatchesLocalCatalogue(api):
    _seed_foods()
    body = requests.get(f"{LOOKUP}?q=banana").json()

    names = [r["name"] for r in body["results"]]
    assert "Bananas, raw" in names
    assert "Bananas, dehydrated, or banana powder" in names


def test__lookup__EveryResultCarriesSourceAndLabel(api):
    _seed_foods()
    body = requests.get(f"{LOOKUP}?q=banana").json()

    for result in body["results"]:
        assert result["source"]
        assert result["source_label"]


def test__lookup__PrefixMatch__RanksAboveLongerQualifiedName(api):
    _seed_foods()
    body = requests.get(f"{LOOKUP}?q=banana").json()

    local = [r for r in body["results"] if r["id"]]
    assert local[0]["name"] == "Bananas, raw"


def test__lookup__Portions__AreBatchLoadedOntoResults(api):
    ids = _seed_foods()
    body = requests.get(f"{LOOKUP}?q=banana").json()

    banana = next(r for r in body["results"] if r["id"] == ids["banana"])
    assert banana["portions"] == [
        {"amount": 1.0, "measure": "medium", "gram_weight": 118.0},
    ]


def test__lookup__TypedBarcode__MatchesLocallyAndIsFlaggedExact(api):
    ids = _seed_foods()
    body = requests.get(f"{LOOKUP}?q=9300675024235").json()

    assert body["is_barcode"] is True
    top = body["results"][0]
    assert top["id"] == ids["beans"]
    assert top["match"] == "barcode"
    assert top["exact"] is True


def test__lookup__DigitsThatArentAnEanLength__AreTreatedAsText(api):
    _seed_foods()   # also takes the live sources offline
    body = requests.get(f"{LOOKUP}?q=500").json()

    # "500" is someone searching for a 500g thing, not scanning a barcode.
    assert body["is_barcode"] is False


#endregion

#region ---------------- stock-item link round-trip ----------------


def _make_stock_item(name: str) -> str:
    # `/stock-levels` is enveloped under `items`, like the other list reads.
    levels = requests.get(f"{BASE}/stock-levels").json()["items"]
    created = make_stock_item(stock_level_id=levels[0]["stock_level_id"], name=name)
    return created["stock_item_id"]


def test__stock_item__LinkFood__RoundTripsOntoTheDetail(api):
    ids = _seed_foods()
    item_id = _make_stock_item(f"Bananas {uuid4().hex[:6]}")

    patch = requests.patch(f"{BASE}/stock-items/{item_id}", json={
        "nutrition_food_id": ids["banana"],
    })
    assert patch.status_code in (200, 204), patch.text

    detail = requests.get(f"{BASE}/stock-items/{item_id}/detail").json()
    assert detail["nutrition_food"]["nutrition_food_id"] == ids["banana"]
    assert detail["nutrition_food"]["name"] == "Bananas, raw"
    # The source travels with it so the detail page can say where the numbers
    # came from, same as the picker does.
    assert detail["nutrition_food"]["source_label"] == "USDA SR Legacy"
    assert detail["nutrition_food"]["kcal_per_100g"] == 89.0


def test__stock_item__ClearFlag__UnlinksTheFood(api):
    ids = _seed_foods()
    item_id = _make_stock_item(f"Bananas {uuid4().hex[:6]}")
    requests.patch(f"{BASE}/stock-items/{item_id}", json={
        "nutrition_food_id": ids["banana"],
    })

    resp = requests.patch(f"{BASE}/stock-items/{item_id}", json={
        "clear_nutrition_food": True,
    })
    assert resp.status_code in (200, 204), resp.text

    detail = requests.get(f"{BASE}/stock-items/{item_id}/detail").json()
    assert detail["nutrition_food"] is None


def test__stock_item__UnlinkedItem__ReportsNullNotAnEmptyObject(api):
    item_id = _make_stock_item(f"Plain {uuid4().hex[:6]}")

    detail = requests.get(f"{BASE}/stock-items/{item_id}/detail").json()
    # Null is the honest default — a link only exists because someone
    # confirmed one, so there's nothing to imply otherwise.
    assert detail["nutrition_food"] is None


def test__stock_item__UnrelatedPatch__LeavesTheLinkAlone(api):
    ids = _seed_foods()
    item_id = _make_stock_item(f"Bananas {uuid4().hex[:6]}")
    requests.patch(f"{BASE}/stock-items/{item_id}", json={
        "nutrition_food_id": ids["banana"],
    })

    requests.patch(f"{BASE}/stock-items/{item_id}", json={"is_essential": True})

    detail = requests.get(f"{BASE}/stock-items/{item_id}/detail").json()
    assert detail["nutrition_food"]["nutrition_food_id"] == ids["banana"]


#endregion


#region ---------------- dataset persistence (FU-639) ----------------


def test__replace_dataset__PortionsSurviveTheRepositoryIdReassignment(api):
    """The import wrote 14,449 portions pointing at ids that never existed.

    `repository.add()` assigns a **fresh** id to every entity it stores, so the
    `NutritionFood.id` values the parser generated were discarded on the way in
    — while the portions it had already built still referenced them. Result: a
    foreign-key violation on the first flush, and a download button that
    downloaded, parsed, and then threw the whole dataset away. Nothing caught it
    because the parser tests never touch a database and the seeded e2e fixtures
    read `food.id` *after* adding.

    This drives the real persistence path and asserts the link survives.
    """
    from dora_api.features.nutrition.dataset_import import (
        ParsedPortion, _replace_dataset,
    )

    source = NUTRITION_SOURCE_USDA_SR_LEGACY
    ref_a, ref_b = f"fk-{uuid4().hex[:8]}", f"fk-{uuid4().hex[:8]}"
    foods = [
        NutritionFood(id=uuid4(), source=source, source_ref=ref_a,
                      name="FK Probe Flour", kcal_per_100g=364.0),
        NutritionFood(id=uuid4(), source=source, source_ref=ref_b,
                      name="FK Probe Banana", kcal_per_100g=89.0),
    ]
    portions = [
        ParsedPortion(fdc_id=ref_a, amount=1, measure="cup", gram_weight=125.0),
        ParsedPortion(fdc_id=ref_b, amount=1, measure="medium", gram_weight=118.0),
    ]

    with app.app_context():
        _replace_dataset(SqlAlchemyRepository(), source, foods, portions)

        repo = SqlAlchemyRepository()
        stored = {f.source_ref: f for f in repo.get(NutritionFood).all()}
        assert ref_a in stored and ref_b in stored
        stored_ids = {f.id for f in stored.values()}
        rows = repo.get(NutritionPortion).all()
        # Every portion resolves to a food that is actually in the table.
        assert rows, "no portions were stored at all"
        assert all(p.nutrition_food_id in stored_ids for p in rows)
        # And each one landed against its own food, not just *a* food.
        by_food = {p.nutrition_food_id: p.measure for p in rows}
        assert by_food[stored[ref_a].id] == "cup"
        assert by_food[stored[ref_b].id] == "medium"


#endregion
