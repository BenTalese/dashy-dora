"""Returns the full location tree with item counts.

A single call powers the Home Zones view, the Zone Detail view, and the
hierarchical destination picker — paginating tree shapes is more trouble
than it's worth at the data sizes we expect (dozens of nodes, hundreds of
items).

The old `attention_score` / `attention_reasons` "heatmap" fields
(`features/locations/attention.py`) were computed here on every request
but never rendered by any SPA surface — legacy from the killed
stock-map / heatmap feature. Removed during the stocktake-mode cleanup
(2026-07-04) along with the attention module itself.
"""
import logging
from dataclasses import dataclass, field
from typing import List
from uuid import UUID

from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.entities.stock_location import StockLocation
from dora_api.features.routers import LOCATION_ROUTER
from dora_api.infrastructure.api_response import ok
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


@dataclass
class LocationItemDto:
    stock_item_id: UUID
    name: str
    stock_level_name: str | None
    expiry_date: str | None
    is_essential: bool


@dataclass
class LocationNodeDto:
    location_id: UUID
    name: str
    kind: str
    parent_id: UUID | None
    sequence: int
    direct_item_count: int
    descendant_item_count: int
    items: List[LocationItemDto] = field(default_factory=list)
    children: List["LocationNodeDto"] = field(default_factory=list)


class GetLocationTreeHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self) -> List[LocationNodeDto]:
        locations: List[StockLocation] = self.repository.get(StockLocation).all()
        items: List[StockItem] = (
            self.repository.get(StockItem)
            .include("stock_level")
            .include("stock_location")
            .all()
        )

        # Bucket items by their location_id (None = unassigned, surfaced
        # separately in the UI).
        items_by_location: dict[UUID, List[StockItem]] = {}
        for item in items:
            if item.stock_location is None:
                continue
            items_by_location.setdefault(item.stock_location.id, []).append(item)

        node_by_id: dict[UUID, LocationNodeDto] = {}
        for loc in locations:
            direct_items = items_by_location.get(loc.id, [])
            item_dtos: List[LocationItemDto] = [
                LocationItemDto(
                    stock_item_id = item.id,
                    name = item.name,
                    stock_level_name = (
                        item.stock_level.name if item.stock_level else None
                    ),
                    expiry_date = item.expiry_date.isoformat() if item.expiry_date else None,
                    is_essential = bool(item.is_essential),
                )
                for item in direct_items
            ]
            node_by_id[loc.id] = LocationNodeDto(
                location_id = loc.id,
                name = loc.name,
                kind = loc.kind,
                parent_id = loc.parent_id,
                sequence = loc.sequence or 0,
                direct_item_count = len(direct_items),
                descendant_item_count = len(direct_items),
                items = item_dtos,
            )

        # Wire children into parents (sorted by sequence then name for
        # stable rendering) and roll up descendant counts from leaves
        # to roots.
        children_by_parent: dict[UUID | None, List[LocationNodeDto]] = {}
        for node in node_by_id.values():
            children_by_parent.setdefault(node.parent_id, []).append(node)
        for siblings in children_by_parent.values():
            siblings.sort(key=lambda n: (n.sequence, n.name.lower()))

        def populate(node: LocationNodeDto) -> None:
            for child in children_by_parent.get(node.location_id, []):
                populate(child)
                node.descendant_item_count += child.descendant_item_count
                node.children.append(child)

        roots = children_by_parent.get(None, [])
        for root in roots:
            populate(root)
        return roots


@LOCATION_ROUTER.route("", methods=["GET"])
def get_location_tree():
    _Tree = GetLocationTreeHandler(SqlAlchemyRepository()).handle()
    _LOGGER.info(f"Returning location tree with {len(_Tree)} root zones.")
    return ok(_Tree)
