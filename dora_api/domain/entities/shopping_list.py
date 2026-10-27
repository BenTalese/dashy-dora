from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List
from uuid import UUID

from dora_api.domain.entities.base_entity import BaseEntity


# the single source of truth for where a list is
# in the shop loop, replacing the old is_archived / is_in_progress flags.
#   draft    : being assembled / edited (the old "planning", non-archived,
#              not-in-progress state).
#   shopping : actively being shopped right now (was is_in_progress).
#   done     : finished or archived (was is_archived). completed_at carries
#              the timestamp.
# Plain str sentinels (not Enum) so SQLAlchemy stores them as varchar.
SHOPPING_LIST_STATUS_DRAFT = "draft"
SHOPPING_LIST_STATUS_SHOPPING = "shopping"
SHOPPING_LIST_STATUS_DONE = "done"

SHOPPING_LIST_STATUS_VALUES = {
    SHOPPING_LIST_STATUS_DRAFT,
    SHOPPING_LIST_STATUS_SHOPPING,
    SHOPPING_LIST_STATUS_DONE,
}


@dataclass
class ShoppingListLine(BaseEntity):
    shopping_list_id: UUID
    # a line is anchored by stock_item_id OR product_id
    # (or both, when a product is nested under a stock item). At least
    # one anchor MUST be set while the line is live; enforced by a DB CHECK
    # + the add-line validator. Once the list is finished the CHECK also
    # accepts `display_name_snapshot` alone — see that field.
    stock_item_id: UUID | None = None
    product_id: UUID | None = None
    # The line's display name, frozen when the list is finished.
    #
    # A finished list is a receipt, and a receipt must not lose entries
    # because the pantry moved on. Both anchors are ON DELETE SET NULL, so
    # deleting a stock item or product leaves the historic line standing —
    # but the *name* only ever lived on the anchor row, so without this the
    # survivor would be nameless (which is why those FKs used to CASCADE and
    # take the line with them).
    #
    # Written at `POST /finish` only. That is already the moment prices are
    # frozen (`picked_offer_price` / `list_price_at_pick`) and is the enforced
    # sole path to `done`, so it is the one place a list becomes immutable.
    # Deliberately NOT written at add time: ~90% of lines never outlive their
    # referent, so a copy per line would be dead weight and would need
    # rename-drift handling. Lines on draft/shopping lists are deleted
    # outright when their anchor goes, so they never need one.
    display_name_snapshot: str | None = None
    quantity: int | None = None
    is_ticked: bool = False
    selected_product_id: UUID | None = None
    sequence: int = 0
    # True only for lines no user action put here directly: the low-stock
    # auto-add hook in update_stock_item (FU-511: fires per
    # AppSetting.auto_add_mode + is_essential), which drops an item onto a
    # list as a knock-on of a stock level changing somewhere else. Lines
    # the user asked for are False — including every /auto-generate line,
    # because the user ticked the sources that produced them. If a user
    # later edits the line (quantity/product), the caller clears this so
    # the marker disappears.
    is_auto_added: bool = False
    added_at: datetime | None = None
    # The offer snapshot pair. Nothing has written `picked_offer_price` since
    # 2026-09-17: an offer price is the shop's advertised number, not the
    # user's money, so a shop the user never priced recorded spend they had
    # never confirmed. Pricing is explicit now (the price editor can pull an
    # offer's price in with one tap), and a list with no prices entered records
    # no spend. Lines finished before then still hold real values, which
    # Reports and the paid-price ladder (`_line_price`) read, so the columns
    # stay. `list_price_at_pick` is still written alongside an entered price
    # (`snapshot_offer_rrp`) so a saving can be shown.
    picked_offer_price: float | None = None
    list_price_at_pick: float | None = None
    # what the shopper *actually* paid (per unit) and
    # which store they actually bought it from, when those differ from the
    # planned offer. Either may be set independently — a user might confirm
    # the store on the chip but type a different till-receipt price, or vice
    # versa. Both NULL = use the picked_offer_price snapshot as the historic
    # paid price (the previous behaviour). When set, actual_unit_price wins
    # for totals and for the assistant's price-history queries.
    actual_unit_price: float | None = None
    purchased_store_id: UUID | None = None
    # **Where you intend to buy this, for this list.** Distinct from
    # `purchased_store_id`, which records where you *actually* bought it and is
    # only meaningful once the shop has happened. Before this existed the plan
    # face had no way to say "get this one at Aldi" — the only writable store on
    # a line was the bought-from stamp, so planning and recording shared one
    # field and the intent could only be expressed by pre-filling the record.
    # The other candidate, `StockItem.usual_store_id`, is a *standing*
    # preference: setting it from a list would change every future list too.
    # Prefill chain (each is the default for the next, never a write-back):
    #   usual_store_id → planned_store_id → purchased_store_id
    planned_store_id: UUID | None = None
    # optional shopping hint: one of the stock item's PreferredBuy
    # labels (PROPOSAL_PRODUCTS_AS_OVERLAY §3.1). Reference-only — no DB FK
    # constraint (see the table mapping / migration re: FU-178); a deleted
    # PreferredBuy just leaves a dangling id the SPA ignores.
    preferred_buy_id: UUID | None = None
    # trim-to-budget optimiser (PROPOSAL_BUDGET_AWARE_LISTS §7.2).
    # True when the line was set aside by the "Trim to fit" pass to keep the
    # projected shop within the user's period-remaining budget. Deferred
    # lines don't contribute to projected totals or ticked/unticked counts;
    # they render under a "Deferred to fit budget" collapsible section
    # on the SPA with a one-tap "Add back". `deferred_reason` freezes the
    # trim-time chip (fixed vocab, brief §5); deviates from brief §7.2 which
    # first said "derive on read" — but re-running the classifier on every
    # detail read is wasteful and lets the chip drift if state (verdict,
    # cadence, meal-plan) changes between the trim tap and the read.
    deferred_by_budget: bool = False
    deferred_reason: str | None = None

    class Fields(BaseEntity.Fields):
        SHOPPING_LIST_ID = "shopping_list_id"
        STOCK_ITEM_ID = "stock_item_id"
        PRODUCT_ID = "product_id"
        QUANTITY = "quantity"
        IS_TICKED = "is_ticked"
        SELECTED_PRODUCT_ID = "selected_product_id"
        SEQUENCE = "sequence"
        IS_AUTO_ADDED = "is_auto_added"
        ADDED_AT = "added_at"
        PICKED_OFFER_PRICE = "picked_offer_price"
        LIST_PRICE_AT_PICK = "list_price_at_pick"
        ACTUAL_UNIT_PRICE = "actual_unit_price"
        PURCHASED_STORE_ID = "purchased_store_id"
        PLANNED_STORE_ID = "planned_store_id"
        PREFERRED_BUY_ID = "preferred_buy_id"
        DEFERRED_BY_BUDGET = "deferred_by_budget"
        DEFERRED_REASON = "deferred_reason"
        DISPLAY_NAME_SNAPSHOT = "display_name_snapshot"


def format_list_date(value: date, today: date | None = None) -> str:
    """Human label for a list's date-derived display name ("Sat 14 Jun");
    the year is appended only when it isn't the current one.

    R-021 carve-out: this is a pure display formatter, called from
    `ShoppingList.display_name` (a @property with no repository access).
    The `today` fallback is server-local — at worst, this can drop or
    keep "current year" mistakenly for a handful of hours around 31 Dec
    in households whose offset crosses the year line vs. the server's.
    The fallback is documented; callers with a repository handy SHOULD
    pass `household_today(repository)`. Display-only — never used for
    date-boundary logic.
    """
    today = today or date.today()
    fmt = "%a %d %b" if value.year == today.year else "%a %d %b %Y"
    return value.strftime(fmt)


@dataclass
class ShoppingList(BaseEntity):
    # The user's custom name. None = no custom name — the list labels itself
    # from its dates via `display_name` below. (UX-v2: was NOT NULL with a
    # date string baked in at create time, which went stale the moment a
    # planned shop date was set or changed.)
    name: str | None
    created_at: datetime
    # Lifecycle status (see SHOPPING_LIST_STATUS_* above). Transitions:
    #   draft    -> shopping : user clicks Start shopping
    #   draft/shopping -> done : Finish (restock review)
    # Once a list is done, it's done — there is no Reopen. (UX-v2 removed the
    # shopping -> draft "stop/pause" transition and the restock-less "archive"
    # path; the undo posture removal in FU-163 retired Reopen too — lists are
    # finished or deleted.)
    status: str = SHOPPING_LIST_STATUS_DRAFT
    completed_at: datetime | None = None
    # Optional shopping day the user is planning this list
    # for. Drives the landing-page pick (today's list wins), the selector's
    # sort, and the shopping-day banner. Never required — a list without a
    # planned date still behaves the same as today.
    planned_shop_date: date | None = None
    # Lines hang off the list. Loaded explicitly by handlers that need them
    # (matches the noload pattern used elsewhere — table_mappings sets
    # lazy="noload"). Default empty so seed/in-memory construction works.
    lines: List[ShoppingListLine] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        """Server-owned display name (R-003): the custom name when set, else
        the planned shop date, else the creation date. Clearing the custom
        name makes the list re-label itself from its dates."""
        if self.name:
            return self.name
        if self.planned_shop_date:
            return format_list_date(self.planned_shop_date)
        created = (
            self.created_at.date()
            if isinstance(self.created_at, datetime) else self.created_at
        )
        return format_list_date(created)

    @property
    def effective_date(self) -> date:
        """Where the list sits in time, for ordering and the next-up pick:
        finalised shop date (completed_at) > planned shop date > created."""
        if self.is_done and self.completed_at:
            return self.completed_at.date()
        if self.planned_shop_date:
            return self.planned_shop_date
        return (
            self.created_at.date()
            if isinstance(self.created_at, datetime) else self.created_at
        )

    @property
    def is_done(self) -> bool:
        return self.status == SHOPPING_LIST_STATUS_DONE

    @property
    def is_shopping(self) -> bool:
        return self.status == SHOPPING_LIST_STATUS_SHOPPING

    @property
    def is_draft(self) -> bool:
        return self.status == SHOPPING_LIST_STATUS_DRAFT

    class Fields(BaseEntity.Fields):
        NAME = "name"
        STATUS = "status"
        CREATED_AT = "created_at"
        COMPLETED_AT = "completed_at"
        PLANNED_SHOP_DATE = "planned_shop_date"
        LINES = "lines"
