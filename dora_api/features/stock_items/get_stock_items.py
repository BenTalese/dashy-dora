import dataclasses
import logging
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from flask import request
from sqlalchemy import func, select

from dora_api.app import db
from dora_api.domain.entities.alert_preference import AlertPreference
from dora_api.domain.entities.app_setting import AppSetting
from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.stock_status import (effective_expiring_soon_window,
                                          is_low_stock, is_out_of_stock,
                                          needs_restock)
from dora_api.features.app_settings.clock import household_today
from dora_api.features.stock_items.stock_attention import (RANK_NONE,
                                                          resolve_attention_map)
from dora_api.features.routers import STOCK_ITEM_ROUTER
from dora_api.infrastructure.api_response import bad_request, paginated
from dora_api.infrastructure.query_options import (InvalidQueryParameter,
                                                   parse_query_options)
from dora_api.persistence.field import EntityField
from dora_api.persistence.page import Page
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository
from dora_api.infrastructure.session_user import current_user_id

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StockItemDto:
    name: str
    stock_item_id: UUID
    stock_level_id: UUID | None
    # Status keyed to the level's ordinal sequence, plus the server-owned
    # derived predicates — so the client never matches on a level name.
    stock_level_sequence: int | None
    is_out_of_stock: bool
    is_low_stock: bool
    needs_restock: bool
    stock_location_id: UUID | None
    stock_group_id: UUID | None
    stock_level_last_updated: datetime
    expiry_date: date | None
    is_essential: bool
    is_open: bool
    # Read by the detail page, which mirrors it from the store so an "opened"
    # set elsewhere shows without a refetch.
    opened_on: date | None
    # ── Server-owned attention (Chunk 3b) ──────────────────────────────
    # The one rule, evaluated for the requesting user: see
    # `stock_attention.py` for what it says and why it lives there. The
    # client renders these; it does not re-derive them (that duplication was
    # B1–B4). `attention_severity` is the worst firing kind's, and is what the
    # overview sorts on within the outlined band (D-9); None when nothing fires.
    needs_attention: bool = False
    attention_severity: str | None = None
    # Which conditions fired, so a client filter chip ("Expiring soon") can
    # narrow by one of them without re-deriving the threshold — the last
    # remaining hardcoded 7-day window on the client was exactly that chip.
    attention_kinds: tuple[str, ...] = ()
    # Urgency ORDER within the outlined band, most urgent first (0 expired,
    # 1 essential-out, 2 expiring-soon, 3 essential-low; 9 = nothing fired).
    # Severity can't do this job — expired and essential_low are both "high",
    # so the overview's sort fell through to alphabetical and read as random
    # (owner, 2026-08-21). See `stock_attention.py` for the full ordering.
    attention_rank: int = RANK_NONE
    # count of linked products. Drives the "2+ products →
    # combined choice modal" decision in `AddToListButton`. 0 = generic
    # stock-item line (no offer); 1 = preselect; 2+ = open QuickAddSheet
    # so the user picks the offer + (if relevant) the target list in one
    # combined surface instead of stacking two prompts.
    linked_product_count: int = 0

    @classmethod
    def from_entity(cls, stock_item: StockItem) -> 'StockItemDto':
        level = stock_item.stock_level
        return StockItemDto(
            name = stock_item.name,
            stock_item_id = stock_item.id,
            stock_level_id = level.id if level else None,
            stock_level_sequence = level.sequence if level else None,
            is_out_of_stock = is_out_of_stock(level),
            is_low_stock = is_low_stock(level),
            needs_restock = needs_restock(level),
            stock_location_id = stock_item.stock_location.id if stock_item.stock_location else None,
            stock_group_id = stock_item.stock_group.id if stock_item.stock_group else None,
            stock_level_last_updated = stock_item.stock_level_last_updated,
            expiry_date = stock_item.expiry_date,
            is_essential = bool(stock_item.is_essential),
            is_open = bool(stock_item.is_open),
            opened_on = stock_item.opened_on,
        )


_FIELD_MAP: dict[str, EntityField] = {
    "stock_item_id": EntityField(StockItem, "id"),
    "stock_level_id": EntityField(StockItem, "_stock_level_id"),
    "stock_location_id": EntityField(StockItem, "_stock_location_id"),
    "stock_group_id": EntityField(StockItem, "_stock_group_id"),
    "is_essential": EntityField(StockItem, StockItem.Fields.IS_ESSENTIAL),
    "is_open": EntityField(StockItem, StockItem.Fields.IS_OPEN),
}


class GetStockItemsHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def _base_query(self):
        return (
            self.repository
            .get(StockItem)
            .include(StockItem.Fields.STOCK_LEVEL)
            .include(StockItem.Fields.STOCK_LOCATION)
            .include(StockItem.Fields.STOCK_GROUP)
        )

    def _hydrate_attention(
        self, dtos: list[StockItemDto], entities: list[StockItem]
    ) -> list[StockItemDto]:
        """Stamp each DTO with the attention verdict. Bulk by construction —
        the window, today and the user's disabled kinds are resolved once for
        the whole page, not per row."""
        if not dtos:
            return dtos

        settings: list[AppSetting] = self.repository.get(AppSetting).all()
        window = effective_expiring_soon_window(settings[0] if settings else None)
        today = household_today(self.repository)
        attention = resolve_attention_map(
            entities,
            today=today,
            window_days=window,
            disabled_kinds=self._disabled_kinds(),
        )
        return [
            dataclasses.replace(
                d,
                needs_attention=attention[d.stock_item_id].needs_attention,
                attention_severity=attention[d.stock_item_id].severity,
                attention_kinds=attention[d.stock_item_id].kinds,
                attention_rank=attention[d.stock_item_id].rank,
            )
            for d in dtos
        ]

    def _disabled_kinds(self) -> frozenset[str]:
        """Kinds the requesting user has switched off. B2: the bell honoured
        these and the rows did not, so disabling a kind half-worked. One read
        per request, not per item."""
        user_id = current_user_id()
        if user_id is None:
            return frozenset()
        rows: list[AlertPreference] = self.repository.get(AlertPreference).all(
            EntityField(AlertPreference, AlertPreference.Fields.USER_ID).eq(user_id)
        )
        return frozenset(r.kind for r in rows if not r.enabled)

    def _hydrate_linked_product_count(
        self, dtos: list[StockItemDto]
    ) -> list[StockItemDto]:
        """C-7 Chunk 2 — bulk-count linked products per stock item.
        A single GROUP BY against the link table. R-005 carve-out: a grouped
        count over an association with no entity.

        FU-463 — built with the ORM `select()` (not raw `text()`) so
        SQLAlchemy adapts UUID bindings to whatever the column type uses
        on each engine. The original raw-SQL version silently never
        matched on SQLite because the string IDs in the IN clause didn't
        compare against the UUIDType column (see
        `project_sqlite_uuid_text_binding` memory + FU-171). Symptom was
        `linked_product_count=0` on every DTO on SQLite deployments,
        regardless of link-table contents.
        """
        if not dtos:
            return dtos

        link_table = db.metadata.tables["StockItemProduct"]

        ids = [d.stock_item_id for d in dtos]
        stmt = (
            select(link_table.c.stock_item_id, func.count().label("n"))
            .where(link_table.c.stock_item_id.in_(ids))
            .group_by(link_table.c.stock_item_id)
        )
        rows = db.session.execute(stmt).all()

        def _key(v) -> str:
            if isinstance(v, UUID):
                return str(v)
            if isinstance(v, bytes):
                return str(UUID(bytes=v))
            return str(v)
        count_by_id = {_key(row[0]): int(row[1]) for row in rows}
        return [
            dataclasses.replace(
                d,
                linked_product_count=count_by_id.get(str(d.stock_item_id), 0),
            )
            for d in dtos
        ]

    def handle(self, options) -> Page[StockItemDto]:
        # The entities are needed alongside the DTOs for the attention pass —
        # it reads `stock_level` / `expiry_date` / `is_essential` off the
        # entity, and re-deriving them from the DTO would be a third copy of
        # the same predicates. `paginate` hands back DTOs, so collect the
        # entities in the projection as it runs.
        entities: list[StockItem] = []

        def _project(entity: StockItem) -> StockItemDto:
            entities.append(entity)
            return StockItemDto.from_entity(entity)

        page = self._base_query().paginate(
            options, _project, field_map=_FIELD_MAP
        )
        items = self._hydrate_linked_product_count(page.items)
        items = self._hydrate_attention(items, entities)
        return dataclasses.replace(page, items=items)

    def handle_by_id(self, stock_item_id: UUID) -> StockItemDto | None:
        entity = self._base_query().by_id(stock_item_id)
        if entity is None:
            return None
        dto = StockItemDto.from_entity(entity)
        dto = self._hydrate_linked_product_count([dto])[0]
        return self._hydrate_attention([dto], [entity])[0]


@STOCK_ITEM_ROUTER.route("")
def get_stock_items():
    try:
        _Options = parse_query_options(request.args)
        _Page = GetStockItemsHandler(SqlAlchemyRepository()).handle(_Options)
    except InvalidQueryParameter as exc:
        return bad_request(str(exc))
    _LOGGER.info(f"Retrieved {len(_Page.items)} of {_Page.total} stock items.")
    return paginated(_Page.items, _Page.total, _Page.page, _Page.limit)
