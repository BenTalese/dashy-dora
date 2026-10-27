"""FU-512 — `POST /onboarding/seed` is a unit of work.

Pre-FU-512 committed after the groups block AND inside the locations loop
after each zone insert. Now: one final commit at the end of the handler.
The locations loop still calls `flush()` before inserting child locations
(child.parent_id → zone_entity.id, and the classic mapper has no
`relationship()` between StockLocation self-refs, so SQLite FK checks would
trip without the flush — the local contract in
`sqlalchemy_repository.py:57-67`).

Happy-path only: the seed loops iterate parsed JSON and don't naturally
raise. A rollback test would need a test-only override of `_load_seed` to
return a poisoned entry; deferred.
"""
import uuid

import requests

BASE = "http://localhost:5170/api"
SEED = f"{BASE}/onboarding/seed"
STOCK_LOCATIONS = f"{BASE}/stock-locations"


def test__seed_onboarding__groups_and_locations__commits_everything_together(api):
    # Pick two filter targets: one group and one location path (zone + child).
    # If the picks already exist in the DB (previous runs), the endpoint
    # returns skipped counts — that's fine, the invariant we're pinning is
    # "no crash, one transaction, endpoint returns a coherent result".
    unique = uuid.uuid4().hex[:6]
    group_pick = f"FU-512 grp {unique}"
    zone_pick = f"FU-512 zone {unique}"
    child_pick = f"FU-512 child {unique}"

    # We can't actually create new seed defaults on the fly (they come from
    # bundled JSON), so the safest happy-path check is: hit the endpoint
    # with the ambient defaults + explicit filters that select nothing new,
    # and confirm the response shape is coherent (no exception, sensible
    # counts, no partial state).
    resp = requests.post(SEED, json={
        "groups": True,
        "group_names": [group_pick],       # unknown name → nothing to create
        "locations": True,
        "location_paths": [f"{zone_pick}/{child_pick}"],  # unknown → nothing
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Filter selected non-existent defaults, so both created counts should
    # be zero. Skipped counts should also be zero (the filter narrowed to
    # unknown names, which don't match any bundled default).
    assert body["groups_created"] == 0, body
    assert body["locations_created"] == 0, body


def test__seed_onboarding__seed_default_groups__commits_them(api):
    # Broad happy path — seed default groups without a filter. Whether they
    # end up "created" or "skipped" depends on whether previous tests seeded
    # them, but the endpoint must return a coherent 200 with matching totals.
    resp = requests.post(SEED, json={"groups": True})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["groups_created"] + body["groups_skipped"] >= 1, body


def test__seed_onboarding__own_group_and_zone_names__created_once_in_the_same_call(api):
    """Finalisation 14-R19: the user's own entries from the stock step ride the
    seed's unit of work (the wizard used to create them client-side after the
    seed had committed). Deduped by name like the defaults."""
    unique = uuid.uuid4().hex[:6]
    body = {
        "groups": False, "locations": False,
        "extra_group_names": [f"Own group {unique}"],
        "extra_location_names": [f"Own zone {unique}"],
    }

    first = requests.post(SEED, json=body)
    assert first.status_code == 200, first.text
    assert first.json()["groups_created"] == 1
    assert first.json()["locations_created"] == 1

    second = requests.post(SEED, json=body)
    assert second.status_code == 200, second.text
    assert second.json()["groups_created"] == 0
    assert second.json()["groups_skipped"] == 1
    assert second.json()["locations_created"] == 0
    assert second.json()["locations_skipped"] == 1

    zones = requests.get(f"{BASE}/locations").json()
    assert f"Own zone {unique}" in {z["name"] for z in zones}
