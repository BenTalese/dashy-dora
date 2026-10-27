from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from dora_api.domain.entities.base_entity import BaseEntity


# Decision sentinels. Strings (not Enum) so SQLAlchemy stores varchar
# without the bind dance, matching SHOPPING_LIST_STATUS_* on ShoppingList
# and the waste-reason values on StockItemWasteEvent.
SUPPRESSION_DECISION_DISMISSED = "dismissed"
SUPPRESSION_DECISION_SNOOZED = "snoozed"

SUPPRESSION_DECISION_VALUES = {
    SUPPRESSION_DECISION_DISMISSED,
    SUPPRESSION_DECISION_SNOOZED,
}


@dataclass
class DoraSuggestionSuppression(BaseEntity):
    """P2-04 — a user's negative decision about a Dora suggestion.

    We never persist *generated* suggestions: the generators are
    deterministic and run fresh each call, so a row per suggestion would
    be churn for no payoff. We only need to remember the *negative*
    decisions the user has made — dismissed (permanent until the
    underlying condition changes) or snoozed (until `snoozed_until`).

    Dedup key is generator-defined. For "use_soon" it's the stock_item_id;
    for "frequent_waster" it's the stock_item_name; for "over_budget" the
    ISO period start. The generator's job is to choose a key that's stable
    across page-loads but specific enough that "dismiss this one" doesn't
    suppress the whole class of suggestion.
    """
    kind: str
    dedup_key: str
    decision: str
    snoozed_until: datetime | None
    created_at: datetime

    class Fields(BaseEntity.Fields):
        KIND = "kind"
        DEDUP_KEY = "dedup_key"
        DECISION = "decision"
        SNOOZED_UNTIL = "snoozed_until"
        CREATED_AT = "created_at"
