"""POST /api/alerts/<alert_id>/action — apply an action to an alert.

Alerts are *derived* from current state, not stored, so "dismissing" an
alert means changing the underlying state so it doesn't re-fire:

  - reset_expiry: clear `expiry_date` on the linked stock item
  - extend_expiry: push `expiry_date` forward by 7 days

(`mark_restocked` went 2026-10-15: the essential-low row now offers the stock
level picker itself, which writes through the stock-item endpoint like every
other level change, plus the shared cart button.)

(`acknowledge_stocktake` was removed with the `stocktake_overdue` kind at
Step-0 Q1 — it was that kind's only action, and "I looked at it" belongs in
the stocktake runner, which owns the freshness stamp.)

The alert_id is the stable scoped key `<scope>:<id>:<kind>` (alert_key.py).
Only stock-scoped alerts carry actions today; we extract the stock item id
and route by the action in the body. Non-stock scopes (meal / list / system,
C-9.4+) have no act_on_alert actions yet.
"""
import logging
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from dora_api.domain.entities.stock_item import StockItem
from dora_api.features.alerts.alert_key import SCOPE_STOCK, parse_alert_key
from dora_api.features.routers import ALERT_ROUTER
from dora_api.infrastructure.api_response import (bad_request,
                                                  business_rule_violation,
                                                  no_content, not_found)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository
from dora_api.features.stock_items.expiry_change import apply_expiry_change, push_expiry

_LOGGER = logging.getLogger(__name__)


ACTION_RESET_EXPIRY = "reset_expiry"
ACTION_EXTEND_EXPIRY = "extend_expiry"
# What the bell's "Push 7 days" moves an expiry by.
EXTEND_EXPIRY_DAYS = 7


class AlertActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str


@dataclass(slots=True)
class AlertActionResponse:
    item_not_found: bool = False
    invalid_action: bool = False


class AlertActionHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, stock_item_id: UUID, action: str) -> AlertActionResponse:
        item: StockItem | None = self.repository.get(StockItem).by_id(stock_item_id)
        if item is None:
            return AlertActionResponse(item_not_found=True)

        # Through the item's one expiry path, so the History tab records it.
        if action == ACTION_RESET_EXPIRY:
            apply_expiry_change(self.repository, item, None)
        elif action == ACTION_EXTEND_EXPIRY:
            push_expiry(self.repository, item, EXTEND_EXPIRY_DAYS)
        else:
            return AlertActionResponse(invalid_action=True)

        self.repository.save_changes()
        return AlertActionResponse()


@ALERT_ROUTER.route("/<alert_id>/action", methods=["POST"])
@has_request_body(AlertActionRequest)
def act_on_alert(alert_id: str):
    # `<scope>:<id>:<kind>` — only stock-scoped alerts carry actions; parse
    # out the stock item id and route by the action in the body.
    parsed = parse_alert_key(alert_id)
    if parsed is None or parsed.scope != SCOPE_STOCK or parsed.stock_item_id is None:
        return bad_request(f"Malformed or non-actionable alert id '{alert_id}'.")
    stock_item_id = parsed.stock_item_id

    _Request: AlertActionRequest = get_request_body()
    _Response = AlertActionHandler(SqlAlchemyRepository()).handle(
        stock_item_id, _Request.action
    )
    if _Response.item_not_found:
        return not_found("StockItem", stock_item_id)
    if _Response.invalid_action:
        return business_rule_violation(f"Unknown action '{_Request.action}'.")
    _LOGGER.info(
        f"Alert action {_Request.action} applied to {stock_item_id} (alert {alert_id})"
    )
    return no_content()
