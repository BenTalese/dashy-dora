"""FU-519 item 4 / PROPOSAL_TEST_SUITE_IMPROVEMENTS §5.D [P2] — DTO
contract snapshots.

One parametrized test per read endpoint that pins the **response key
shape** (envelope keys + first-item keys for list endpoints, top-level
keys for object endpoints). Catches silent DTO drift — the failure mode
FU-166 spent days realigning — at the moment a field is added, renamed,
or dropped.

Snapshots live in ``dto_snapshots.json`` next to this file. When a shape
change is *intentional*, refresh them::

    DORA_UPDATE_DTO_SNAPSHOTS=1 .venv/Scripts/python.exe -m pytest \
        tests/e2e/dora_api/test_dto_contracts.py --no-cov -q

then commit the JSON diff — the diff *is* the reviewable contract change.
Additive field growth still fails here by design: a new field is a
contract change the snapshot should record, and refreshing is one command.
"""
import json
import os
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
import requests

from tests.factories import make_product, make_stock_item

BASE = "http://localhost:5170/api"
_SNAPSHOT_PATH = Path(__file__).with_name("dto_snapshots.json")
_UPDATE = os.environ.get("DORA_UPDATE_DTO_SNAPSHOTS") == "1"

_ENVELOPE_KEYS = {"items", "total", "page", "limit"}


#region ---------------- seed helpers ----------------


def _any_stock_level_id() -> str:
    return requests.get(f"{BASE}/stock-levels").json()["items"][0]["stock_level_id"]


def _seed_stock_item() -> None:
    make_stock_item(stock_level_id=_any_stock_level_id(),
                    name=f"contract item {uuid4().hex[:8]}")


def _seed_expired_stock_item() -> None:
    """An expired item guarantees at least one alert row."""
    make_stock_item(stock_level_id=_any_stock_level_id(),
                    name=f"contract expired {uuid4().hex[:8]}",
                    expiry_date="2020-01-01")


def _seed_product() -> None:
    make_product(name=f"contract product {uuid4().hex[:8]}")


def _seed_recipe() -> None:
    resp = requests.post(f"{BASE}/recipes",
                         json={"name": f"contract recipe {uuid4().hex[:8]}"})
    assert resp.status_code == 201, resp.text


def _seed_shopping_list() -> None:
    resp = requests.post(f"{BASE}/shopping-lists",
                         json={"name": f"contract list {uuid4().hex[:8]}"})
    assert resp.status_code == 201, resp.text


def _seed_meal_plan() -> None:
    today = requests.get(f"{BASE}/meal-plans/today").json()["today"]
    resp = requests.post(f"{BASE}/meal-plans", json={
        "name": f"contract plan {uuid4().hex[:8]}",
        "start_date": today,
    })
    assert resp.status_code == 201, resp.text


def _seed_meal_plan_template() -> None:
    # Saving a template requires a source week that actually has meals.
    recipe = requests.post(f"{BASE}/recipes",
                           json={"name": f"contract tpl recipe {uuid4().hex[:8]}"})
    assert recipe.status_code == 201, recipe.text
    today = date.fromisoformat(
        requests.get(f"{BASE}/meal-plans/today").json()["today"]
    )
    plan = requests.post(f"{BASE}/meal-plans", json={
        "name": f"contract tpl plan {uuid4().hex[:8]}",
        "start_date": today.isoformat(),
        "entries": [{
            "recipe_id": recipe.json()["recipe_id"],
            "scheduled_for": today.isoformat(),
            "servings": 2,
            "slot": "Dinner",
        }],
    })
    assert plan.status_code == 201, plan.text
    resp = requests.post(f"{BASE}/meal-plan-templates", json={
        "name": f"contract template {uuid4().hex[:8]}",
        "source_meal_plan_id": plan.json()["meal_plan_id"],
    })
    assert resp.status_code == 201, resp.text

#endregion seed helpers


# (case_id, path, query params, seed callable or None). Every list
# endpoint here must end up non-empty (seeded app data or a seed
# callable) so the snapshot always captures real item keys.
CASES = [
    ("stock_items",        "/stock-items",        {},            _seed_stock_item),
    ("stock_levels",       "/stock-levels",       {},            None),
    ("stock_groups",       "/stock-groups",       {},            None),
    ("stores",             "/stores",             {},            None),
    ("products",           "/products",           {},            _seed_product),
    ("recipes",            "/recipes",            {},            _seed_recipe),
    ("recipe_collections", "/recipe-collections", {},            None),
    ("cuisines",           "/cuisines",           {},            None),
    ("categories",         "/categories",         {},            None),
    ("dietary_tags",       "/dietary-tags",       {},            None),
    ("tools",              "/tools",              {},            None),
    ("meal_slots",         "/meal-slots",         {},            None),
    ("meal_plans",         "/meal-plans",         {},            _seed_meal_plan),
    ("meal_plan_templates", "/meal-plan-templates", {},          _seed_meal_plan_template),
    ("shopping_lists",     "/shopping-lists",     {},            _seed_shopping_list),
    ("users",              "/users",              {},            None),
    ("alerts",             "/alerts",             {},            _seed_expired_stock_item),
    ("app_settings",       "/app-settings",       {},            None),
    ("auth_me",            "/auth/me",            {},            None),
    ("dashboard_summary",  "/dashboard/summary",  {},            _seed_stock_item),
    ("dashboard_dora_score", "/dashboard/dora-score", {},        None),
    ("search",             "/search",             {"q": "dora"}, None),
    ("health",             "/health",             {},            None),
    ("onboarding_state",   "/onboarding/state",   {},            None),
    ("suggestions",        "/suggestions",        {},            None),
    ("waste_rescue",       "/waste/rescue",       {},            None),
]


def _signature(body) -> dict:
    """Reduce a response body to its comparable key shape."""
    if isinstance(body, dict) and _ENVELOPE_KEYS <= set(body.keys()):
        items = body["items"]
        assert items, (
            "list endpoint returned no items — add/extend its seed "
            "callable so the snapshot captures real item keys"
        )
        return {
            "envelope": sorted(body.keys()),
            "item_keys": sorted(items[0].keys()),
        }
    if isinstance(body, dict):
        return {"keys": sorted(body.keys())}
    if isinstance(body, list):
        assert body, "bare-list endpoint returned no rows — seed it"
        return {"list_item_keys": sorted(body[0].keys())}
    pytest.fail(f"unsnapshottable body type: {type(body)!r}")


def _load_snapshots() -> dict:
    if _SNAPSHOT_PATH.exists():
        return json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    return {}


def _store_snapshot(case_id: str, sig: dict) -> None:
    snaps = _load_snapshots()
    snaps[case_id] = sig
    _SNAPSHOT_PATH.write_text(
        json.dumps(snaps, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )


@pytest.mark.parametrize(
    "case_id,path,params,seed",
    CASES,
    ids=[c[0] for c in CASES],
)
def test__dto_contract__ResponseKeys__MatchSnapshot(api, case_id, path, params, seed):
    if seed is not None:
        seed()

    resp = requests.get(f"{BASE}{path}", params=params)
    assert resp.status_code == 200, f"{path}: {resp.status_code} {resp.text[:200]}"
    sig = _signature(resp.json())

    if _UPDATE:
        _store_snapshot(case_id, sig)
        return

    snaps = _load_snapshots()
    assert case_id in snaps, (
        f"no snapshot for '{case_id}' — run with DORA_UPDATE_DTO_SNAPSHOTS=1 "
        "to record it, then commit dto_snapshots.json"
    )
    assert sig == snaps[case_id], (
        f"DTO shape drift on GET {path}. If intentional, refresh: "
        "DORA_UPDATE_DTO_SNAPSHOTS=1 pytest tests/e2e/dora_api/"
        "test_dto_contracts.py and commit the JSON diff."
    )
