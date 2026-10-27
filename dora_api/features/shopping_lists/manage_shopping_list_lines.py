"""Add / update / delete shopping list lines, plus quick-add.

Lines are the per-stock-item rows on a list. Endpoints:

  POST   /api/shopping-lists/<id>/lines        — add a line
  PATCH  /api/shopping-lists/<id>/lines/<lid>  — tick, quantity, selected_product
  DELETE /api/shopping-lists/<id>/lines/<lid>
  POST   /api/shopping-lists/quick-add/lines     — quick-add (DRAFT-count inference)

P6-01 Chunk 2: there is no user-set "main list" flag — quick-add resolves the
target by counting DRAFT lists (see quick_add_target_resolver.py). The client may
pass `shopping_list_id` to disambiguate the 2+ case (and remember the pick in
sessionStorage).
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.product import Product
from dora_api.domain.entities.product_offer import ProductOffer
from dora_api.domain.entities.shopping_list import (SHOPPING_LIST_STATUS_DONE,
                                                    SHOPPING_LIST_STATUS_DRAFT,
                                                    ShoppingList,
                                                    ShoppingListLine)
from dora_api.domain.entities.stock_item import StockItem
from dora_api.features.routers import SHOPPING_LIST_ROUTER
from dora_api.features.shopping_lists._line_defaults import apply_line_defaults
from dora_api.features.shopping_lists._observation_sync import (
    sync_line_observations)
from dora_api.features.shopping_lists.quick_add_target_resolver import (
    QuickAddTargetCandidate, resolve_quick_add_target)
from dora_api.infrastructure.api_response import (business_rule_violation, ok,
                                                  no_content, not_found)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


# ───── Add line ───────────────────────────────────────────────────────────

class AddLineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # a line may anchor on a stock item, a product, or
    # both. At least one MUST be set; validated below + at the DB
    # (CHECK ck_shopping_list_line_anchor). `product_id` enables the
    # "standalone product line" path (L130 / L191 rule 1): a product
    # whose linked stock item isn't on the list adds as its own row.
    stock_item_id: UUID | None = None
    product_id: UUID | None = None
    quantity: int | None = Field(default=1, ge=1)
    selected_product_id: UUID | None = None
    # A recipe ingredient's picked preferred buy, carried onto the line.
    # Reference-only, like the column.
    preferred_buy_id: UUID | None = None
    # Omitted by every current caller; the handler falls back to the stock
    # item's `usual_store_id`. Present so a caller that *knows* the store —
    # a meal-plan build, a template with a store on it — can say so rather
    # than having the usual one applied over the top of it.
    planned_store_id: UUID | None = None


@dataclass(slots=True)
class AddLineResponse:
    line_id: UUID | None = None
    list_not_found: bool = False
    item_not_found: bool = False
    product_not_found: bool = False
    no_anchor: bool = False
    already_on_list: bool = False


class AddLineHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(
        self, request: AddLineRequest, shopping_list_id: UUID, *, commit: bool = True,
    ) -> AddLineResponse:
        """`commit=False` leaves the save to a bulk caller (one commit per
        request, FU-713)."""
        # anchor validation. At least one of
        # stock_item_id/product_id is required; the DB enforces it too
        # but failing early gives the SPA a clean 400.
        if request.stock_item_id is None and request.product_id is None:
            return AddLineResponse(no_anchor=True)

        lst: ShoppingList | None = self.repository.get(ShoppingList).by_id(shopping_list_id)
        if lst is None:
            return AddLineResponse(list_not_found=True)

        item: StockItem | None = None
        if request.stock_item_id is not None:
            item = self.repository.get(StockItem).by_id(request.stock_item_id)
            if item is None:
                return AddLineResponse(item_not_found=True)
        if request.product_id is not None:
            product: Product | None = self.repository.get(Product).by_id(request.product_id)
            if product is None:
                return AddLineResponse(product_not_found=True)

        # dedupe by anchor. Same stock_item_id OR same
        # product_id on the same list = already on list. (A product
        # nested under a stock item carries both columns; either
        # match counts.)
        sibling_lines = self.repository.get(ShoppingListLine).all(
            EntityField(ShoppingListLine, "shopping_list_id").eq(shopping_list_id)
        )
        existing = None
        for sibling in sibling_lines:
            if (
                request.stock_item_id is not None
                and sibling.stock_item_id == request.stock_item_id
                and sibling.product_id is None
            ):
                existing = sibling
                break
            if (
                request.product_id is not None
                and sibling.product_id == request.product_id
            ):
                existing = sibling
                break
        if existing is not None:
            return AddLineResponse(line_id=existing.id, already_on_list=True)

        # Sequence = current max + 1 so new lines append.
        next_sequence = (max((l.sequence for l in sibling_lines), default=-1)) + 1

        # Planned store, preferred buy and picked offer are prefilled from
        # the item — its usual store, and whatever you chose for it last time
        # (`_line_defaults`). The usual store is written down rather than
        # inherited at read time (owner, 2026-09-17) so the row's store picker
        # shows a real choice and "Any store" keeps meaning *no store*.
        line = ShoppingListLine(
            shopping_list_id = shopping_list_id,
            stock_item_id = request.stock_item_id,
            product_id = request.product_id,
            quantity = request.quantity,
            selected_product_id = request.selected_product_id,
            preferred_buy_id = request.preferred_buy_id,
            planned_store_id = request.planned_store_id,
            sequence = next_sequence,
            added_at = datetime.now(timezone.utc),
        )
        apply_line_defaults(self.repository, [line])
        self.repository.add(line)
        if commit:
            self.repository.save_changes()
        return AddLineResponse(line_id=line.id)


@SHOPPING_LIST_ROUTER.route("/<uuid:shopping_list_id>/lines", methods=["POST"])
@has_request_body(AddLineRequest)
def add_line(shopping_list_id: UUID):
    _Request: AddLineRequest = get_request_body()
    _Response = AddLineHandler(SqlAlchemyRepository()).handle(_Request, shopping_list_id)
    if _Response.list_not_found:
        return not_found("ShoppingList", shopping_list_id)
    if _Response.no_anchor:
        return business_rule_violation(
            "A line needs at least one of stock_item_id or product_id."
        )
    if _Response.item_not_found and _Request.stock_item_id is not None:
        return not_found("StockItem", _Request.stock_item_id)
    if _Response.product_not_found and _Request.product_id is not None:
        return not_found("Product", _Request.product_id)
    _LOGGER.info(
        f"Added line {_Response.line_id} to shopping list {shopping_list_id} "
        f"(stock_item={_Request.stock_item_id}, already_on_list={_Response.already_on_list})"
    )
    return ok({
        "line_id": _Response.line_id,
        "already_on_list": _Response.already_on_list,
    })


# ───── Price snapshot helpers ─────────────────────────────────────────────

def snapshot_offer_rrp(repository: SqlAlchemyRepository, line: ShoppingListLine) -> None:
    """Freeze the chosen offer's **was-price** onto a finished line.

    The RRP, and only the RRP (2026-09-17). Its twin below used to freeze the
    offer's *current* price too, which is what turned an advertised number into
    recorded spend; that stopped. This one survives because the two values
    answer different questions: `picked_offer_price` claimed "this is what you
    paid", while `list_price_at_pick` says "this is what it would have cost at
    full price" — context for a price the user *did* enter, not a substitute
    for one.

    So savings stay computable and keep meaning what they say: RRP minus what
    you actually paid, on lines where you said what you paid. A line finished
    with no price contributes no saving, the same way it now contributes no
    spend.
    """
    if line.selected_product_id is None or line.actual_unit_price is None:
        return
    offer: ProductOffer | None = repository.get(ProductOffer).one(
        EntityField(ProductOffer, "_product_id").eq(line.selected_product_id)
    )
    if offer is None or offer.price_was is None:
        return
    line.list_price_at_pick = float(offer.price_was)



# ───── Update line (tick, quantity, selected_product) ─────────────────────

class UpdateLineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quantity: int | None = Field(default=None, ge=1)
    is_ticked: bool | None = None
    selected_product_id: UUID | None = None
    # `None` for selected_product_id is ambiguous (clear vs unset). Use this
    # explicit flag to clear an existing selection.
    clear_selected_product: bool = False
    sequence: int | None = None
    # Purchase-memory overrides. Same clear-vs-unset story as the
    # selected_product fields: clients send the explicit clear_* flag to
    # blank a previously-recorded actual price/store, otherwise omitted
    # fields are left untouched.
    actual_unit_price: float | None = Field(default=None, ge=0)
    clear_actual_unit_price: bool = False
    purchased_store_id: UUID | None = None
    clear_purchased_store: bool = False
    # Where the user *plans* to buy this line, set from the plan face. Not a
    # purchase record — it never feeds a price observation, which is why it is
    # absent from `observation_fields_touched` below.
    planned_store_id: UUID | None = None
    clear_planned_store: bool = False
    # optional PreferredBuy hint on the line (clear-vs-unset flag).
    preferred_buy_id: UUID | None = None
    clear_preferred_buy: bool = False
    # "Add back" from the Deferred-to-fit-budget section flips
    # this to False; the reason chip is cleared alongside it. Only ever
    # sent as False from the SPA (deferral itself goes through the
    # dedicated trim-to-budget endpoint, not this PATCH).
    deferred_by_budget: bool | None = None


@dataclass(slots=True)
class UpdateLineResponse:
    line_not_found: bool = False


class UpdateLineHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(
        self,
        request: UpdateLineRequest,
        shopping_list_id: UUID,
        line_id: UUID,
    ) -> UpdateLineResponse:
        line: ShoppingListLine | None = self.repository.get(ShoppingListLine).by_id(line_id)
        # Path params arrive as str; the entity's FK is a UUID. Compare as
        # strings so the parent-ownership guard doesn't always mismatch.
        if line is None or str(line.shopping_list_id) != str(shopping_list_id):
            return UpdateLineResponse(line_not_found=True)

        set_fields = request.model_fields_set
        # Track whether the user is editing substantive fields — qty or
        # selected_product. If so, an auto_ provenance flips back to
        # "manual" (the user has taken ownership of the line). Ticking
        # alone doesn't count: it's a shopping-mode action, not editing.
        user_edited = False
        if "quantity" in set_fields:
            line.quantity = request.quantity
            user_edited = True
        if "is_ticked" in set_fields and request.is_ticked is not None:
            # Ticking is "I put it in the trolley" and nothing more. It does
            # not record a price: an offer's price is the shop's claim, not
            # the user's, and since 2026-09-17 nothing writes one on their
            # behalf (see `ShoppingListLine.picked_offer_price`).
            line.is_ticked = request.is_ticked
        if "sequence" in set_fields and request.sequence is not None:
            line.sequence = request.sequence
        if request.clear_selected_product:
            line.selected_product_id = None
            # Snapshot belongs to the (now-cleared) selection; clear it
            # so totals fall back to "no priced intent" instead of
            # showing a stale price for an offer the user no longer
            # picked.
            line.picked_offer_price = None
            line.list_price_at_pick = None
            user_edited = True
        elif "selected_product_id" in set_fields and request.selected_product_id is not None:
            line.selected_product_id = request.selected_product_id
            # No price snapshot. Choosing an offer says *which* product you
            # mean; it prices the line's estimate (the ladder's offer rung) but
            # does not say what you paid.
            #
            # It does say where you'll buy it (owner, 2026-09-27: picking an
            # offer "should overwrite the selected store for the shopping
            # row"). Un-picking leaves the store alone; there is nothing to
            # restore it to that is truer than what is there.
            product: Product | None = self.repository.get(Product).include(Product.Fields.STORE).by_id(
                request.selected_product_id
            )
            if product is not None:
                line.planned_store_id = product.store.id
            user_edited = True

        # actual paid price / store. Editing these doesn't clear
        # is_auto_added: they're a shopping-mode capture, not a
        # re-curation of how the line came to be on the list.
        if request.clear_actual_unit_price:
            line.actual_unit_price = None
        elif "actual_unit_price" in set_fields and request.actual_unit_price is not None:
            line.actual_unit_price = float(request.actual_unit_price)
        if request.clear_purchased_store:
            line.purchased_store_id = None
        elif "purchased_store_id" in set_fields and request.purchased_store_id is not None:
            line.purchased_store_id = request.purchased_store_id
        if request.clear_planned_store:
            line.planned_store_id = None
        elif "planned_store_id" in set_fields and request.planned_store_id is not None:
            line.planned_store_id = request.planned_store_id

        # preferred-buy hint (a reminder; doesn't flip provenance).
        if request.clear_preferred_buy:
            line.preferred_buy_id = None
        elif "preferred_buy_id" in set_fields and request.preferred_buy_id is not None:
            line.preferred_buy_id = request.preferred_buy_id

        # "Add back" clears both the deferred flag and the frozen
        # reason chip in lock-step; the two fields are always coherent.
        if "deferred_by_budget" in set_fields and request.deferred_by_budget is False:
            line.deferred_by_budget = False
            line.deferred_reason = None

        if user_edited and line.is_auto_added:
            line.is_auto_added = False

        # FU-726 — amending a *finished* list (the receipt face) edits the very
        # fields the harvested price observation was built from. The FK is
        # provenance, not a sync link (LC-4), so nothing corrects it on our
        # behalf: without this, a typo'd $110.00 fixed on the receipt would keep
        # feeding the money ladder's historic rung — and therefore every future
        # estimate for that item — forever. Only the observation-shaping fields
        # trigger it, and only once the list is done: before that no observation
        # exists yet and /finish will build it from the final values anyway.
        observation_fields_touched = bool(
            {"actual_unit_price", "purchased_store_id", "quantity"} & set(set_fields)
            or request.clear_actual_unit_price
            or request.clear_purchased_store
        )
        if observation_fields_touched:
            parent: ShoppingList | None = self.repository.get(ShoppingList).by_id(
                line.shopping_list_id
            )
            if (
                parent is not None
                and parent.status == SHOPPING_LIST_STATUS_DONE
                # Only bought lines ever produced an observation, so only bought
                # lines get one corrected — pricing something you didn't buy
                # must not invent purchase history.
                and line.is_ticked
            ):
                sync_line_observations(
                    self.repository, [line], overwrite_existing=True
                )

        self.repository.save_changes()
        return UpdateLineResponse()


@SHOPPING_LIST_ROUTER.route("/<uuid:shopping_list_id>/lines/<uuid:line_id>", methods=["PATCH"])
@has_request_body(UpdateLineRequest)
def update_line(shopping_list_id: UUID, line_id: UUID):
    _Request: UpdateLineRequest = get_request_body()
    _Response = UpdateLineHandler(SqlAlchemyRepository()).handle(_Request, shopping_list_id, line_id)
    if _Response.line_not_found:
        return not_found("ShoppingListLine", line_id)
    _LOGGER.debug(f"Updated line {line_id} on list {shopping_list_id}")
    return no_content()


# ───── Delete line ────────────────────────────────────────────────────────

@dataclass(slots=True)
class DeleteLineResponse:
    line_not_found: bool = False


def _remove_nested_product_lines(
    repository: Repository, shopping_list_id: UUID, stock_item_id: UUID,
) -> None:
    """Removing a stock-item line also removes the product-only lines on the
    same list whose product is linked to that item (Cart Button rule 3): a
    "nested product line" has `product_id` set and no `stock_item_id`."""
    stock_item = (
        repository.get(StockItem)
        .include(StockItem.Fields.PRODUCTS)
        .by_id(stock_item_id)
    )
    product_ids = [p.id for p in (stock_item.products or [])] if stock_item else []
    if not product_ids:
        return
    nested = repository.get(ShoppingListLine).all(
        EntityField(ShoppingListLine, "shopping_list_id").eq(shopping_list_id)
        & EntityField(ShoppingListLine, "stock_item_id").is_null()
        & EntityField(ShoppingListLine, "product_id").in_(product_ids)
    )
    for child in nested:
        repository.remove(child)


class DeleteLineHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, shopping_list_id: UUID, line_id: UUID) -> DeleteLineResponse:
        line: ShoppingListLine | None = self.repository.get(ShoppingListLine).by_id(line_id)
        # Path params arrive as str; the entity's FK is a UUID. Compare as
        # strings so the parent-ownership guard doesn't always mismatch.
        if line is None or str(line.shopping_list_id) != str(shopping_list_id):
            return DeleteLineResponse(line_not_found=True)
        if line.stock_item_id is not None and line.product_id is None:
            _remove_nested_product_lines(self.repository, line.shopping_list_id, line.stock_item_id)
        self.repository.remove(line)
        self.repository.save_changes()
        return DeleteLineResponse()


@SHOPPING_LIST_ROUTER.route("/<uuid:shopping_list_id>/lines/<uuid:line_id>", methods=["DELETE"])
def delete_line(shopping_list_id: UUID, line_id: UUID):
    _Response = DeleteLineHandler(SqlAlchemyRepository()).handle(shopping_list_id, line_id)
    if _Response.line_not_found:
        return not_found("ShoppingListLine", line_id)
    _LOGGER.info(f"Deleted line {line_id} from list {shopping_list_id}")
    return no_content()


# ───── Remove by stock-item (cart-button quick-remove path) ──────────────

@dataclass(slots=True)
class RemoveByStockItemResponse:
    list_not_found: bool = False
    removed: bool = False


class RemoveLineByStockItemHandler:
    """Used by the stock overview's cart button when the user clicks on an
    already-listed item — we don't carry the line_id around, just the
    stock_item_id. Idempotent: removing an item that isn't on the list
    is a no-op (still 204) so the client doesn't have to special-case the
    race where another tab already removed it.
    """

    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(
        self, shopping_list_id: UUID, stock_item_id: UUID, *, commit: bool = True,
    ) -> RemoveByStockItemResponse:
        """`commit=False` leaves the save to a bulk caller (one commit per
        request, FU-713)."""
        lst: ShoppingList | None = self.repository.get(ShoppingList).by_id(shopping_list_id)
        if lst is None:
            return RemoveByStockItemResponse(list_not_found=True)

        existing = self.repository.get(ShoppingListLine).one(
            EntityField(ShoppingListLine, "shopping_list_id").eq(shopping_list_id)
            & EntityField(ShoppingListLine, "stock_item_id").eq(stock_item_id)
        )
        if existing is not None:
            _remove_nested_product_lines(self.repository, shopping_list_id, stock_item_id)
            self.repository.remove(existing)
            if commit:
                self.repository.save_changes()
            return RemoveByStockItemResponse(removed=True)
        return RemoveByStockItemResponse()


@SHOPPING_LIST_ROUTER.route(
    "/<uuid:shopping_list_id>/lines/by-stock-item/<uuid:stock_item_id>", methods=["DELETE"]
)
def remove_line_by_stock_item(shopping_list_id: UUID, stock_item_id: UUID):
    _Response = RemoveLineByStockItemHandler(SqlAlchemyRepository()).handle(
        shopping_list_id, stock_item_id,
    )
    if _Response.list_not_found:
        return not_found("ShoppingList", shopping_list_id)
    _LOGGER.info(
        f"Cart-remove on list {shopping_list_id} for item {stock_item_id}: "
        f"removed={_Response.removed}"
    )
    # FU-573: report whether a line was actually removed (vs the idempotent
    # no-op when the item wasn't on the list) so a "remove from all lists"
    # fan-out can count real removals rather than every 2xx response.
    return ok({"removed": _Response.removed})


# ───── Quick-add to the inferred draft target ─────────────────────────────

class QuickAddRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stock_item_id: UUID
    # If the client has resolved the ambiguous (2+ drafts) case — e.g. via the
    # sessionStorage pick — it sends the chosen list here. The server still
    # validates that it's a draft.
    shopping_list_id: UUID | None = None


@dataclass(slots=True)
class QuickAddResponse:
    # Discriminator on `result`: "added" | "no_draft" | "ambiguous" |
    # "item_not_found" | "hint_invalid".
    result: str = "added"
    line_id: UUID | None = None
    shopping_list_id: UUID | None = None
    already_on_list: bool = False
    candidates: list[QuickAddTargetCandidate] | None = None


class QuickAddToDraftHandler:
    """Resolves the quick-add target by DRAFT-count inference (Chunk 2) and
    adds a line. The client may pass `shopping_list_id` to resolve the
    ambiguous (2+ drafts) case; sessionStorage on the client remembers the
    pick for the rest of the tab session.
    """

    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: QuickAddRequest) -> QuickAddResponse:
        item: StockItem | None = self.repository.get(StockItem).by_id(request.stock_item_id)
        if item is None:
            return QuickAddResponse(result="item_not_found")

        target: ShoppingList | None
        if request.shopping_list_id is not None:
            target = self.repository.get(ShoppingList).by_id(request.shopping_list_id)
            if target is None or target.status != SHOPPING_LIST_STATUS_DRAFT:
                return QuickAddResponse(result="hint_invalid")
        else:
            active_lists = self.repository.get(ShoppingList).all(
                EntityField(ShoppingList, ShoppingList.Fields.STATUS).ne(SHOPPING_LIST_STATUS_DONE)
            )
            outcome = resolve_quick_add_target(active_lists)
            if outcome.kind == "none":
                return QuickAddResponse(result="no_draft")
            if outcome.kind == "ambiguous":
                return QuickAddResponse(result="ambiguous", candidates=outcome.candidates)
            target = next(
                (l for l in active_lists if l.id == outcome.target_list_id), None
            )
            if target is None:  # defensive; resolver guarantees this id is in `lists`
                return QuickAddResponse(result="no_draft")

        # One dedupe, one construction: `AddLineHandler` owns both. This used
        # to re-implement them — without the `product_id is None` guard, so a
        # product line nested under the item counted as "already on the list"
        # (finalisation 03-R5).
        added = AddLineHandler(self.repository).handle(
            AddLineRequest(stock_item_id=request.stock_item_id), target.id,
        )
        if added.item_not_found:
            return QuickAddResponse(result="item_not_found")
        return QuickAddResponse(
            result="added",
            line_id=added.line_id,
            shopping_list_id=target.id,
            already_on_list=added.already_on_list,
        )


@SHOPPING_LIST_ROUTER.route("/quick-add/lines", methods=["POST"])
@has_request_body(QuickAddRequest)
def quick_add_to_draft():
    _Request: QuickAddRequest = get_request_body()
    _Response = QuickAddToDraftHandler(SqlAlchemyRepository()).handle(_Request)
    if _Response.result == "item_not_found":
        return not_found("StockItem", _Request.stock_item_id)
    if _Response.result == "hint_invalid":
        return business_rule_violation(
            "The chosen shopping list is not a draft."
        )
    if _Response.result == "no_draft":
        # Not a 404 — there may be SHOPPING/DONE lists, just no draft. The
        # client surfaces a "create a list?" prompt.
        return ok({"result": "no_draft"})
    if _Response.result == "ambiguous":
        return ok({
            "result": "ambiguous",
            "candidates": [
                {"shopping_list_id": c.shopping_list_id, "name": c.name}
                for c in (_Response.candidates or [])
            ],
        })
    _LOGGER.info(
        f"Quick-added stock item {_Request.stock_item_id} to list "
        f"{_Response.shopping_list_id} (already_on_list={_Response.already_on_list})"
    )
    return ok({
        "result": "added",
        "shopping_list_id": _Response.shopping_list_id,
        "line_id": _Response.line_id,
        "already_on_list": _Response.already_on_list,
    })
