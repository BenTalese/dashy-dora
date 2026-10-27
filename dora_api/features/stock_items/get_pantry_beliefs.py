"""P8-07 — Zero-Input Pantry belief endpoint.

  GET /api/stock-items/beliefs

Returns the inferred belief (band + confidence + reason) for every stock
item, computed server-side (R-003) from the closed loop. The SPA overlays
these as additive "Dora thinks…" chips beside the manually-recorded level
on the stock overview + detail.

Gated on the per-user `inferred_pantry_enabled` opt-out (default on). When
a user has switched inference off, the endpoint short-circuits to
`{enabled: false, beliefs: {}}` so the client never renders the overlay —
belt-and-braces alongside the SPA's own gate.
"""
import logging

from dora_api.domain.entities.stock_item import StockItem
from dora_api.features.routers import STOCK_ITEM_ROUTER
from dora_api.features.stock_items.pantry_belief import (PantryBelief,
                                                         gather_beliefs_for_items)
from dora_api.infrastructure.api_response import ok
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.session_user import current_user


_LOGGER = logging.getLogger(__name__)


def _belief_dto(belief: PantryBelief) -> dict:
    """The five fields a surface renders. `believed_sequence` and the float
    `confidence` stay on the dataclass for ranking; no client reads them
    (finalisation 07-R12)."""
    return {
        "believed_band": belief.believed_band,
        "confidence_band": belief.confidence_band,
        "reason": belief.reason,
        "is_inferred": belief.is_inferred,
        "differs_from_recorded": belief.differs_from_recorded,
    }


@STOCK_ITEM_ROUTER.route("/beliefs", methods=["GET"])
def get_pantry_beliefs():
    repo = SqlAlchemyRepository()

    # Respect the per-user opt-out. A missing user (shouldn't happen behind
    # auth) is treated as "off" — no overlay rather than a surprise.
    user = current_user(repo)
    if user is None or not user.inferred_pantry_enabled:
        return ok({"enabled": False, "beliefs": {}})

    # The belief resolves the recorded level by FK; no include needed.
    items: list[StockItem] = repo.get(StockItem).all()
    beliefs = gather_beliefs_for_items(repo, items)
    _LOGGER.debug("pantry beliefs computed for %d items", len(beliefs))
    return ok({
        "enabled": True,
        "beliefs": {str(item_id): _belief_dto(belief) for item_id, belief in beliefs.items()},
    })
