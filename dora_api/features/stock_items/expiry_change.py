"""One path for every change to a stock item's expiry date.

`apply_expiry_change` writes the date and records the History-tab transition
(set / pushed / cleared) the same way for the item PATCH, the push-expiry
endpoint and the bell's alert actions, so no path skips the event. The
"+N days" rule lives here once (finalisation 05-R2 / 06-R1): from the later of
the household's today and the current expiry, so +1 on an expired item reads
"tomorrow" and +1 on a future date moves that date by a day.

  POST /api/stock-items/<id>/push-expiry   body {days}  → {expiry_date}
"""
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.entities.stock_item_expiry_event import (
    StockItemExpiryEvent, classify_expiry_transition,
)
from dora_api.features.app_settings.clock import household_today
from dora_api.features.routers import STOCK_ITEM_ROUTER
from dora_api.infrastructure.api_response import not_found, ok
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.ports import Repository
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository


def pushed_expiry(current: date | None, today: date, days: int) -> date:
    return max(today, current or today) + timedelta(days=days)


def apply_expiry_change(repository: Repository, item: StockItem, new_expiry: date | None) -> None:
    """Set the item's expiry and record the transition (a same-date write
    records nothing). The caller saves."""
    previous = item.expiry_date
    item.expiry_date = new_expiry
    transition = classify_expiry_transition(previous, new_expiry)
    if transition is None:
        return
    kind, delta = transition
    repository.add(StockItemExpiryEvent(
        stock_item_id = item.id,
        kind = kind,
        previous_expiry_date = previous,
        new_expiry_date = new_expiry,
        delta_days = delta,
        occurred_at = datetime.now(UTC),
    ))


def push_expiry(repository: Repository, item: StockItem, days: int) -> date:
    new_expiry = pushed_expiry(item.expiry_date, household_today(repository), days)
    apply_expiry_change(repository, item, new_expiry)
    return new_expiry


class PushExpiryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    days: int = Field(ge=1, le=365)


@dataclass(frozen=True, slots=True)
class PushExpiryResponse:
    expiry_date: date


@STOCK_ITEM_ROUTER.route("<uuid:stock_item_id>/push-expiry", methods=["POST"])
@has_request_body(PushExpiryRequest)
def push_stock_item_expiry(stock_item_id: UUID):
    repo = SqlAlchemyRepository()
    item: StockItem | None = repo.get(StockItem).by_id(stock_item_id)
    if item is None:
        return not_found(StockItem.__name__, stock_item_id)
    request: PushExpiryRequest = get_request_body()
    new_expiry = push_expiry(repo, item, request.days)
    repo.save_changes()
    return ok(PushExpiryResponse(expiry_date=new_expiry))
