"""FU-577 — the auto-add-on-low branching matrix, tested directly against
PATCH /api/stock-items/<id>.

`UpdateStockItemHandler` owns the whole decision (R-003):

  fire iff  _auto_add_enabled_for(item)          # AppSetting.auto_add_mode × is_essential
        and needs_restock(new_level)             # new level is Low or Out
        and not needs_restock(previous_level)    # ...and it's a genuine transition
        and item not on ANY active list          # dedup — "the user already knows"
        and resolve_quick_add_target == "single"   # exactly one DRAFT list

On fire the PATCH returns **200** `{"auto_added": {"line_id", "shopping_list_id"}}`
and the draft gains a line with `is_auto_added=true`; otherwise the
normal **204** and no line anywhere.

The e2e browser spec (`web_app/e2e/auto-add-on-low.spec.ts`) pins only the
`all`-mode happy-path UI seam; this file pins the branch matrix the browser
can't practically drive (DORA_VERIFY L845/848/850/851/852). The
unknown-mode→essential_only degrade in `_auto_add_enabled_for` is unreachable
over HTTP (the app-settings PATCH validates the enum), so it isn't tested here.
"""
from uuid import uuid4

import pytest
import requests

from dora_api.domain.stock_status import (LOW_STOCK_SEQUENCE,
                                          OUT_OF_STOCK_SEQUENCE,
                                          STOCKED_SEQUENCE)
from dora_api.features.stock_items.create_stock_item import \
    CreateStockItemRequest

APP_SETTINGS = "http://localhost:5170/api/app-settings"
SHOPPING_LISTS = "http://localhost:5170/api/shopping-lists"
STOCK_ITEMS = "http://localhost:5170/api/stock-items"
STOCK_LEVELS = "http://localhost:5170/api/stock-levels"



#region ---------------- fixtures / helpers ----------------

@pytest.fixture
def levels_by_sequence():
    levels = requests.get(STOCK_LEVELS).json()["items"]
    return {l["sequence"]: l["stock_level_id"] for l in levels}


@pytest.fixture
def fresh_state(api):
    # Clear every active list so each test controls the draft count exactly —
    # the seed leaves several active lists (and their lines) around, which
    # would both skew `resolve_quick_add_target` and trip the dedup guard.
    # (`done` is /finish-only since FU-227 chunk 5, so DELETE the rest.)
    summaries = requests.get(SHOPPING_LISTS).json()
    for s in summaries:
        if s["status"] != "done":
            r = requests.delete(f"{SHOPPING_LISTS}/{s['shopping_list_id']}")
            assert r.status_code in (200, 204), r.text
    yield


def _set_mode(mode: str) -> None:
    resp = requests.patch(APP_SETTINGS, json={"auto_add_mode": mode})
    assert resp.status_code == 200, resp.text


def _create_list(name: str) -> str:
    resp = requests.post(SHOPPING_LISTS, json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()["shopping_list_id"]


def _create_item(level_id: str, *, flagged: bool) -> str:
    resp = requests.post(STOCK_ITEMS, json=CreateStockItemRequest(
        name=f"auto-add-{uuid4()}",
        stock_level_id=level_id,
        is_essential=flagged,
    ).model_dump(mode="json"))
    assert resp.status_code == 201, resp.text
    return resp.json()["stock_item_id"]


def _patch_level(item_id: str, level_id: str):
    return requests.patch(
        f"{STOCK_ITEMS}/{item_id}", json={"stock_level_id": level_id}
    )


def _lines_for_item(list_id: str, item_id: str) -> list[dict]:
    detail = requests.get(f"{SHOPPING_LISTS}/{list_id}").json()
    return [l for l in detail["lines"] if l["stock_item_id"] == item_id]


def _assert_fired(resp, item_id: str, list_id: str) -> None:
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["auto_added"]["shopping_list_id"] == list_id
    lines = _lines_for_item(list_id, item_id)
    assert len(lines) == 1
    assert lines[0]["is_auto_added"] is True
    assert lines[0]["line_id"] == body["auto_added"]["line_id"]


def _assert_silent(resp, item_id: str, list_id: str | None = None) -> None:
    assert resp.status_code == 204, resp.text
    if list_id is not None:
        assert _lines_for_item(list_id, item_id) == []

#endregion fixtures / helpers


#region ---------------- mode × flagged matrix ----------------

def test__auto_add__off_flagged_to_low__does_not_fire(
    fresh_state, levels_by_sequence
):
    # DORA_VERIFY L848 — Off never fires, even for an Essential item.
    _set_mode("off")
    draft = _create_list(f"off-{uuid4()}")
    item = _create_item(levels_by_sequence[STOCKED_SEQUENCE], flagged=True)

    resp = _patch_level(item, levels_by_sequence[LOW_STOCK_SEQUENCE])

    _assert_silent(resp, item, draft)


def test__auto_add__essential_only_flagged_to_low__fires(
    fresh_state, levels_by_sequence
):
    # The default-mode happy path: Essential item, single draft, Stocked→Low.
    _set_mode("essential_only")
    draft = _create_list(f"essential-{uuid4()}")
    item = _create_item(levels_by_sequence[STOCKED_SEQUENCE], flagged=True)

    resp = _patch_level(item, levels_by_sequence[LOW_STOCK_SEQUENCE])

    _assert_fired(resp, item, draft)


def test__auto_add__essential_only_unflagged_to_low__does_not_fire(
    fresh_state, levels_by_sequence
):
    # DORA_VERIFY L850 — Essential-only ignores non-Essential items.
    _set_mode("essential_only")
    draft = _create_list(f"essential-neg-{uuid4()}")
    item = _create_item(levels_by_sequence[STOCKED_SEQUENCE], flagged=False)

    resp = _patch_level(item, levels_by_sequence[LOW_STOCK_SEQUENCE])

    _assert_silent(resp, item, draft)


def test__auto_add__all_unflagged_to_low__fires(
    fresh_state, levels_by_sequence
):
    # DORA_VERIFY L849 (backend twin of the e2e happy path) — `all` fires
    # regardless of the Essential flag.
    _set_mode("all")
    draft = _create_list(f"all-{uuid4()}")
    item = _create_item(levels_by_sequence[STOCKED_SEQUENCE], flagged=False)

    resp = _patch_level(item, levels_by_sequence[LOW_STOCK_SEQUENCE])

    _assert_fired(resp, item, draft)


def test__auto_add__stocked_to_out__fires(
    fresh_state, levels_by_sequence
):
    # DORA_VERIFY L845 — the Out transition rides the same needs_restock
    # predicate as Low.
    _set_mode("essential_only")
    draft = _create_list(f"to-out-{uuid4()}")
    item = _create_item(levels_by_sequence[STOCKED_SEQUENCE], flagged=True)

    resp = _patch_level(item, levels_by_sequence[OUT_OF_STOCK_SEQUENCE])

    _assert_fired(resp, item, draft)

#endregion mode × flagged matrix


#region ---------------- transition guard ----------------

def test__auto_add__low_to_out__does_not_fire(
    fresh_state, levels_by_sequence
):
    # Low already needs restock, so Low→Out is not a transition into the
    # needs-restock band — no double-fire while an item worsens.
    _set_mode("essential_only")
    draft = _create_list(f"low-to-out-{uuid4()}")
    item = _create_item(levels_by_sequence[LOW_STOCK_SEQUENCE], flagged=True)

    resp = _patch_level(item, levels_by_sequence[OUT_OF_STOCK_SEQUENCE])

    _assert_silent(resp, item, draft)


def test__auto_add__out_to_stocked__does_not_fire(
    fresh_state, levels_by_sequence
):
    # A restock (rise) never fires.
    _set_mode("essential_only")
    draft = _create_list(f"restock-{uuid4()}")
    item = _create_item(levels_by_sequence[OUT_OF_STOCK_SEQUENCE], flagged=True)

    resp = _patch_level(item, levels_by_sequence[STOCKED_SEQUENCE])

    _assert_silent(resp, item, draft)

#endregion transition guard


#region ---------------- dedup guard ----------------

def test__auto_add__already_on_target_draft__does_not_fire(
    fresh_state, levels_by_sequence
):
    # DORA_VERIFY L851 — already on the draft: the manual line stays the only
    # line (no auto duplicate), and the PATCH is a plain 204.
    _set_mode("essential_only")
    draft = _create_list(f"dedup-draft-{uuid4()}")
    item = _create_item(levels_by_sequence[STOCKED_SEQUENCE], flagged=True)
    r = requests.post(f"{SHOPPING_LISTS}/{draft}/lines", json={"stock_item_id": item})
    assert r.status_code == 200, r.text

    resp = _patch_level(item, levels_by_sequence[LOW_STOCK_SEQUENCE])

    assert resp.status_code == 204, resp.text
    lines = _lines_for_item(draft, item)
    assert len(lines) == 1
    assert lines[0]["is_auto_added"] is False


def test__auto_add__already_on_other_active_list__does_not_fire(
    fresh_state, levels_by_sequence
):
    # DORA_VERIFY L851: the item already sits on one active list, so the
    # other one stays untouched.
    _set_mode("essential_only")
    shopping = _create_list(f"dedup-shopping-{uuid4()}")
    item = _create_item(levels_by_sequence[STOCKED_SEQUENCE], flagged=True)
    r = requests.post(f"{SHOPPING_LISTS}/{shopping}/lines", json={"stock_item_id": item})
    assert r.status_code == 200, r.text
    draft = _create_list(f"dedup-second-{uuid4()}")

    resp = _patch_level(item, levels_by_sequence[LOW_STOCK_SEQUENCE])

    _assert_silent(resp, item, draft)

#endregion dedup guard


#region ---------------- draft-count guard ----------------

def test__auto_add__zero_drafts__does_not_fire(
    fresh_state, levels_by_sequence
):
    # DORA_VERIFY L852 — no draft target at all: silent 204.
    _set_mode("essential_only")
    item = _create_item(levels_by_sequence[STOCKED_SEQUENCE], flagged=True)

    resp = _patch_level(item, levels_by_sequence[LOW_STOCK_SEQUENCE])

    _assert_silent(resp, item)


def test__auto_add__two_drafts__does_not_fire(
    fresh_state, levels_by_sequence
):
    # DORA_VERIFY L852 — 2+ drafts is ambiguous; the server never silently
    # picks one. Neither draft gains a line.
    _set_mode("essential_only")
    draft_a = _create_list(f"ambiguous-a-{uuid4()}")
    draft_b = _create_list(f"ambiguous-b-{uuid4()}")
    item = _create_item(levels_by_sequence[STOCKED_SEQUENCE], flagged=True)

    resp = _patch_level(item, levels_by_sequence[LOW_STOCK_SEQUENCE])

    _assert_silent(resp, item, draft_a)
    assert _lines_for_item(draft_b, item) == []


#endregion draft-count guard
