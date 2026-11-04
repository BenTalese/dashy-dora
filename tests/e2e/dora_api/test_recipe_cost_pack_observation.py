"""QA2-18: a recipe's "1 pack" priced from what was paid on a shopping list.

A counted observation ("$6 for 12 ea") can't say on its own whether it was one
carton of twelve or twelve loose eggs. When it came off a shopping list, the
line's quantity does: the whole-pack price is the line total over it.
"""
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
import requests

from dora_api.app import app
from dora_api.domain.entities.stock_item_price_observation import \
    StockItemPriceObservation
from dora_api.features.recipes.recipe_cost import _unit_price_map
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.persistence.uuid_key import uuid_key

BASE = "http://localhost:5170/api"


def _stocked_level_id() -> str:
    levels = requests.get(f"{BASE}/stock-levels").json()["items"]
    return next(l["stock_level_id"] for l in levels if l["sequence"] == 0)


def _item_on_a_list(quantity: int) -> tuple[str, str]:
    item = requests.post(f"{BASE}/stock-items", json={
        "name": f"Pack Obs Item {uuid4().hex[:8]}", "stock_level_id": _stocked_level_id(),
    })
    assert item.status_code == 201, item.text
    lst = requests.post(f"{BASE}/shopping-lists", json={"name": f"Pack Obs {uuid4().hex[:8]}"})
    assert lst.status_code == 201, lst.text
    line = requests.post(
        f"{BASE}/shopping-lists/{lst.json()['shopping_list_id']}/lines",
        json={"stock_item_id": item.json()["stock_item_id"], "quantity": quantity},
    )
    assert line.status_code in (200, 201), line.text
    body = line.json()
    line_id = body.get("shopping_list_line_id") or body.get("line_id") or body.get("id")
    assert line_id, body
    return item.json()["stock_item_id"], line_id


def _whole_pack_after_paying(total: float, measure: float, quantity: int) -> float | None:
    item_id, line_id = _item_on_a_list(quantity)
    now = datetime.now(timezone.utc)
    with app.app_context():
        repo = SqlAlchemyRepository()
        repo.add(StockItemPriceObservation(
            stock_item_id=UUID(item_id), total_price=total, total_measure=measure,
            unit="ea", observed_at=now, store_id=None,
            shopping_list_line_id=UUID(line_id), created_at=now,
        ))
        repo.save_changes()
        _, obs = _unit_price_map(repo, [UUID(item_id)])
        return obs[uuid_key(item_id)].whole_pack_amount


def test__one_carton_of_twelve__is_the_whole_pack():
    assert _whole_pack_after_paying(6.0, 12, quantity=1) == pytest.approx(6.0)


def test__two_cartons__divide_by_the_line_quantity():
    assert _whole_pack_after_paying(12.0, 24, quantity=2) == pytest.approx(6.0)
