"""FU-193 — backend behavioural coverage for the Onboarding C-5.3/.4/.5 surfaces.

Covers products data-presence gating (FU-209), the install-wide household
cooking config (FU-615 — headcount + batch cook-style, moved off User onto
AppSetting), and the starter catalogue + name-resolved item seeding.
Migrations themselves are verified separately (single head + well-formed batch
DDL); these tests assert the runtime round-trips that the wizard relies on.
"""
import uuid

import requests

from tests.e2e.dora_api._onboarding_finish import finish_demo, finish_items

BASE = "http://localhost:5170/api"
HEALTH = f"{BASE}/health"
APP_SETTINGS = f"{BASE}/app-settings"
ME = f"{BASE}/auth/me"
CATALOG = f"{BASE}/onboarding/catalog"
STOCK_ITEMS = f"{BASE}/stock-items"
RECIPES = f"{BASE}/recipes"
MEAL_PLANS = f"{BASE}/meal-plans"


# ── products data-presence gate (FU-209) ────────────────────────────


def test__health__products_flag_reflects_data_presence(api):
    # Products is a data-presence overlay (PROPOSAL_PRODUCTS_AS_OVERLAY): the
    # flag is true iff product rows exist — there is no admin/user toggle.
    flags = requests.get(HEALTH).json()["features"]
    body = requests.get(f"{BASE}/products").json()
    items = body["items"] if isinstance(body, dict) and "items" in body else body
    assert flags["products"] is (len(items) > 0)


def test__app_settings__no_longer_carries_products_enabled(api):
    # GET must not expose it, and PATCHing it is
    # rejected by the request model (extra="forbid").
    assert "products_enabled" not in requests.get(APP_SETTINGS).json()
    rejected = requests.patch(APP_SETTINGS, json={"products_enabled": True})
    assert 400 <= rejected.status_code < 500


# ── FU-615 install-wide household cooking config (headcount + cook-style) ──


def test__app_settings__household_headcount_roundtrips(api):
    # Moved off /auth/me to the install-wide AppSetting; the admin dev user
    # can PATCH it and it mirrors onto /api/health.cooking_policy for every
    # client (cook mode reads it there).
    original = requests.get(APP_SETTINGS).json().get("household_headcount")
    try:
        assert requests.patch(APP_SETTINGS, json={"household_headcount": 4}).status_code == 200
        assert requests.get(APP_SETTINGS).json()["household_headcount"] == 4
        assert requests.get(HEALTH).json()["cooking_policy"]["household_headcount"] == 4
        # null clears it back to "not set" (cook mode then falls back to servings).
        assert requests.patch(APP_SETTINGS, json={"household_headcount": None}).status_code == 200
        assert requests.get(APP_SETTINGS).json()["household_headcount"] is None
        assert requests.get(HEALTH).json()["cooking_policy"]["household_headcount"] is None
    finally:
        requests.patch(APP_SETTINGS, json={"household_headcount": original})


def test__app_settings__household_headcount_out_of_range_rejected(api):
    assert requests.patch(APP_SETTINGS, json={"household_headcount": 0}).status_code == 400
    assert requests.patch(APP_SETTINGS, json={"household_headcount": 100}).status_code == 400


def test__app_settings__batch_features_enabled_roundtrips(api):
    original = requests.get(APP_SETTINGS).json().get("batch_features_enabled")
    try:
        assert requests.patch(APP_SETTINGS, json={"batch_features_enabled": True}).status_code == 200
        assert requests.get(APP_SETTINGS).json()["batch_features_enabled"] is True
        assert requests.get(HEALTH).json()["cooking_policy"]["batch_features_enabled"] is True
        assert requests.patch(APP_SETTINGS, json={"batch_features_enabled": False}).status_code == 200
        assert requests.get(HEALTH).json()["cooking_policy"]["batch_features_enabled"] is False
    finally:
        requests.patch(APP_SETTINGS, json={"batch_features_enabled": bool(original)})


def test__users_me__no_longer_carries_cooking_config(api):
    # FU-615 — the two prefs left /auth/me entirely; GET must not expose them
    # and PATCHing them is rejected by the request model (extra="forbid").
    me = requests.get(ME).json()
    assert "household_headcount" not in me
    assert "batch_features_enabled" not in me
    assert requests.patch(ME, json={"household_headcount": 4}).status_code == 400
    assert requests.patch(ME, json={"batch_features_enabled": True}).status_code == 400


# ── C-5.5 starter catalogue + name-resolved seeding ──────────────────


def test__onboarding_catalog__serialises_groups_locations_packs(api):
    body = requests.get(CATALOG).json()
    assert isinstance(body["groups"], list) and body["groups"]
    assert isinstance(body["locations"], list) and body["locations"]
    # Nested location nodes carry name/kind/children.
    first_zone = body["locations"][0]
    assert {"name", "kind", "children"} <= set(first_zone.keys())
    # 5 starter packs ship in starter_packs.json.
    assert len(body["packs"]) == 5
    pack = body["packs"][0]
    assert {"key", "label", "blurb", "items"} <= set(pack.keys())


def test__onboarding_seed_items__creates_prelocated_and_dedupes(api):
    groups = requests.get(f"{BASE}/stock-groups").json()
    locations = requests.get(f"{BASE}/locations").json()
    assert groups and locations, "seed DB has groups + locations to resolve against"
    group_name = groups[0]["name"]
    location_name = locations[0]["name"]

    unique_name = f"FU193SeedItem-{uuid.uuid4().hex[:8]}"
    payload = {
        "items": [
            {
                "name": unique_name,
                "group_name": group_name,
                "location_name": location_name,
            }
        ]
    }

    first = finish_items(payload)
    assert first.status_code == 200
    assert first.json() == {"created": 1, "skipped": 0}

    # The item is created pre-located: group + location resolved by name.
    created = requests.get(f"{STOCK_ITEMS}?filter=name:eq:{unique_name}").json()["items"]
    assert len(created) == 1
    item = created[0]
    assert item["stock_group_id"] == groups[0]["stock_group_id"]
    assert item["stock_location_id"] == locations[0]["location_id"]

    # Re-running Finish must not duplicate: same name is skipped.
    second = finish_items(payload)
    assert second.status_code == 200
    assert second.json() == {"created": 0, "skipped": 1}
    still_one = requests.get(f"{STOCK_ITEMS}?filter=name:eq:{unique_name}").json()["items"]
    assert len(still_one) == 1


# ── FU-194 demo dataset toggle ───────────────────────────────────────


def test__onboarding_seed_demo__is_idempotent(api):
    # The dev seed already ships an "Spaghetti Aglio e Olio" recipe, so the
    # first call here lands as a no-op (`seeded: false`) AND a second call
    # behaves identically — that's the contract: never duplicate.
    first = finish_demo()
    assert first.status_code == 200
    body_one = first.json()
    assert set(body_one.keys()) == {
        "seeded", "items_created", "recipe_created", "meal_plan_created",
    }
    # On a freshly-seeded DB the recipe already exists, so seeded=False;
    # on a clean DB (no seed) it'd be seeded=True with recipe_created=True.
    # Whichever branch we landed in, a second call must match exactly.
    second = finish_demo()
    assert second.status_code == 200
    assert second.json() == body_one
    # Either way, exactly one recipe by that name exists afterward.
    recipes = requests.get(RECIPES).json().get("items", [])
    matches = [r for r in recipes if r.get("name") == "Spaghetti Aglio e Olio"]
    assert len(matches) == 1
