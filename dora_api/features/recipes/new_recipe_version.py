"""C-4 Chunk 8 — `POST /recipes/<id>/new-version`.

Per DEC-2 the version model is *flat*: recipes sharing a
`version_group_id` are equal peers (no current pointer, no snapshot vs
current distinction). New-version copies the source recipe (ingredients,
sections, tools, steps, step images, vocabulary, image, source URL) into a
fresh row with the same group id — and if the source had no group id yet, allocates one and
back-fills the source so the two recipes form the group.

The handler returns the new recipe id; the SPA routes into its detail
page with `(v<N>)` already in the name.

Allocations stay per-recipe (user picks which version they want when
scheduling a meal-plan entry); no version-aware allocation logic.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select

from dora_api.app import db
from dora_api.domain.entities.recipe import Recipe
from dora_api.domain.entities.recipe_ingredient import RecipeIngredient
from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.types import EMPTY_UUID
from dora_api.features.recipes.recipe_section_access import (
    SectionWrite, get_sections_for_recipe, replace_sections_for_recipe,
)
from dora_api.features.recipes.recipe_step_access import (
    StepWrite, get_steps_for_recipe, replace_steps_for_recipe,
)
from dora_api.features.recipes.recipe_step_image_access import (
    StepImageWrite, get_step_image_metadata_for_recipe, get_step_image_bytes,
    replace_step_images_for_recipe,
)
from dora_api.features.recipes.recipe_tag_access import (
    get_tag_ids_for_recipe, set_tag_ids_for_recipe,
)
from dora_api.features.recipes.recipe_tool_access import (
    get_tool_ids_for_recipe, set_tool_ids_for_recipe,
)
from dora_api.features.routers import RECIPE_ROUTER
from dora_api.infrastructure.api_response import created, not_found
from dora_api.persistence.field import EntityField
from dora_api.features.recipes.get_recipes import GetRecipesHandler, get_recipes
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class NewRecipeVersionResponse:
    new_recipe_id: UUID = EMPTY_UUID
    source_not_found: bool = False


class NewRecipeVersionHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, source_id: UUID) -> NewRecipeVersionResponse:
        source: Recipe | None = (
            self.repository
            .get(Recipe)
            .include(Recipe.Fields.INGREDIENTS)
            # cuisine + category are noload now; the clone below
            # reads both off `source`, so eager-load them.
            .include(Recipe.Fields.CUISINE)
            .include(Recipe.Fields.CATEGORY)
            .one(EntityField(Recipe, "id").eq(source_id))
        )
        if source is None:
            return NewRecipeVersionResponse(source_not_found=True)

        # Resolve the group id. A singleton source gets a fresh group id
        # which is back-filled onto the source itself so the two recipes
        # form the group — otherwise the link would only exist on the new
        # row and we'd lose the symmetry the "equal peers" model expects.
        group_id = source.version_group_id
        if group_id is None:
            group_id = uuid4()
            source.version_group_id = group_id
            # Flush the back-fill so `_sibling_count` (a Core SELECT) counts
            # the source as a group member. Without it the first version of a
            # singleton counted 0 siblings → "(v1)", while the second (source
            # now visibly grouped) counted 1 → "(v3)": the sequence skipped v2
            # entirely. Flushing makes it v2, v3, v4… (FU-589).
            self.repository.flush()

        sibling_count = self._sibling_count(group_id)
        copy_name = f"{source.name} (v{sibling_count + 1})"

        # Clone ingredients first — the new recipe + its step links need
        # them inserted before the recipe save, so build them, add() each
        # (the repo assigns ids), and remember the old→new id map for
        # step linkage below.
        #
        # FU-590 — the whole clone-and-build runs inside `no_autoflush`. The
        # cloned RecipeIngredient rows are add()ed to the session BEFORE the
        # parent `new_recipe` exists to link them (recipe_id still NULL), and
        # constructing `new_recipe` reads `source.image` — a deferred column,
        # so its lazy load issues a SELECT that would otherwise autoflush the
        # unparented ingredients → `NOT NULL constraint failed:
        # RecipeIngredient.recipe_id` → 500 on new-version of ANY recipe that
        # has ingredients. Suppressing autoflush here lets the explicit flush
        # below persist Recipe-then-ingredients in FK-correct order.
        old_to_new_ing: dict[UUID, UUID] = {}
        with db.session.no_autoflush:
            cloned_ingredients: list[RecipeIngredient] = []
            for ing in (source.ingredients or []):
                # R-032 — `ing.stock_item` is a `lazy="noload"` relationship
                # (always None), so cloning off it silently DROPPED the link:
                # a linked ingredient came out unlinked, and — with no
                # raw_text copied either — violated the anchor CHECK
                # (stock_item_id OR raw_text) → 500. Resolve the real
                # StockItem from the loaded FK, and carry raw_text +
                # is_optional so both anchor kinds and the optional flag
                # survive the copy.
                linked = (
                    self.repository.get(StockItem).by_id(ing._stock_item_id)
                    if ing._stock_item_id is not None else None
                )
                cloned = RecipeIngredient(
                    notes=ing.notes,
                    quantity=ing.quantity,
                    stock_item=linked,
                    unit=ing.unit,
                    is_optional=ing.is_optional,
                    raw_text=ing.raw_text,
                    label=ing.label,
                    preferred_buy_id=ing.preferred_buy_id,
                    selected_product_id=ing.selected_product_id,
                )
                cloned_ingredients.append(cloned)
            for ing in cloned_ingredients:
                self.repository.add(ing)
            for original, copy in zip(source.ingredients or [], cloned_ingredients):
                old_to_new_ing[original.id] = copy.id

            new_recipe = Recipe(
                available_meals=0,
                category=source.category,
                cook_time_minutes=source.cook_time_minutes,
                cuisine=source.cuisine,
                difficulty=source.difficulty,
                image=source.image,
                ingredients=cloned_ingredients,
                instructions=source.instructions,
                is_favourite=False,
                last_made_on=None,
                name=copy_name,
                prep_time_minutes=source.prep_time_minutes,
                recipe_collection=source.recipe_collection,
                servings=source.servings,
                source=source.source,
                time_of_day=source.time_of_day,
                version_group_id=group_id,
                kcal=source.kcal,
                steps_mode=source.steps_mode,
                notes=source.notes,  # RD-29 — carry personal notes across versions
                # a new version is a fresh row in the household; stamp
                # at write time rather than carrying the source's created_at,
                # so the "Recently added" axis surfaces the version when it
                # was actually added here.
                created_at=datetime.now(timezone.utc),
            )
            self.repository.add(new_recipe)
        # FU-512 unit-of-work: same shape as CreateRecipe (FU-456). Access
        # helpers below use `db.session.execute(insert(...))` at Core level,
        # so the new-recipe FK must be visible before their inserts — flush,
        # don't commit. `replace_steps_for_recipe` can raise ValueError on a
        # bad parent chain; because we clone from a valid source that path is
        # empirically unreachable, but the shape stays uniform.
        self.repository.flush()

        # Sections — the recipe's named ingredient/step groups ("For the
        # sauce"). Cloned before the ingredient back-fill and the step writes
        # below, because both carry a `section_id` FK into this table and the
        # rows have to exist first. Until 2026-08-26 they were not copied at
        # all, so a sectioned recipe came out of new-version flattened into
        # the implicit main group — every card gone, on a page that renders
        # sections as cards.
        source_sections = get_sections_for_recipe(source_id)
        old_to_new_section: dict[UUID, UUID] = {}
        if source_sections:
            # The source section's own id doubles as the client_id, so the
            # helper's client→real map *is* the old→new map.
            old_to_new_section = {
                UUID(str(client_id)): real
                for client_id, real in replace_sections_for_recipe(
                    new_recipe.id,
                    [
                        SectionWrite(
                            client_id=row["id"],
                            sequence=row["sequence"],
                            name=row["name"],
                        )
                        for row in source_sections
                    ],
                ).items()
            }
            for original, copy in zip(source.ingredients or [], cloned_ingredients):
                if original.section_id is None:
                    continue
                copy.section_id = old_to_new_section.get(original.section_id)

        # Tags + tools — separate access helpers; safe to call after flush.
        tag_ids = get_tag_ids_for_recipe(source_id)
        if tag_ids:
            set_tag_ids_for_recipe(new_recipe.id, tag_ids)
        tool_ids = get_tool_ids_for_recipe(source_id)
        if tool_ids:
            set_tool_ids_for_recipe(new_recipe.id, tool_ids)

        # Steps — map each step's `ingredient_ids` through the old→new
        # ingredient id map so the copies reference the *new* recipe's
        # ingredients rather than the source's. Step ids themselves get
        # fresh uuid4()s inside `replace_steps_for_recipe` via client_ids.
        source_steps = get_steps_for_recipe(source_id)
        if source_steps:
            old_step_id_to_client: dict[UUID, str] = {
                row["id"]: str(row["id"]) for row in source_steps
            }
            step_writes: list[StepWrite] = []
            for row in source_steps:
                parent = row["parent_step_id"]
                step_writes.append(StepWrite(
                    client_id=old_step_id_to_client[row["id"]],
                    parent_client_id=(
                        old_step_id_to_client[parent] if parent is not None else None
                    ),
                    sequence=row["sequence"],
                    text=row["text"],
                    hint=row["hint"],
                    timer_minutes=row.get("timer_minutes"),
                    ingredient_ids=[
                        old_to_new_ing[oid]
                        for oid in row["ingredient_ids"]
                        if oid in old_to_new_ing
                    ],
                    tool_ids=list(row["tool_ids"]),
                    section_id=(
                        old_to_new_section.get(row["section_id"])
                        if row["section_id"] is not None else None
                    ),
                ))
            replace_steps_for_recipe(new_recipe.id, step_writes)

        # PROPOSAL_RECIPE_IMAGE_STEPS — clone ordered step images too. We
        # decode each row's bytes back into the data-URL string and feed
        # the access helper's write path so encoding stays consistent
        # across upload sites.
        source_images = get_step_image_metadata_for_recipe(source_id)
        if source_images:
            image_writes: list[StepImageWrite] = []
            for row in source_images:
                raw = get_step_image_bytes(source_id, row["id"])
                if raw is None:
                    continue
                image_writes.append(StepImageWrite(
                    sequence=row["sequence"],
                    image_data_url=raw.decode("utf-8", "ignore"),
                ))
            if image_writes:
                replace_step_images_for_recipe(new_recipe.id, image_writes)

        # Single commit at the end — everything or nothing.
        self.repository.save_changes()
        return NewRecipeVersionResponse(new_recipe_id=new_recipe.id)

    def _sibling_count(self, group_id: UUID) -> int:
        table = db.metadata.tables["Recipe"]
        rows = db.session.execute(
            select(table.c.id).where(table.c.version_group_id == group_id)
        ).all()
        return len(rows)


@RECIPE_ROUTER.route("<uuid:recipe_id>/new-version", methods=["POST"])
def new_recipe_version(recipe_id: UUID):
    handler = NewRecipeVersionHandler(SqlAlchemyRepository())
    response = handler.handle(recipe_id)
    if response.source_not_found:
        _LOGGER.warning(f"New version requested for missing recipe {recipe_id}.")
        return not_found(Recipe.__name__, recipe_id)
    dto = GetRecipesHandler(SqlAlchemyRepository()).handle_by_id(response.new_recipe_id)
    return created(
        response.new_recipe_id,
        f"{RECIPE_ROUTER.name}.{get_recipes.__name__}",
        "recipe_id",
        body=dto,
    )
