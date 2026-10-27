"""GET /api/shopping-lists/<id> — full detail with lines + linked products.

Each line carries enough info to render the row without further fetches:
stock item name and location, selected offer (if chosen) and *all* offers (so
the user can pick), and current ticked/quantity state. The money and store
ladders and the list totals are resolved here (R-003); the client renders
them.
"""
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List
from uuid import UUID

from dora_api.domain.location_breadcrumb import build_breadcrumb
from dora_api.domain.entities.store import Store
from dora_api.domain.entities.product import Product
from dora_api.domain.entities.shopping_list import (SHOPPING_LIST_STATUS_DONE,
                                                    ShoppingList,
                                                    ShoppingListLine)
from dora_api.domain.entities.preferred_buy import PreferredBuy
from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.entities.stock_location import StockLocation
from dora_api.features.routers import SHOPPING_LIST_ROUTER
from dora_api.features.shopping_lists._line_price import (line_paid_unit_price,
                                                        resolve_store_id)
from dora_api.features.stock_items.inference_overlay import (
    SURFACE_SHOPPING, divergent_items, surface_enabled)
from dora_api.features.shopping_lists.shopping_list_attachment_access import (
    get_attachment_metadata_for_list)
from dora_api.infrastructure.api_response import not_found, ok
from dora_api.infrastructure.session_user import current_user
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LineProductOfferDto:
    product_id: UUID
    name: str
    brand: str | None
    store_id: UUID
    store_name: str
    size: str | None
    price_now: float | None
    price_was: float | None
    is_selected: bool


def build_line_offers(item: StockItem | None, selected_product_id: UUID | None) -> List[LineProductOfferDto]:
    """Every offer linked to the item, cheapest first, then by store name.
    The item must be loaded with `products.store` and `products.current_offer`.
    Shared by the list detail and the template detail, which offer the same
    picker."""
    if item is None:
        return []
    offers = [
        LineProductOfferDto(
            product_id = product.id,
            name = product.name,
            brand = product.brand,
            store_id = product.store.id,
            store_name = product.store.name,
            size = product.size,
            price_now = product.current_offer.price_now if product.current_offer else None,
            price_was = product.current_offer.price_was if product.current_offer else None,
            is_selected = selected_product_id == product.id,
        )
        for product in item.products or []
    ]
    offers.sort(key=lambda o: (
        o.price_now if o.price_now is not None else float("inf"),
        o.store_name.lower(),
    ))
    return offers


# a stock item's PreferredBuy label as a pickable shopping hint.
@dataclass(frozen=True, slots=True)
class LinePreferredBuyDto:
    preferred_buy_id: UUID
    label: str


@dataclass(frozen=True, slots=True)
class ShoppingListLineDto:
    line_id: UUID
    # a line is anchored by stock_item_id OR product_id
    # (or both, when a product is nested under a stock item). NULL
    # stock_item_id ⇒ standalone-product line ("product only").
    stock_item_id: UUID | None
    product_id: UUID | None
    stock_item_name: str
    stock_location_id: UUID | None
    stock_location_breadcrumb: List[str]
    quantity: int | None
    is_ticked: bool
    selected_product_id: UUID | None
    sequence: int
    # True when the auto-add-on-low trigger placed this line here without
    # the user asking. Drives the one marker ShoppingListDetail renders on
    # a row. Auto-generated lines are False — the user picked those sources.
    is_auto_added: bool
    # what the shopper actually paid / where they
    # actually bought it. Both NULL until the user overrides on the line.
    actual_unit_price: float | None
    purchased_store_id: UUID | None
    purchased_store_name: str | None
    # Where the till-entry editor's suggestion comes from, as a human label
    # ("from your last receipt"), or None. The figure itself is
    # `estimated_unit_price`; the label is resolved here so the client just
    # renders the string (R-003).
    prefill_source_label: str | None = None
    offers: List[LineProductOfferDto] = field(default_factory=list)
    # the chosen hint + the item's available labels for the picker.
    preferred_buy_id: UUID | None = None
    preferred_buys: List[LinePreferredBuyDto] = field(default_factory=list)
    # trim-to-budget optimiser. True when this line has been set
    # aside by the "Trim to fit" pass; the SPA routes it into the
    # collapsible "Deferred to fit budget" section on the list-detail page
    # instead of the active list. Totals below skip deferred lines.
    # `deferred_reason` carries the chip vocab string from brief §5,
    # frozen at trim time.
    deferred_by_budget: bool = False
    deferred_reason: str | None = None
    # ── Redesign: sectioning + the two ladders ────────────────────────────
    # The stock item's group, for the "Order by → Group" sectioning mode.
    # None ⇒ the line falls into the trailing "Unsorted" section.
    stock_group_id: UUID | None = None
    stock_group_name: str | None = None
    # **Money ladder** (R-003 — resolved here, never re-derived client-side):
    # `actual_unit_price` → the offer the user picked on the row → the item's
    # last actual purchase → nothing. An unpicked offer never prices a line;
    # see the ladder in the handler. `estimate_source` names the rung.
    estimated_unit_price: float | None = None
    estimate_source: str = "none"   # 'actual' | 'offer' | 'historic' | 'none'
    # Where the last actual purchase was, so the price editor can name the
    # store even when the user has already typed an override for this trip.
    last_paid_store_id: UUID | None = None
    last_paid_store_name: str | None = None
    # Where the user *plans* to buy this line (`planned_store_id`), surfaced so
    # the plan face can edit it. Distinct from `purchased_store_id` above, which
    # is where they actually did.
    planned_store_id: UUID | None = None
    planned_store_name: str | None = None
    # The stock item's standing `usual_store_id`, surfaced so the row's store
    # picker can *mark* it — "Coles (usual)" — instead of describing it in the
    # empty option. The picker needs to distinguish "the store I buy this at
    # normally" from "the store I chose for this list", and only the server
    # knows the first.
    usual_store_id: UUID | None = None
    # **Store ladder**: bought-this-trip → **this list's planned store** → the
    # item's `usual_store_id` ("I always buy this here") → the store of the last
    # actual purchase (where you happened to buy it) → the chosen offer's store.
    # Intent beats history here, which is the reverse of the money ladder,
    # because this answers "where do I *plan* to buy it" — and the more specific
    # intent wins: a choice made for *this* list outranks a standing preference
    # for the item.
    # None ⇒ the "No store set" bucket in the breakdown + Store sectioning.
    resolved_store_id: UUID | None = None
    resolved_store_name: str | None = None


@dataclass(frozen=True, slots=True)
class StoreSpendDto:
    """One bucket of the plan-face store breakdown ("where you'll spend it").

    `store_id` is None for the catch-all "No store set" bucket. `subtotal`
    only sums lines that actually resolved a price, and `priced_line_count`
    says how many did — the UI needs both so it can admit "3 items unpriced,
    not counted" rather than presenting a confidently wrong total.
    """
    store_id: UUID | None
    store_name: str
    line_count: int
    priced_line_count: int
    subtotal: float
    # The store's own brand colour, derived from its uploaded logo
    # (`features/stores/_logo_colour.py`). None when the store has no logo,
    # or the logo has no usable hue — the SPA falls back to its deterministic
    # hash swatch there, so a bucket always has *a* colour.
    brand_colour: str | None = None


@dataclass(frozen=True, slots=True)
class ShoppingListTotalsDto:
    """Server-owned list-level money/count aggregates (state-ownership Type B).

    The browser used to sum these across the fetched lines on the dashboard;
    the server now owns the cross-line totals so the number
    can't silently disagree. Per-line *display* price stays a client concern
    (the accepted Type-C `priceOfLine` helper) — only the aggregate moved.

    `by_store` is here rather than in the client for exactly that reason: it is
    a cross-entity aggregate summed across a fetched collection, which R-003
    puts on the server side of the line.
    """
    total_price: float        # full price of every line
    remaining_price: float    # price of un-ticked lines only ("still to grab")
    # Price of the ticked lines only — "what's in the trolley". Server-owned
    # for the same R-003 reason as the rest: the run face's Picked section
    # needs it, and summing it across the fetched lines client-side would put
    # a second definition of the money ladder in the browser.
    picked_price: float
    total_savings: float      # savings vs RRP across all lines
    unticked_count: int
    ticked_count: int
    line_count: int
    # Ordered subtotal-desc, with the "No store set" bucket forced last.
    # Empty when no active line resolved a store at all — the UI hides the
    # whole card in that case rather than showing a single meaningless row.
    by_store: List[StoreSpendDto] = field(default_factory=list)


def _first_or_selected(offers: 'List[LineProductOfferDto]') -> 'LineProductOfferDto | None':
    """The offer a line is based on: the explicitly-selected one, else the
    first (the list is pre-sorted preferred→cheapest). Mirrors the client's
    `chosenOfferFor` exactly — both operate on the same server-sorted offers."""
    for offer in offers:
        if offer.is_selected:
            return offer
    return offers[0] if offers else None


def _line_price(line: 'ShoppingListLineDto') -> float:
    """What this line is expected to cost: the resolved money-ladder estimate
    times quantity.

    The ladder itself is applied once, in the handler, and lands on
    `estimated_unit_price` — this is only the quantity multiply. Before the
    redesign the ladder was inlined here as actual→offer; it now runs
    actual→historic→offer so a price you have actually paid outranks an
    advertised one, and so a user with no products at all still gets real
    totals off their own purchase history.
    """
    if line.estimated_unit_price is None:
        return 0.0
    return line.estimated_unit_price * (line.quantity or 1)


def _line_savings(line: 'ShoppingListLineDto') -> float:
    """(chosen offer RRP − what you paid) × qty, floored at 0.

    Only counts once there is a price the *user* stands behind — an entered
    price, or one carried from a past purchase. It used to fall back to the
    offer's own `price_now`, which meant a line could report a saving while
    contributing nothing to the total it was supposedly saving against
    (2026-09-17, with the offer rung's removal from the estimate ladder).
    """
    offer = _first_or_selected(line.offers)
    if offer is None or offer.price_was is None:
        return 0.0
    paid = line.estimated_unit_price
    if paid is None:
        return 0.0
    diff = offer.price_was - paid
    if diff <= 0:
        return 0.0
    return diff * (line.quantity or 1)


def compute_list_totals(
    lines: List['ShoppingListLineDto'],
    *,
    spent_only: bool = False,
    brand_colour_by_store: dict[UUID, str | None] | None = None,
) -> ShoppingListTotalsDto:
    """Aggregate the per-line price/savings into list-level totals. Single source
    for the dashboard's list card (it reads these instead of summing).

    FU-448 — lines with `deferred_by_budget=True` are not part of the active
    list; they render under the Deferred section and don't count toward
    projected total, savings, or ticked/unticked counts.

    ``spent_only`` switches the *money* from projection to record, and is set for
    a **done** list. While a list is being planned or shopped, an unticked line is
    money you are still expected to spend, so it belongs in the total. Once the
    shop is finished that line is something you decided not to buy — counting it
    would make the receipt claim money that never left the account, and would put
    unbought items in the "Where you spent it" split. The *counts* are unaffected:
    the receipt still needs to know how many lines it skipped."""
    total_price = 0.0
    remaining_price = 0.0
    picked_price = 0.0
    total_savings = 0.0
    unticked = 0
    active_line_count = 0
    # store_id (None = unassigned) → [name, line_count, priced_count, subtotal]
    _Buckets: dict[UUID | None, list] = {}
    for line in lines:
        if line.deferred_by_budget:
            continue
        active_line_count += 1
        price = _line_price(line)
        if not line.is_ticked:
            remaining_price += price
            unticked += 1
        else:
            picked_price += price
        # On a finished list an unticked line is money that was never spent, so
        # it drops out of the total, the savings and the store split alike.
        if spent_only and not line.is_ticked:
            continue
        total_price += price
        total_savings += _line_savings(line)
        _Key = line.resolved_store_id
        _Bucket = _Buckets.get(_Key)
        if _Bucket is None:
            _Bucket = [line.resolved_store_name or "No store set", 0, 0, 0.0]
            _Buckets[_Key] = _Bucket
        _Bucket[1] += 1
        # An unpriced line still counts toward its store's item count — it is
        # genuinely part of that shop — but must not silently contribute $0 to
        # the subtotal, or the card would read as a confident total that is
        # quietly short. `priced_line_count` is what lets the UI say so.
        if line.estimated_unit_price is not None:
            _Bucket[2] += 1
            _Bucket[3] += price
    _Colours = brand_colour_by_store or {}
    _ByStore = [
        StoreSpendDto(
            store_id = sid,
            store_name = b[0],
            line_count = b[1],
            priced_line_count = b[2],
            subtotal = b[3],
            brand_colour = _Colours.get(sid) if sid else None,
        )
        for sid, b in _Buckets.items()
    ]
    # Biggest spend first, but the catch-all bucket always sorts last — it is
    # a gap to fill, not a destination competing with the real stores.
    _ByStore.sort(key = lambda s: (s.store_id is None, -s.subtotal, s.store_name.lower()))
    # A breakdown needs at least one *real* store to be worth rendering; a
    # lone "No store set" row tells the user nothing they didn't know.
    if not any(s.store_id is not None for s in _ByStore):
        _ByStore = []
    return ShoppingListTotalsDto(
        total_price = total_price,
        remaining_price = remaining_price,
        picked_price = picked_price,
        total_savings = total_savings,
        unticked_count = unticked,
        ticked_count = active_line_count - unticked,
        line_count = active_line_count,
        by_store = _ByStore,
    )


# receipt-photo attachment metadata. Bytes never inlined; the SPA
# loads each via `GET /shopping-lists/<list_id>/attachments/<id>`.
@dataclass(frozen=True, slots=True)
class ShoppingListAttachmentDto:
    attachment_id: UUID
    sequence: int


@dataclass(frozen=True, slots=True)
class InferredSuggestionDto:
    """One "Dora thinks you're out of this" suggestion. `reason` is the belief's
    own plain-English why, so the chip can explain itself on tap."""
    stock_item_id: UUID
    name: str
    reason: str


@dataclass(frozen=True, slots=True)
class ShoppingListDetailDto:
    shopping_list_id: UUID
    # Custom name (None = self-labelled) + the resolved label to render —
    # same split as the summaries DTO; the fallback rule lives on the entity.
    name: str | None
    display_name: str
    status: str
    created_at: datetime
    completed_at: datetime | None
    totals: ShoppingListTotalsDto
    planned_shop_date: date | None = None
    lines: List[ShoppingListLineDto] = field(default_factory=list)
    # empty list when the list is a draft or has no attachments yet.
    attachments: List[ShoppingListAttachmentDto] = field(default_factory=list)
    # FU-653 — things Dora believes you've run out of that aren't on this list
    # yet. **Suggestions only**: nothing is added, no line is created, and the
    # list is identical whether or not you look at them (owner directive —
    # inference must not get in the way of the normal flow). Always empty when
    # the user hasn't opted the shopping surface in, and on a finished list
    # (suggesting additions to a completed shop is noise).
    inferred_suggestions: List['InferredSuggestionDto'] = field(default_factory=list)


@dataclass(slots=True)
class _DetailContext:
    """Everything a line needs, loaded in bulk once per read so N rows cost no
    per-row queries (finalisation 03-R35)."""
    stock_items: dict[UUID, StockItem]
    preferred_buys: dict[UUID, List[PreferredBuy]]
    product_names: dict[UUID, str]
    locations: dict[UUID, StockLocation]
    store_names: dict[UUID, str]
    store_colours: dict[UUID, str | None]
    # (when, price, store_id) of each item's latest actual purchase.
    prior_purchases: dict[UUID, tuple[datetime, float, UUID | None]]


class GetShoppingListDetailHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, shopping_list_id: UUID) -> ShoppingListDetailDto | None:
        _List: ShoppingList | None = self.repository.get(ShoppingList).by_id(shopping_list_id)
        if _List is None:
            return None

        _Lines: List[ShoppingListLine] = (
            self.repository.get(ShoppingListLine)
            .all(EntityField(ShoppingListLine, "shopping_list_id").eq(shopping_list_id))
        )
        _Lines.sort(key=lambda l: (l.sequence, l.id))

        _Context = self._load_context(shopping_list_id, _Lines)
        _LineDtos = [self._line_dto(line, _Context) for line in _Lines]

        # receipt-photo metadata. Only fetched for non-draft lists
        # (the UI hides the section on drafts anyway; saves a query for
        # the common case).
        _Attachments: List[ShoppingListAttachmentDto] = []
        if _List.status != "draft":
            _Attachments = [
                ShoppingListAttachmentDto(
                    attachment_id=row["id"], sequence=row["sequence"],
                )
                for row in get_attachment_metadata_for_list(_List.id)
            ]

        return ShoppingListDetailDto(
            inferred_suggestions = self._inferred_suggestions(_List, _Lines),
            shopping_list_id = _List.id,
            name = _List.name,
            display_name = _List.display_name,
            status = _List.status,
            created_at = _List.created_at,
            completed_at = _List.completed_at,
            planned_shop_date = _List.planned_shop_date,
            # A finished list's money is a record of what was spent, not a
            # projection of what might be (see `spent_only`).
            totals = compute_list_totals(
                _LineDtos,
                spent_only = _List.status == SHOPPING_LIST_STATUS_DONE,
                brand_colour_by_store = _Context.store_colours,
            ),
            lines = _LineDtos,
            attachments = _Attachments,
        )

    def _load_context(self, shopping_list_id: UUID, lines: List[ShoppingListLine]) -> _DetailContext:
        # Product-only lines have no stock_item_id; skip those when
        # assembling the stock-item id set.
        stock_item_ids = list({l.stock_item_id for l in lines if l.stock_item_id})
        stock_items: dict[UUID, StockItem] = {}
        preferred_buys: dict[UUID, List[PreferredBuy]] = {}
        if stock_item_ids:
            stock_items = {
                s.id: s
                for s in self.repository.get(StockItem)
                .include("stock_location")
                .include("stock_group")
                .include("products")
                    .then_include("store")
                .include("products")
                    .then_include("current_offer")
                .all(EntityField(StockItem, "id").in_(stock_item_ids))
            }
            # PreferredBuy labels, so each line can offer them as a hint picker.
            for pb in self.repository.get(PreferredBuy).all(
                EntityField(PreferredBuy, "stock_item_id").in_(stock_item_ids)
            ):
                preferred_buys.setdefault(pb.stock_item_id, []).append(pb)

        # Product names for product-only lines, so the DTO can fall back to
        # the product name when there's no anchor stock item to ask.
        product_ids = list({l.product_id for l in lines if l.product_id})
        product_names: dict[UUID, str] = {}
        if product_ids:
            product_names = {
                p.id: p.name
                for p in self.repository.get(Product).all(EntityField(Product, "id").in_(product_ids))
            }

        # Location lookup powers the per-line breadcrumb used to group lines
        # by shopper's route through the store. Loaded once and walked
        # locally so we don't do per-line ancestry queries.
        locations: dict[UUID, StockLocation] = {}
        if any(s.stock_location is not None for s in stock_items.values()):
            locations = {loc.id: loc for loc in self.repository.get(StockLocation).all()}

        prior_purchases = self._prior_purchases(shopping_list_id, stock_item_ids)

        # Every store any ladder can land on: `purchased_store_id` overrides,
        # this list's `planned_store_id`, the items' `usual_store_id`, and the
        # stores of prior actual purchases. One query covers all four, and the
        # store card's brand colour (2026-08-26 feedback) rides along.
        wanted_store_ids: set[UUID] = {l.purchased_store_id for l in lines if l.purchased_store_id}
        wanted_store_ids |= {l.planned_store_id for l in lines if l.planned_store_id}
        wanted_store_ids |= {s.usual_store_id for s in stock_items.values() if s.usual_store_id}
        wanted_store_ids |= {p[2] for p in prior_purchases.values() if p[2]}
        store_names: dict[UUID, str] = {}
        store_colours: dict[UUID, str | None] = {}
        if wanted_store_ids:
            stores = self.repository.get(Store).all(EntityField(Store, "id").in_(list(wanted_store_ids)))
            store_names = {s.id: s.name for s in stores}
            store_colours = {s.id: s.brand_colour for s in stores}

        return _DetailContext(
            stock_items=stock_items,
            preferred_buys=preferred_buys,
            product_names=product_names,
            locations=locations,
            store_names=store_names,
            store_colours=store_colours,
            prior_purchases=prior_purchases,
        )

    def _prior_purchases(
        self, shopping_list_id: UUID, stock_item_ids: List[UUID],
    ) -> dict[UUID, tuple[datetime, float, UUID | None]]:
        """The most recent *actual purchase* of each item on a prior finished
        list, priced via the shared actual→picked ladder: the till prefill,
        the money ladder's `historic` rung and the store ladder's "where you
        bought it last time" rung. Manual price observations are per-measure
        and feed "Your prices", not this per-item figure.

        Loads every ticked line ever for these items; a `MAX(completed_at)`
        join would bound it, but the repository port has no join and the
        ladders are now pinned end to end (FU-725), so it waits until a
        household's history makes it measurable (finalisation 03-R48)."""
        latest: dict[UUID, tuple[datetime, float, UUID | None]] = {}
        if not stock_item_ids:
            return latest
        prior_lines = self.repository.get(ShoppingListLine).all(
            EntityField(ShoppingListLine, ShoppingListLine.Fields.STOCK_ITEM_ID).in_(stock_item_ids)
            & EntityField(ShoppingListLine, ShoppingListLine.Fields.IS_TICKED).eq(True)
        )
        # Exclude the list being viewed (compare as str — the path param may
        # arrive as a string while the FK is a UUID).
        current_id = str(shopping_list_id)
        prior_list_ids = {
            l.shopping_list_id for l in prior_lines if str(l.shopping_list_id) != current_id
        }
        done_at: dict[UUID, datetime] = {}
        if prior_list_ids:
            for sl in self.repository.get(ShoppingList).all(
                EntityField(ShoppingList, "id").in_(list(prior_list_ids))
            ):
                if sl.is_done:
                    done_at[sl.id] = sl.completed_at or sl.created_at
        for l in prior_lines:
            completed = done_at.get(l.shopping_list_id)
            if completed is None:
                continue
            paid = line_paid_unit_price(l)
            if paid is None:
                continue
            prev = latest.get(l.stock_item_id)
            if prev is None or completed > prev[0]:
                latest[l.stock_item_id] = (completed, paid, l.purchased_store_id)
        return latest

    def _line_dto(self, line: ShoppingListLine, ctx: _DetailContext) -> ShoppingListLineDto:
        item = ctx.stock_items.get(line.stock_item_id) if line.stock_item_id else None
        offers = build_line_offers(item, line.selected_product_id)
        # Live anchor first, then the product name for product-only lines,
        # then the name frozen at finish (FU-883) for a historic line whose
        # anchor has since been deleted. "(missing item)" stays as the last
        # resort — a line can only reach it if it was orphaned without ever
        # being finished.
        display_name = (
            item.name if item
            else (ctx.product_names.get(line.product_id) if line.product_id else None)
            or line.display_name_snapshot
            or "(missing item)"
        )
        prior = ctx.prior_purchases.get(line.stock_item_id) if line.stock_item_id else None
        chosen = _first_or_selected(offers)

        # ── Money ladder ─────────────────────────────────────────────
        # actual → picked offer → historic → none.
        #
        # The offer rung is an offer the user **picked** on the row, never
        # the cheapest-offer fallback `chosen` uses for the store ladder.
        # 2026-09-17 took offers out of the ladder entirely: history
        # outranked them, so committing to one changed nothing on any line
        # you had bought before, and an unpicked offer produced a confident
        # total from prices nobody had agreed to. The owner's 2026-09-27
        # call keeps the second half of that and fixes the first: picking
        # an offer is the agreement, so it outranks what you paid last
        # time, and un-picking it puts the old figure back. It is still an
        # estimate; nothing is recorded as spend until a price is entered
        # in shop mode.
        picked = next((o for o in offers if o.is_selected), None)
        estimate: float | None = None
        estimate_source = "none"
        if line.actual_unit_price is not None:
            estimate = float(line.actual_unit_price)
            estimate_source = "actual"
        elif picked is not None and picked.price_now is not None:
            estimate = float(picked.price_now)
            estimate_source = "offer"
        elif prior is not None:
            estimate = prior[1]
            estimate_source = "historic"

        # ── Store ladder ─────────────────────────────────────────────
        # Ordering + rationale live in `_line_price.resolve_store_id`, the
        # R-003 chokepoint (the money ladder's twin).
        store_id = resolve_store_id(
            purchased_store_id = line.purchased_store_id,
            planned_store_id = line.planned_store_id,
            usual_store_id = item.usual_store_id if item is not None else None,
            last_purchase_store_id = prior[2] if prior is not None else None,
            chosen_offer_store_id = chosen.store_id if chosen is not None else None,
        )
        store_name = ctx.store_names.get(store_id) if store_id else None
        # The offers list carries names the store lookup never saw (it is
        # seeded from lines and items, not products), so fall back to the
        # offer's own copy rather than dropping the line into "No store set".
        if store_id is not None and store_name is None:
            store_name = next((o.store_name for o in offers if o.store_id == store_id), None)

        return ShoppingListLineDto(
            line_id = line.id,
            stock_item_id = line.stock_item_id,
            product_id = line.product_id,
            stock_item_name = display_name,
            stock_location_id = (
                item.stock_location.id if item and item.stock_location else None
            ),
            # R-003 — the walk itself lives in `domain.location_breadcrumb`.
            stock_location_breadcrumb = (
                build_breadcrumb(item.stock_location, ctx.locations) if item else []
            ),
            quantity = line.quantity,
            is_ticked = bool(line.is_ticked),
            selected_product_id = line.selected_product_id,
            sequence = line.sequence,
            is_auto_added = line.is_auto_added,
            deferred_by_budget = bool(line.deferred_by_budget),
            deferred_reason = line.deferred_reason,
            actual_unit_price = line.actual_unit_price,
            purchased_store_id = line.purchased_store_id,
            purchased_store_name = (
                ctx.store_names.get(line.purchased_store_id) if line.purchased_store_id else None
            ),
            planned_store_id = line.planned_store_id,
            planned_store_name = (
                ctx.store_names.get(line.planned_store_id) if line.planned_store_id else None
            ),
            usual_store_id = item.usual_store_id if item is not None else None,
            # D3 prefill: the editor seeds from the estimate; only a prior
            # actual purchase earns a source label.
            prefill_source_label = "from your last receipt" if prior is not None else None,
            offers = offers,
            preferred_buy_id = line.preferred_buy_id,
            preferred_buys = sorted(
                (
                    LinePreferredBuyDto(preferred_buy_id = pb.id, label = pb.label)
                    for pb in ctx.preferred_buys.get(line.stock_item_id, [])
                ),
                key=lambda d: d.label.lower(),
            ),
            stock_group_id = item.stock_group.id if item and item.stock_group else None,
            stock_group_name = item.stock_group.name if item and item.stock_group else None,
            estimated_unit_price = estimate,
            estimate_source = estimate_source,
            last_paid_store_id = prior[2] if prior else None,
            last_paid_store_name = (
                ctx.store_names.get(prior[2]) if prior and prior[2] else None
            ),
            resolved_store_id = store_id,
            resolved_store_name = store_name,
        )

    # FU-653 — the shopping surface of the Zero-Input belief overlay.
    _MAX_SUGGESTIONS = 6

    def _inferred_suggestions(
        self, shopping_list: ShoppingList, lines: List[ShoppingListLine],
    ) -> List[InferredSuggestionDto]:
        """Items Dora believes are out, that this list doesn't already carry.

        Scoped to items *recorded* as available — an item you've already
        recorded as out is the existing low-stock machinery's job (auto-add,
        the Needs-restock filter), and repeating it here as a "suggestion"
        would be Dora taking credit for what you told her.

        Capped: this is a nudge beside the list, not a second list. Sorted by
        name so the order is stable between refreshes rather than shuffling
        with belief confidence.
        """
        # The gate comes first so a surface that's off never loads the
        # whole pantry to say nothing (finalisation 03-R36).
        if shopping_list.is_done or not surface_enabled(current_user(self.repository), SURFACE_SHOPPING):
            return []
        already_on_list = {l.stock_item_id for l in lines if l.stock_item_id}
        candidates = self.repository.get(StockItem).all()
        candidates = [c for c in candidates if c.id not in already_on_list]
        divergence = divergent_items(self.repository, candidates)
        if not divergence.believed_out:
            return []
        by_id = {c.id: c for c in candidates}
        out = [
            InferredSuggestionDto(
                stock_item_id = item_id,
                name = by_id[item_id].name,
                reason = divergence.reasons.get(item_id, ""),
            )
            for item_id in divergence.believed_out
            if item_id in by_id
        ]
        out.sort(key=lambda s: s.name.lower())
        return out[:self._MAX_SUGGESTIONS]


@SHOPPING_LIST_ROUTER.route("/<uuid:shopping_list_id>", methods=["GET"])
def get_shopping_list_detail(shopping_list_id: UUID):
    _Detail = GetShoppingListDetailHandler(SqlAlchemyRepository()).handle(shopping_list_id)
    if _Detail is None:
        return not_found("ShoppingList", shopping_list_id)
    _LOGGER.debug(
        "Shopping list %s detail: %d lines", shopping_list_id, len(_Detail.lines)
    )
    return ok(_Detail)
