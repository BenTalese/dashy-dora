"""C-4 Chunk 2 — the `RecipeTag` link (recipe ↔ user-configurable
`DietaryTag`), through the shared `RecipeLinkAccess` (`_recipe_link_access`).
The module-level names are the ones the handlers import."""
from collections import defaultdict
from typing import Iterable
from uuid import UUID

from sqlalchemy import select

from dora_api.app import db
from dora_api.features.recipes._recipe_link_access import RecipeLinkAccess

TAGS = RecipeLinkAccess(
    "RecipeTag", "DietaryTag", "dietary_tag_id",
    "'{raw}' is not a recognised dietary tag. See /api/recipes/tags for the available list.",
)

validate_tag_ids = TAGS.validate_ids
resolve_tag_filter_values = TAGS.resolve_filter_values
get_tag_ids_for_recipe = TAGS.ids_for_recipe
get_tag_ids_for_recipes = TAGS.ids_for_recipes
set_tag_ids_for_recipe = TAGS.set_ids_for_recipe
find_recipe_ids_with_all_tags = TAGS.recipe_ids_with_all
find_recipe_ids_with_any_tags = TAGS.recipe_ids_with_any


def get_tag_names_for_recipes(recipe_ids: Iterable[UUID]) -> dict[UUID, list[str]]:
    """Bulk fetch of human-readable tag names per recipe — for surfaces that
    show names rather than ids (e.g. the assistant). {recipe_id: [name, ...]}."""
    ids = list(recipe_ids)
    if not ids:
        return {}
    table = db.metadata.tables["RecipeTag"]
    tags = db.metadata.tables["DietaryTag"]
    rows = db.session.execute(
        select(table.c.recipe_id, tags.c.name)
        .select_from(table.join(tags, table.c.dietary_tag_id == tags.c.id))
        .where(table.c.recipe_id.in_(ids))
        .order_by(tags.c.name)
    ).all()
    bucketed: dict[UUID, list[str]] = defaultdict(list)
    for recipe_id, name in rows:
        bucketed[recipe_id].append(name)
    return dict(bucketed)
