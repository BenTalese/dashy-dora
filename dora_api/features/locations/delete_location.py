import logging
from dataclasses import dataclass
from uuid import UUID

from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.entities.stock_location import StockLocation
from dora_api.features.routers import LOCATION_ROUTER
from dora_api.infrastructure.api_response import no_content, not_found
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class DeleteLocationResponse:
    location_not_found: bool = False


class DeleteLocationHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, location_id: UUID) -> DeleteLocationResponse:
        location: StockLocation | None = self.repository.get(StockLocation).by_id(location_id)
        if location is None:
            return DeleteLocationResponse(location_not_found=True)

        # Walk descendants once so we can null out item FKs without leaving
        # orphaned references when the cascade-delete runs. Items belonging
        # to descendant locations would otherwise be left with a dangling
        # stock_location_id (the FK is SET NULL on delete, but doing it
        # explicitly here surfaces the count for logging).
        descendant_ids = self._collect_descendant_ids(location_id)
        if descendant_ids:
            items_in_subtree = (
                self.repository.get(StockItem)
                .all(EntityField(StockItem, "_stock_location_id").in_(list(descendant_ids)))
            )
            for item in items_in_subtree:
                item.stock_location = None

        self.repository.remove(location)
        self.repository.save_changes()
        return DeleteLocationResponse()

    def _collect_descendant_ids(self, root_id: UUID) -> set[UUID]:
        all_locations = self.repository.get(StockLocation).all()
        by_parent: dict[UUID | None, list[StockLocation]] = {}
        for loc in all_locations:
            by_parent.setdefault(loc.parent_id, []).append(loc)

        result: set[UUID] = {root_id}
        stack = [root_id]
        while stack:
            current = stack.pop()
            for child in by_parent.get(current, []):
                if child.id not in result:
                    result.add(child.id)
                    stack.append(child.id)
        return result


@LOCATION_ROUTER.route("/<uuid:location_id>", methods=["DELETE"])
def delete_location(location_id: UUID):
    _Response = DeleteLocationHandler(SqlAlchemyRepository()).handle(location_id)
    if _Response.location_not_found:
        return not_found("StockLocation", location_id)
    _LOGGER.info(f"Deleted location subtree rooted at {location_id}")
    return no_content()
