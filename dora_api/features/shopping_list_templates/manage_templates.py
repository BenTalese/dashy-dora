"""CRUD + instantiate + snapshot for ShoppingListTemplate.

Templates are small and the endpoints share the same imports, so they
live together in one file. Endpoints:

  GET    /api/shopping-list-templates             — list summaries
  GET    /api/shopping-list-templates/<id>        — full detail with lines
  POST   /api/shopping-list-templates             — create (optionally with lines)
  PATCH  /api/shopping-list-templates/<id>        — rename
  PATCH  /api/shopping-list-templates/<id>/lines/<line_id> (quantity, offer, preferred buy)
  DELETE /api/shopping-list-templates/<id>
  POST   /api/shopping-list-templates/<id>/lines  — add a line
  DELETE /api/shopping-list-templates/<id>/lines/<line_id>
  POST   /api/shopping-list-templates/<id>/instantiate     — create a shopping list from this template
  POST   /api/shopping-list-templates/from-list/<list_id>  — snapshot a list as a new template
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from dora_api.app import db
from dora_api.domain.entities.preferred_buy import PreferredBuy
from dora_api.domain.entities.product import Product
from dora_api.domain.entities.shopping_list import (ShoppingList, format_list_date,
                                                    ShoppingListLine)
from dora_api.domain.entities.shopping_list_template import (
    ShoppingListTemplate, ShoppingListTemplateLine,
)
from dora_api.domain.entities.stock_item import StockItem
from dora_api.features.app_settings.clock import household_today
from dora_api.features.routers import SHOPPING_LIST_TEMPLATE_ROUTER
from dora_api.features.shopping_lists._line_defaults import apply_line_defaults
from dora_api.features.shopping_lists.get_shopping_list_detail import (
    LinePreferredBuyDto, LineProductOfferDto, build_line_offers,
)
from dora_api.infrastructure.api_response import (business_rule_violation,
                                                  created,
                                                  entity_existence_failures,
                                                  no_content, not_found, ok)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.uuid_key import uuid_key
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


# ───── DTOs ──────────────────────────────────────────────────────────────

def _line_quantity(template_quantity: int | None) -> int:
    """A template line may carry 0 (the editor's "none yet"); a list line
    needs at least 1 (`CreateLineRequest.quantity` is `ge=1`)."""
    return max(1, template_quantity or 1)


@dataclass(frozen=True, slots=True)
class TemplateLineDto:
    line_id: UUID
    stock_item_id: UUID
    stock_item_name: str
    quantity: int | None
    sequence: int
    selected_product_id: UUID | None
    preferred_buy_id: UUID | None
    # The same choices the list row's picker offers (`ShoppingListLineDto`).
    offers: List[LineProductOfferDto] = field(default_factory=list)
    preferred_buys: List[LinePreferredBuyDto] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class TemplateSummaryDto:
    template_id: UUID
    name: str
    created_at: datetime
    updated_at: datetime
    line_count: int


@dataclass(frozen=True, slots=True)
class TemplateDetailDto:
    template_id: UUID
    name: str
    created_at: datetime
    updated_at: datetime
    lines: List[TemplateLineDto] = field(default_factory=list)


# ───── List summaries ────────────────────────────────────────────────────

class GetTemplatesHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self) -> List[TemplateSummaryDto]:
        templates: List[ShoppingListTemplate] = self.repository.get(ShoppingListTemplate).all()
        if not templates:
            return []
        # R-005 carve-out: a grouped count the repository has no port for.
        table = db.metadata.tables["ShoppingListTemplateLine"]
        counts = {
            uuid_key(template_id): int(n)
            for template_id, n in db.session.execute(
                select(table.c.template_id, func.count()).group_by(table.c.template_id)
            ).all()
        }
        summaries = [
            TemplateSummaryDto(
                template_id = t.id,
                name = t.name,
                created_at = t.created_at,
                updated_at = t.updated_at,
                line_count = counts.get(uuid_key(t.id), 0),
            )
            for t in templates
        ]
        # Recently-updated first — the template you tweaked today is the
        # one you probably want to grab next.
        summaries.sort(key=lambda s: s.updated_at, reverse=True)
        return summaries


@SHOPPING_LIST_TEMPLATE_ROUTER.route("", methods=["GET"])
def get_templates():
    _Result = GetTemplatesHandler(SqlAlchemyRepository()).handle()
    _LOGGER.debug("Returned %d template summaries", len(_Result))
    return ok(_Result)


# ───── Get detail ────────────────────────────────────────────────────────

class GetTemplateDetailHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, template_id: UUID) -> TemplateDetailDto | None:
        template: ShoppingListTemplate | None = self.repository.get(ShoppingListTemplate).by_id(template_id)
        if template is None:
            return None
        lines: List[ShoppingListTemplateLine] = self.repository.get(ShoppingListTemplateLine).all(
            EntityField(ShoppingListTemplateLine, "template_id").eq(template_id)
        )
        lines.sort(key=lambda l: (l.sequence, l.id))

        # Resolve stock items, their offers and preferred buys in one batch
        # each so we don't N+1.
        stock_item_ids = list({l.stock_item_id for l in lines})
        items: dict[UUID, StockItem] = {}
        preferred_buys: dict[UUID, List[PreferredBuy]] = {}
        if stock_item_ids:
            items = {
                i.id: i for i in self.repository.get(StockItem)
                .include("products")
                    .then_include("store")
                .include("products")
                    .then_include("current_offer")
                .all(EntityField(StockItem, "id").in_(stock_item_ids))
            }
            for pb in self.repository.get(PreferredBuy).all(
                EntityField(PreferredBuy, PreferredBuy.Fields.STOCK_ITEM_ID).in_(stock_item_ids)
            ):
                preferred_buys.setdefault(pb.stock_item_id, []).append(pb)

        line_dtos = [
            TemplateLineDto(
                line_id = l.id,
                stock_item_id = l.stock_item_id,
                stock_item_name = items[l.stock_item_id].name
                    if l.stock_item_id in items else "(missing item)",
                quantity = l.quantity,
                sequence = l.sequence,
                selected_product_id = l.selected_product_id,
                preferred_buy_id = l.preferred_buy_id,
                offers = build_line_offers(items.get(l.stock_item_id), l.selected_product_id),
                preferred_buys = sorted(
                    (
                        LinePreferredBuyDto(preferred_buy_id = pb.id, label = pb.label)
                        for pb in preferred_buys.get(l.stock_item_id, [])
                    ),
                    key=lambda d: d.label.lower(),
                ),
            )
            for l in lines
        ]
        return TemplateDetailDto(
            template_id = template.id,
            name = template.name,
            created_at = template.created_at,
            updated_at = template.updated_at,
            lines = line_dtos,
        )


@SHOPPING_LIST_TEMPLATE_ROUTER.route("/<uuid:template_id>", methods=["GET"])
def get_template_detail(template_id: UUID):
    _Result = GetTemplateDetailHandler(SqlAlchemyRepository()).handle(template_id)
    if _Result is None:
        return not_found("ShoppingListTemplate", template_id)
    return ok(_Result)


# ───── Create template ───────────────────────────────────────────────────

class CreateTemplateLineInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stock_item_id: UUID
    # The editor's stepper goes down to 0 ("no quantity yet"); a template
    # line instantiates into a list line, which clamps to >= 1 (`_line_quantity`).
    quantity: int | None = Field(default=1, ge=0)


class CreateTemplateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    lines: List[CreateTemplateLineInput] = Field(default_factory=list)


@dataclass(slots=True)
class CreateTemplateResponse:
    template_id: UUID | None = None
    missing_stock_item_ids: tuple[UUID, ...] = ()


class CreateTemplateHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: CreateTemplateRequest) -> CreateTemplateResponse:
        requested_ids = list(dict.fromkeys(line.stock_item_id for line in request.lines))
        found_ids = {
            str(item.id) for item in self.repository.get(StockItem).all(
                EntityField(StockItem, "id").in_(requested_ids)
            )
        } if requested_ids else set()
        missing = tuple(i for i in requested_ids if str(i) not in found_ids)
        if missing:
            return CreateTemplateResponse(missing_stock_item_ids=missing)

        now = datetime.now(timezone.utc)
        template = ShoppingListTemplate(
            name = request.name.strip(),
            created_at = now,
            updated_at = now,
        )
        self.repository.add(template)

        # Lines added in submission order — sequence reflects that order so
        # downstream rendering and instantiation preserve intent. Same
        # unique-per-item rule as AddTemplateLine: a repeated item folds into
        # its first occurrence.
        seen: set[UUID] = set()
        for line in request.lines:
            if line.stock_item_id in seen:
                continue
            seen.add(line.stock_item_id)
            self.repository.add(ShoppingListTemplateLine(
                template_id = template.id,
                stock_item_id = line.stock_item_id,
                quantity = line.quantity,
                sequence = len(seen) - 1,
            ))
        # FU-512 unit-of-work: one commit at the end.
        self.repository.save_changes()
        return CreateTemplateResponse(template_id=template.id)


@SHOPPING_LIST_TEMPLATE_ROUTER.route("", methods=["POST"])
@has_request_body(CreateTemplateRequest)
def create_template():
    _Request: CreateTemplateRequest = get_request_body()
    _Response = CreateTemplateHandler(SqlAlchemyRepository()).handle(_Request)
    if _Response.missing_stock_item_ids:
        return entity_existence_failures(
            StockItem.__name__, "lines", *_Response.missing_stock_item_ids,
        )
    _LOGGER.info(
        f"Created template {_Response.template_id} '{_Request.name}' with {len(_Request.lines)} line(s)"
    )
    return created(
        _Response.template_id,
        f"{SHOPPING_LIST_TEMPLATE_ROUTER.name}.{get_templates.__name__}",
        "template_id",
        body={"template_id": _Response.template_id},
    )


# ───── Update template (rename) ──────────────────────────────────────────

class UpdateTemplateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=255)


@dataclass(slots=True)
class UpdateTemplateResponse:
    not_found: bool = False


class UpdateTemplateHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: UpdateTemplateRequest, template_id: UUID) -> UpdateTemplateResponse:
        template: ShoppingListTemplate | None = self.repository.get(ShoppingListTemplate).by_id(template_id)
        if template is None:
            return UpdateTemplateResponse(not_found=True)
        if "name" in request.model_fields_set and request.name is not None:
            template.name = request.name.strip()
        template.updated_at = datetime.now(timezone.utc)
        self.repository.save_changes()
        return UpdateTemplateResponse()


@SHOPPING_LIST_TEMPLATE_ROUTER.route("/<uuid:template_id>", methods=["PATCH"])
@has_request_body(UpdateTemplateRequest)
def update_template(template_id: UUID):
    _Request: UpdateTemplateRequest = get_request_body()
    _Response = UpdateTemplateHandler(SqlAlchemyRepository()).handle(_Request, template_id)
    if _Response.not_found:
        return not_found("ShoppingListTemplate", template_id)
    _LOGGER.info(f"Updated template {template_id}")
    return no_content()


# ───── Delete template ───────────────────────────────────────────────────

@dataclass(slots=True)
class DeleteTemplateResponse:
    not_found: bool = False


class DeleteTemplateHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, template_id: UUID) -> DeleteTemplateResponse:
        template: ShoppingListTemplate | None = self.repository.get(ShoppingListTemplate).by_id(template_id)
        if template is None:
            return DeleteTemplateResponse(not_found=True)
        self.repository.remove(template)
        self.repository.save_changes()
        return DeleteTemplateResponse()


@SHOPPING_LIST_TEMPLATE_ROUTER.route("/<uuid:template_id>", methods=["DELETE"])
def delete_template(template_id: UUID):
    _Response = DeleteTemplateHandler(SqlAlchemyRepository()).handle(template_id)
    if _Response.not_found:
        return not_found("ShoppingListTemplate", template_id)
    _LOGGER.info(f"Deleted template {template_id}")
    return no_content()


# ───── Add line to template ──────────────────────────────────────────────

class AddTemplateLineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stock_item_id: UUID
    quantity: int | None = Field(default=1, ge=0)


@dataclass(slots=True)
class AddTemplateLineResponse:
    line_id: UUID | None = None
    template_not_found: bool = False
    item_not_found: bool = False
    already_on_template: bool = False


class AddTemplateLineHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: AddTemplateLineRequest, template_id: UUID) -> AddTemplateLineResponse:
        template: ShoppingListTemplate | None = self.repository.get(ShoppingListTemplate).by_id(template_id)
        if template is None:
            return AddTemplateLineResponse(template_not_found=True)
        item: StockItem | None = self.repository.get(StockItem).by_id(request.stock_item_id)
        if item is None:
            return AddTemplateLineResponse(item_not_found=True)

        # Same unique-per-item rule as ShoppingList: adding twice folds.
        existing = self.repository.get(ShoppingListTemplateLine).one(
            EntityField(ShoppingListTemplateLine, "template_id").eq(template_id)
            & EntityField(ShoppingListTemplateLine, "stock_item_id").eq(request.stock_item_id)
        )
        if existing is not None:
            return AddTemplateLineResponse(line_id=existing.id, already_on_template=True)

        siblings = self.repository.get(ShoppingListTemplateLine).all(
            EntityField(ShoppingListTemplateLine, "template_id").eq(template_id)
        )
        next_sequence = (max((l.sequence for l in siblings), default=-1)) + 1
        line = ShoppingListTemplateLine(
            template_id = template_id,
            stock_item_id = request.stock_item_id,
            quantity = request.quantity,
            sequence = next_sequence,
        )
        self.repository.add(line)
        template.updated_at = datetime.now(timezone.utc)
        self.repository.save_changes()
        return AddTemplateLineResponse(line_id=line.id)


@SHOPPING_LIST_TEMPLATE_ROUTER.route("/<uuid:template_id>/lines", methods=["POST"])
@has_request_body(AddTemplateLineRequest)
def add_template_line(template_id: UUID):
    _Request: AddTemplateLineRequest = get_request_body()
    _Response = AddTemplateLineHandler(SqlAlchemyRepository()).handle(_Request, template_id)
    if _Response.template_not_found:
        return not_found("ShoppingListTemplate", template_id)
    if _Response.item_not_found:
        return not_found("StockItem", _Request.stock_item_id)
    _LOGGER.info(
        f"Added template line {_Response.line_id} to {template_id} "
        f"(already_on_template={_Response.already_on_template})"
    )
    return ok({"line_id": _Response.line_id, "already_on_template": _Response.already_on_template})


# ───── Delete line ───────────────────────────────────────────────────────

@dataclass(slots=True)
class DeleteTemplateLineResponse:
    not_found: bool = False


class DeleteTemplateLineHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, template_id: UUID, line_id: UUID) -> DeleteTemplateLineResponse:
        line: ShoppingListTemplateLine | None = self.repository.get(ShoppingListTemplateLine).by_id(line_id)
        if line is None or line.template_id != template_id:
            return DeleteTemplateLineResponse(not_found=True)
        self.repository.remove(line)

        template: ShoppingListTemplate | None = self.repository.get(ShoppingListTemplate).by_id(template_id)
        if template is not None:
            template.updated_at = datetime.now(timezone.utc)
        self.repository.save_changes()
        return DeleteTemplateLineResponse()


@SHOPPING_LIST_TEMPLATE_ROUTER.route("/<uuid:template_id>/lines/<uuid:line_id>", methods=["DELETE"])
def delete_template_line(template_id: UUID, line_id: UUID):
    _Response = DeleteTemplateLineHandler(SqlAlchemyRepository()).handle(template_id, line_id)
    if _Response.not_found:
        return not_found("ShoppingListTemplateLine", line_id)
    _LOGGER.info(f"Deleted template line {line_id} from template {template_id}")
    return no_content()


# ───── Update template line (quantity, offer, preferred buy) ─────────────

class UpdateTemplateLineRequest(BaseModel):
    """Omitted fields are left alone; an explicit null clears."""
    model_config = ConfigDict(extra="forbid")
    quantity: int | None = Field(default=None, ge=0)
    selected_product_id: UUID | None = None
    preferred_buy_id: UUID | None = None


@dataclass(slots=True)
class UpdateTemplateLineResponse:
    not_found: bool = False
    invalid_choice: str | None = None


class UpdateTemplateLineHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(
        self,
        request: UpdateTemplateLineRequest,
        template_id: UUID,
        line_id: UUID,
    ) -> UpdateTemplateLineResponse:
        line: ShoppingListTemplateLine | None = self.repository.get(ShoppingListTemplateLine).by_id(line_id)
        if line is None or line.template_id != template_id:
            return UpdateTemplateLineResponse(not_found=True)
        set_fields = request.model_fields_set
        if "quantity" in set_fields:
            line.quantity = request.quantity
        if "selected_product_id" in set_fields:
            if request.selected_product_id is not None:
                item: StockItem | None = self.repository.get(StockItem).include("products").by_id(
                    line.stock_item_id
                )
                linked = {str(p.id) for p in (item.products if item else None) or []}
                if str(request.selected_product_id) not in linked:
                    return UpdateTemplateLineResponse(
                        invalid_choice="That product isn't linked to this item.",
                    )
            line.selected_product_id = request.selected_product_id
        if "preferred_buy_id" in set_fields:
            if request.preferred_buy_id is not None:
                pb: PreferredBuy | None = self.repository.get(PreferredBuy).by_id(request.preferred_buy_id)
                if pb is None or str(pb.stock_item_id) != str(line.stock_item_id):
                    return UpdateTemplateLineResponse(
                        invalid_choice="That preferred buy isn't one of this item's.",
                    )
            line.preferred_buy_id = request.preferred_buy_id

        # Bump the template's updated_at so summaries sort sensibly.
        template: ShoppingListTemplate | None = self.repository.get(ShoppingListTemplate).by_id(template_id)
        if template is not None:
            template.updated_at = datetime.now(timezone.utc)
        self.repository.save_changes()
        return UpdateTemplateLineResponse()


@SHOPPING_LIST_TEMPLATE_ROUTER.route("/<uuid:template_id>/lines/<uuid:line_id>", methods=["PATCH"])
@has_request_body(UpdateTemplateLineRequest)
def update_template_line(template_id: UUID, line_id: UUID):
    _Request: UpdateTemplateLineRequest = get_request_body()
    _Response = UpdateTemplateLineHandler(SqlAlchemyRepository()).handle(
        _Request, template_id, line_id,
    )
    if _Response.not_found:
        return not_found("ShoppingListTemplateLine", line_id)
    if _Response.invalid_choice:
        return business_rule_violation(_Response.invalid_choice)
    _LOGGER.debug(f"Updated template line {line_id} on template {template_id}")
    return no_content()


# ───── Instantiate template → new shopping list ──────────────────────────

class InstantiateTemplateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Optional name override; if absent, defaults to "<template_name> · <today>".
    name: str | None = None
    # Top up this existing list instead of creating one (`name` is then
    # ignored). Items already on it are skipped, like any other add.
    merge_into_list_id: UUID | None = None


@dataclass(slots=True)
class InstantiateTemplateResponse:
    new_shopping_list_id: UUID | None = None
    not_found: bool = False
    target_not_found: bool = False
    target_done: bool = False
    line_count: int = 0
    skipped_count: int = 0


class InstantiateTemplateHandler:
    """Creates a new ShoppingList from the template's lines.

    Stock items that have since been deleted are silently skipped (we'd
    otherwise blow up creating a line pointing at a missing FK). A line's
    picked offer and preferred buy carry over while they still apply to the
    item: the offer's product is still linked, the preferred buy still
    exists. A carried offer also sets the line's planned store, as picking
    one on the list does. Anything left unset gets the usual new-line
    defaults (`apply_line_defaults`).
    """

    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: InstantiateTemplateRequest, template_id: UUID) -> InstantiateTemplateResponse:
        template: ShoppingListTemplate | None = self.repository.get(ShoppingListTemplate).by_id(template_id)
        if template is None:
            return InstantiateTemplateResponse(not_found=True)

        now = datetime.now(timezone.utc)
        on_list: set[UUID] = set()
        next_sequence = 0
        if request.merge_into_list_id is not None:
            target = self.repository.get(ShoppingList).by_id(request.merge_into_list_id)
            if target is None:
                return InstantiateTemplateResponse(target_not_found=True)
            if target.is_done:
                return InstantiateTemplateResponse(target_done=True)
            existing = self.repository.get(ShoppingListLine).all(
                EntityField(ShoppingListLine, "shopping_list_id").eq(target.id)
            )
            # The same "already on the list" rule as `AddLineHandler`: a
            # plain stock-item line, not a product nested under one.
            on_list = {l.stock_item_id for l in existing if l.stock_item_id and l.product_id is None}
            next_sequence = max((l.sequence for l in existing), default=-1) + 1
        else:
            # Household date through `format_list_date` (R-021 / R-056) — this
            # was a server-local `strftime`, a second copy of that format
            # (finalisation 03-R8).
            today = household_today(self.repository)
            name = (request.name or "").strip() or f"{template.name} · {format_list_date(today, today)}"
            target = ShoppingList(name=name, created_at=now)
            self.repository.add(target)

        template_lines: List[ShoppingListTemplateLine] = self.repository.get(ShoppingListTemplateLine).all(
            EntityField(ShoppingListTemplateLine, "template_id").eq(template_id)
        )
        template_lines.sort(key=lambda l: l.sequence)

        # Bulk-load the stock items (skipping orphans) with their linked
        # products, and the live preferred buys, so the carried choices can be
        # checked without a query per line.
        items: dict[UUID, StockItem] = {}
        live_preferred_buys: set[UUID] = set()
        if template_lines:
            item_ids = [l.stock_item_id for l in template_lines]
            items = {
                i.id: i for i in self.repository.get(StockItem)
                .include("products")
                .all(EntityField(StockItem, "id").in_(item_ids))
            }
            live_preferred_buys = {
                pb.id for pb in self.repository.get(PreferredBuy).all(
                    EntityField(PreferredBuy, PreferredBuy.Fields.STOCK_ITEM_ID).in_(item_ids)
                )
            }

        new_lines: List[ShoppingListLine] = []
        skipped = 0
        for tl in template_lines:
            item = items.get(tl.stock_item_id)
            if item is None:
                continue
            if tl.stock_item_id in on_list:
                skipped += 1
                continue
            offer: Product | None = next(
                (p for p in item.products or [] if p.id == tl.selected_product_id), None,
            )
            new_lines.append(ShoppingListLine(
                shopping_list_id = target.id,
                stock_item_id = tl.stock_item_id,
                quantity = _line_quantity(tl.quantity),
                sequence = next_sequence + len(new_lines),
                selected_product_id = offer.id if offer else None,
                # R-032 — the FK column, not the noload `store` relationship.
                planned_store_id = offer._store_id if offer else None,
                preferred_buy_id = (
                    tl.preferred_buy_id if tl.preferred_buy_id in live_preferred_buys else None
                ),
                added_at = now,
            ))
            # A template can hold the same item twice (legacy rows); the
            # second copy is "already on the list" like any other.
            on_list.add(tl.stock_item_id)
        apply_line_defaults(self.repository, new_lines)
        for line in new_lines:
            self.repository.add(line)
        added = len(new_lines)
        # FU-512 unit-of-work: single commit. A new list still persists even
        # when every template line points at a deleted stock item (added==0).
        self.repository.save_changes()
        return InstantiateTemplateResponse(
            new_shopping_list_id=target.id, line_count=added, skipped_count=skipped,
        )


@SHOPPING_LIST_TEMPLATE_ROUTER.route("/<uuid:template_id>/instantiate", methods=["POST"])
@has_request_body(InstantiateTemplateRequest)
def instantiate_template(template_id: UUID):
    _Request: InstantiateTemplateRequest = get_request_body()
    _Response = InstantiateTemplateHandler(SqlAlchemyRepository()).handle(_Request, template_id)
    if _Response.not_found:
        return not_found("ShoppingListTemplate", template_id)
    if _Response.target_not_found:
        return not_found("ShoppingList", _Request.merge_into_list_id)
    if _Response.target_done:
        return business_rule_violation("A finished list can't take more items.")
    _LOGGER.info(
        f"Instantiated template {template_id} -> list {_Response.new_shopping_list_id} "
        f"({_Response.line_count} lines, {_Response.skipped_count} already on it)"
    )
    return ok({
        "shopping_list_id": _Response.new_shopping_list_id,
        "line_count": _Response.line_count,
        "skipped_count": _Response.skipped_count,
    })


# ───── Snapshot existing list → new template ─────────────────────────────

class SnapshotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    # If True, every line on the source list ends up on the template.
    # If False (default), only unticked lines are saved — the assumption
    # is "this is what I usually need; the ticked items were one-offs".
    include_ticked: bool = False


@dataclass(slots=True)
class SnapshotResponse:
    template_id: UUID | None = None
    source_not_found: bool = False
    line_count: int = 0
    # Product-only source lines have no stock item and a template line is
    # item-anchored (NOT NULL), so they are skipped rather than 500-ing the
    # snapshot (finalisation 03-R2). Reported so the SPA can say so.
    skipped_product_lines: int = 0


class SnapshotFromListHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: SnapshotRequest, source_list_id: UUID) -> SnapshotResponse:
        source: ShoppingList | None = self.repository.get(ShoppingList).by_id(source_list_id)
        if source is None:
            return SnapshotResponse(source_not_found=True)

        now = datetime.now(timezone.utc)
        # `display_name`, not `name`: a self-labelled list has `name=None` and
        # the fallback read "Template from None" (finalisation 03-R2).
        template = ShoppingListTemplate(
            name = (request.name or "").strip() or f"Template from {source.display_name}",
            created_at = now,
            updated_at = now,
        )
        self.repository.add(template)

        source_lines: List[ShoppingListLine] = self.repository.get(ShoppingListLine).all(
            EntityField(ShoppingListLine, "shopping_list_id").eq(source_list_id)
        )
        if not request.include_ticked:
            source_lines = [l for l in source_lines if not l.is_ticked]
        source_lines.sort(key=lambda l: l.sequence)

        added = 0
        skipped_product_lines = 0
        templated_items: set[UUID] = set()
        for sl in source_lines:
            if sl.stock_item_id is None:
                skipped_product_lines += 1
                continue
            # An item can sit on a list as both a plain line and a nested
            # product line; a template holds one line per item.
            if sl.stock_item_id in templated_items:
                continue
            templated_items.add(sl.stock_item_id)
            self.repository.add(ShoppingListTemplateLine(
                template_id = template.id,
                stock_item_id = sl.stock_item_id,
                quantity = sl.quantity if sl.quantity is not None else 1,
                sequence = added,
                selected_product_id = sl.selected_product_id,
                preferred_buy_id = sl.preferred_buy_id,
            ))
            added += 1
        # FU-512 unit-of-work: single commit.
        self.repository.save_changes()
        return SnapshotResponse(
            template_id=template.id, line_count=added,
            skipped_product_lines=skipped_product_lines,
        )


@SHOPPING_LIST_TEMPLATE_ROUTER.route("/from-list/<uuid:source_list_id>", methods=["POST"])
@has_request_body(SnapshotRequest)
def snapshot_from_list(source_list_id: UUID):
    _Request: SnapshotRequest = get_request_body()
    _Response = SnapshotFromListHandler(SqlAlchemyRepository()).handle(_Request, source_list_id)
    if _Response.source_not_found:
        return not_found("ShoppingList", source_list_id)
    _LOGGER.info(
        f"Snapshotted list {source_list_id} -> template {_Response.template_id} "
        f"({_Response.line_count} lines)"
    )
    return ok({
        "template_id": _Response.template_id,
        "line_count": _Response.line_count,
        "skipped_product_lines": _Response.skipped_product_lines,
    })
