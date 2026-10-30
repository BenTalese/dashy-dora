"""FU-519 tail — e2e for the hierarchical locations tree router.

POST/GET /api/locations + PATCH/DELETE /api/locations/<id> — the tree CRUD
surface behind Home Zones / Zone Detail / the destination picker. Pins:

  - zone → area → section nesting + the node DTO shape,
  - the kind ladder on create (zone has no parent, area under zone,
    section under area — nothing else),
  - rename / re-sequence / reparent via PATCH, incl. the cycle guard,
  - delete semantics: subtree cascade + stock items left unassigned,
  - direct vs descendant item-count rollups,
  - 4xx (never 5xx) for malformed / unknown ids.

The flat name-only `/api/stock-locations` create is a different surface
(covered by its own taxonomy suite); only the tree API accepts `parent_id`.
"""
from uuid import uuid4

import requests

from tests.factories import make_stock_item
from tests.support import assert_problem

BASE = "http://localhost:5170/api"
LOCATIONS = f"{BASE}/locations"

NODE_KEYS = {
    "location_id", "name", "kind", "parent_id", "sequence",
    "direct_item_count", "descendant_item_count", "items", "children",
}
ITEM_KEYS = {"stock_item_id", "name", "stock_level_name", "expiry_date", "is_essential"}


def _token() -> str:
    return f"zq{uuid4().hex[:8]}"


def _make(name: str, kind: str, parent_id: str | None = None, sequence: int = 0) -> str:
    body: dict = {"name": name, "kind": kind, "sequence": sequence}
    if parent_id is not None:
        body["parent_id"] = parent_id
    resp = requests.post(LOCATIONS, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()["location_id"]


def _tree() -> list[dict]:
    resp = requests.get(LOCATIONS)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)
    return body


def _find(nodes: list[dict], location_id: str) -> dict | None:
    """Depth-first search of the whole tree for a node by id."""
    for node in nodes:
        if node["location_id"] == location_id:
            return node
        hit = _find(node["children"], location_id)
        if hit is not None:
            return hit
    return None


def _stock_level_id() -> str:
    return requests.get(f"{BASE}/stock-levels").json()["items"][0]["stock_level_id"]


#region ---------------- create + tree shape ----------------


def test__create_location__ZoneAreaSectionChain__NestedInTree(api):
    token = _token()
    zone_id = _make(f"Garage {token}", "zone")
    area_id = _make(f"Chest freezer {token}", "area", zone_id)
    section_id = _make(f"Top drawer {token}", "section", area_id)

    tree = _tree()

    zone = _find(tree, zone_id)
    assert zone is not None, "new zone missing from tree roots"
    assert zone["kind"] == "zone"
    assert zone["parent_id"] is None
    # The zone must be a root, not nested under anything.
    assert any(n["location_id"] == zone_id for n in tree)

    area = _find(zone["children"], area_id)
    assert area is not None, "area not nested under its zone"
    assert area["kind"] == "area"
    assert area["parent_id"] == zone_id

    section = _find(area["children"], section_id)
    assert section is not None, "section not nested under its area"
    assert section["kind"] == "section"
    assert section["parent_id"] == area_id
    assert section["children"] == []


def test__get_location_tree__NodeAndItemShape__MatchesContract(api):
    token = _token()
    zone_id = _make(f"Pantry {token}", "zone")
    item = make_stock_item(
        stock_level_id=_stock_level_id(),
        name=f"{token} beans",
        stock_location_id=zone_id,
    )

    zone = _find(_tree(), zone_id)

    assert set(zone.keys()) == NODE_KEYS
    assert zone["direct_item_count"] == 1
    assert zone["descendant_item_count"] == 1
    entry = next(
        i for i in zone["items"] if i["stock_item_id"] == item["stock_item_id"]
    )
    assert set(entry.keys()) == ITEM_KEYS
    assert entry["name"] == f"{token} beans"
    assert entry["is_essential"] is False
    assert entry["expiry_date"] is None


def test__create_location__InvalidKind__400(api):
    resp = requests.post(LOCATIONS, json={"name": "Attic", "kind": "wing"})
    assert_problem(resp, 400, title="Invalid location kind 'wing'.")


def test__create_location__ZoneWithParent__422(api):
    token = _token()
    zone_id = _make(f"Shed {token}", "zone")
    resp = requests.post(
        LOCATIONS, json={"name": f"Loft {token}", "kind": "zone", "parent_id": zone_id},
    )
    assert_problem(resp, 422, title="Business rule violation.")


def test__create_location__AreaWithoutParent__422(api):
    resp = requests.post(LOCATIONS, json={"name": f"Shelf {_token()}", "kind": "area"})
    assert_problem(resp, 422, title="Business rule violation.")


def test__create_location__SectionUnderZone__422(api):
    # Kind ladder is strict — a section can't skip the area level.
    token = _token()
    zone_id = _make(f"Cellar {token}", "zone")

    resp = requests.post(LOCATIONS, json={
        "name": f"Bin {token}", "kind": "section", "parent_id": zone_id,
    })

    body = assert_problem(resp, 422, title="Business rule violation.")
    # NOTE — pinned copy bug: the message names the *valid* parent kind,
    # so it reads "A section cannot live under a area parent." even though
    # area is exactly where a section belongs. Functional behaviour (422)
    # is correct; the copy is misleading. Reported as a finding.
    assert "section" in resp.text


def test__create_location__SectionUnderSection__422(api):
    token = _token()
    zone_id = _make(f"Kitchen {token}", "zone")
    area_id = _make(f"Fridge {token}", "area", zone_id)
    section_id = _make(f"Crisper {token}", "section", area_id)

    resp = requests.post(LOCATIONS, json={
        "name": f"Sub-crisper {token}", "kind": "section", "parent_id": section_id,
    })

    assert_problem(resp, 422, title="Business rule violation.")


def test__create_location__UnknownParent__422NotFoundMessage(api):
    resp = requests.post(LOCATIONS, json={
        "name": f"Orphan {_token()}", "kind": "area", "parent_id": str(uuid4()),
    })
    body = assert_problem(resp, 422, title="Business rule violation.")
    assert "Parent location was not found." in resp.text


def test__create_location__MalformedParentId__400(api):
    resp = requests.post(LOCATIONS, json={
        "name": "Bad parent", "kind": "area", "parent_id": "not-a-uuid",
    })
    assert_problem(resp, 400, field="parent_id")


def test__create_location__EmptyName__400(api):
    resp = requests.post(LOCATIONS, json={"name": "", "kind": "zone"})
    assert_problem(resp, 400, field="name")


#endregion create + tree shape

#region ---------------- update: rename / resequence / move ----------------


def test__update_location__Rename__ReflectedInTree(api):
    token = _token()
    zone_id = _make(f"Bar {token}", "zone")

    resp = requests.patch(f"{LOCATIONS}/{zone_id}", json={"name": f"Wine bar {token}"})

    assert resp.status_code == 204, resp.text
    assert _find(_tree(), zone_id)["name"] == f"Wine bar {token}"


def test__update_location__SequenceReorder__SiblingsSortedBySequenceThenName(api):
    token = _token()
    zone_id = _make(f"Store room {token}", "zone")
    # Same sequence → alphabetical; then bump one to the front.
    a_id = _make(f"Alpha {token}", "area", zone_id, sequence=5)
    b_id = _make(f"Bravo {token}", "area", zone_id, sequence=5)

    order = [c["location_id"] for c in _find(_tree(), zone_id)["children"]]
    assert order == [a_id, b_id]

    resp = requests.patch(f"{LOCATIONS}/{b_id}", json={"sequence": 1})
    assert resp.status_code == 204, resp.text

    order = [c["location_id"] for c in _find(_tree(), zone_id)["children"]]
    assert order == [b_id, a_id]


def test__update_location__MoveAreaToAnotherZone__Reparents(api):
    token = _token()
    zone1_id = _make(f"House {token}", "zone")
    zone2_id = _make(f"Garage {token}", "zone")
    area_id = _make(f"Shelving {token}", "area", zone1_id)

    resp = requests.patch(f"{LOCATIONS}/{area_id}", json={"parent_id": zone2_id})

    assert resp.status_code == 204, resp.text
    tree = _tree()
    assert _find(_find(tree, zone1_id)["children"], area_id) is None
    moved = _find(_find(tree, zone2_id)["children"], area_id)
    assert moved is not None
    assert moved["parent_id"] == zone2_id


def test__update_location__MoveUnderOwnDescendant__422(api):
    token = _token()
    zone_id = _make(f"Attic {token}", "zone")
    area_id = _make(f"Boxes {token}", "area", zone_id)

    resp = requests.patch(f"{LOCATIONS}/{zone_id}", json={"parent_id": area_id})

    body = assert_problem(resp, 422, title="Business rule violation.")
    # FU-532 fixed the dead cycle branch: `location_id` now arrives from the
    # Flask route as a real `uuid.UUID` (via the `<uuid:location_id>`
    # converter), so the cycle walk's `cursor.id == location_id` comparison in
    # update_location.py finally matches. A move under an own descendant is now
    # refused by the *dedicated cycle* message (which is checked before the kind
    # ladder), not the kind-mismatch fallback it used to fall through to.
    assert "underneath itself or one of its descendants" in resp.text


def test__update_location__MoveZoneUnderUnrelatedArea__422KindMismatch(api):
    # A zone can never gain a parent — even a non-cyclic one.
    token = _token()
    zone1_id = _make(f"Home {token}", "zone")
    zone2_id = _make(f"Shed {token}", "zone")
    area2_id = _make(f"Wall racks {token}", "area", zone2_id)

    resp = requests.patch(f"{LOCATIONS}/{zone1_id}", json={"parent_id": area2_id})

    assert_problem(resp, 422, title="Business rule violation.")


def test__update_location__MoveSectionUnderZone__422KindMismatch(api):
    token = _token()
    zone_id = _make(f"Kitchen {token}", "zone")
    area_id = _make(f"Pantry {token}", "area", zone_id)
    section_id = _make(f"Spice rack {token}", "section", area_id)

    resp = requests.patch(f"{LOCATIONS}/{section_id}", json={"parent_id": zone_id})

    assert_problem(resp, 422, title="Business rule violation.")


def test__update_location__ExplicitNullParent__AreaCannotDetachToRoot(api):
    # PATCH {"parent_id": null} used to skip the kind ladder (the check only
    # ran for a non-null parent), leaving an "area" root no create path
    # allows. Only a zone may be a root.
    token = _token()
    zone_id = _make(f"Laundry {token}", "zone")
    area_id = _make(f"Cupboard {token}", "area", zone_id)

    resp = requests.patch(f"{LOCATIONS}/{area_id}", json={"parent_id": None})

    assert_problem(resp, 422, title="Business rule violation.")
    assert _find(_tree(), area_id)["parent_id"] == zone_id


def test__update_location__UnknownId__404(api):
    missing = uuid4()
    assert_problem(
        requests.patch(f"{LOCATIONS}/{missing}", json={"name": "Ghost"}),
        404, detail=f"StockLocation with the ID '{missing}' was not found.",
    )
    assert_problem(
        requests.delete(f"{LOCATIONS}/{missing}"),
        404, detail=f"StockLocation with the ID '{missing}' was not found.",
    )


#endregion update

#region ---------------- delete ----------------


def test__delete_location__LeafWithItems__ItemsLeftUnassigned(api):
    token = _token()
    zone_id = _make(f"Camping tub {token}", "zone")
    item = make_stock_item(
        stock_level_id=_stock_level_id(),
        name=f"{token} gas canister",
        stock_location_id=zone_id,
    )

    resp = requests.delete(f"{LOCATIONS}/{zone_id}")

    assert resp.status_code == 204, resp.text
    assert _find(_tree(), zone_id) is None
    # The item survives, just unassigned.
    detail = requests.get(f"{BASE}/stock-items/{item['stock_item_id']}/detail")
    assert detail.status_code == 200, detail.text
    assert detail.json()["stock_location_id"] is None


def test__delete_location__ZoneWithDescendants__WholeSubtreeRemoved(api):
    token = _token()
    zone_id = _make(f"Garage {token}", "zone")
    area_id = _make(f"Freezer {token}", "area", zone_id)
    section_id = _make(f"Bottom drawer {token}", "section", area_id)
    item = make_stock_item(
        stock_level_id=_stock_level_id(),
        name=f"{token} peas",
        stock_location_id=section_id,
    )

    resp = requests.delete(f"{LOCATIONS}/{zone_id}")

    assert resp.status_code == 204, resp.text
    tree = _tree()
    assert _find(tree, zone_id) is None
    assert _find(tree, area_id) is None
    assert _find(tree, section_id) is None
    # Descendants are really deleted (FK ON DELETE CASCADE), not orphaned:
    # a PATCH against the former section 404s.
    assert requests.patch(
        f"{LOCATIONS}/{section_id}", json={"name": "Ghost"},
    ).status_code == 404
    # The item deep in the subtree is unassigned, not deleted.
    detail = requests.get(f"{BASE}/stock-items/{item['stock_item_id']}/detail")
    assert detail.status_code == 200, detail.text
    assert detail.json()["stock_location_id"] is None


#endregion delete

#region ---------------- item-count rollups ----------------


def test__get_location_tree__ItemCounts__DescendantsRollUpToAncestors(api):
    token = _token()
    level = _stock_level_id()
    zone_id = _make(f"Kitchen {token}", "zone")
    area_id = _make(f"Fridge {token}", "area", zone_id)
    make_stock_item(stock_level_id=level, name=f"{token} zone item",
                    stock_location_id=zone_id)
    make_stock_item(stock_level_id=level, name=f"{token} area item 1",
                    stock_location_id=area_id)
    make_stock_item(stock_level_id=level, name=f"{token} area item 2",
                    stock_location_id=area_id)

    zone = _find(_tree(), zone_id)

    assert zone["direct_item_count"] == 1
    assert zone["descendant_item_count"] == 3
    area = _find(zone["children"], area_id)
    assert area["direct_item_count"] == 2
    assert area["descendant_item_count"] == 2


#endregion item-count rollups
