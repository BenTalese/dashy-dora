"""Recorded stock level, resolved without relying on relationship hydration.

`StockItem.stock_level` is mapped `lazy="noload"`, so reading it off an entity
whose load didn't populate it returns `None` **silently** — no error, just
"this item has no level". That is R-032, the codebase's most recurrent defect
class, and its identity-map corollary is the nastier half: an `.include()` on
*this* query can still hand back an instance the session already tracks with
the relationship unset.

Which is exactly what `/api/stock-items/<id>/buy-verdict` was hitting. It
included `STOCK_LEVEL` and still read `None`, so the `need` axis collapsed to
thin-data and the endpoint answered `unsure/low` for **every** item — including
one flatly out of stock, which should be its most confident `buy`. Belief's
`recorded_sequence` reads the same relationship and had the same exposure; both
now come through here.

Per R-032's own guidance, the FK value is read straight off the private mapped
column (`item._stock_level_id`) and the levels are fetched by id in one query.
There are only three of them, so this is cheap regardless of pantry size.
"""
from __future__ import annotations

from uuid import UUID

from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.entities.stock_level import StockLevel
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository


def resolve_levels_by_item(
    repository: SqlAlchemyRepository, items: list[StockItem],
) -> dict[UUID, StockLevel | None]:
    """`{stock_item_id: StockLevel | None}` for these items, in one query.

    `None` means the item genuinely has no level (no FK, or it points at a
    missing row) — never "the relationship wasn't loaded".
    """
    if not items:
        return {}

    level_id_by_item: dict[UUID, UUID | None] = {
        item.id: item._stock_level_id for item in items
    }

    level_ids = {lid for lid in level_id_by_item.values() if lid is not None}
    levels_by_id: dict[UUID, StockLevel] = {}
    if level_ids:
        levels: list[StockLevel] = repository.get(StockLevel).all(
            EntityField(StockLevel, "id").in_(list(level_ids))
        )
        levels_by_id = {level.id: level for level in levels}

    return {
        item_id: (
            levels_by_id.get(level_id) if level_id is not None else None
        )
        for item_id, level_id in level_id_by_item.items()
    }


def resolve_levels_for_recipes(
    repository: SqlAlchemyRepository, recipes,
) -> dict[UUID, StockLevel | None]:
    """`resolve_levels_by_item` over every stock item these recipes'
    ingredients link to — the map `domain/recipe_cookability` takes as
    `levels_by_item` (FU-684). Needs `INGREDIENTS -> STOCK_ITEM` loaded; the
    level itself is read by FK, so it needn't be."""
    items = {
        ingredient.stock_item.id: ingredient.stock_item
        for recipe in recipes
        for ingredient in (recipe.ingredients or [])
        if ingredient.stock_item is not None
    }
    return resolve_levels_by_item(repository, list(items.values()))


__all__ = ["resolve_levels_by_item", "resolve_levels_for_recipes"]
