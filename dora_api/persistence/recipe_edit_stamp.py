"""FU-730 — stamp `Recipe.updated_at` on every ORM write that edits a recipe.

The stamp used to live in the PATCH handler alone, so any other writer of a
recipe's content (the bulk ingredient linker, the assistant, a future
importer-overwrite or vocabulary rewrite) left "last updated" behind. Lifting it
into a `before_flush` hook makes it the save path's job: a flush that changes a
persisted recipe's own columns or relationships, or adds / changes / removes one
of its `RecipeIngredient` rows, marks the recipe edited.

Not an edit (`NON_EDIT_FIELDS`): cooking, the meal pool, favouriting and
version grouping record what *happened* to a recipe, not what it *is*. A brand
new recipe isn't stamped (it has `created_at`), and a writer that sets
`updated_at` itself in the same flush (a seed back-dating its history) wins.

Not seen here: the access helpers that write steps, sections, tags, tools and
step images through Core statements (`db.session.execute(table.insert())`)
bypass the unit of work. Their only callers are create (a new recipe), new
version (a new recipe) and PATCH, which stamps explicitly for that reason.
"""
from datetime import UTC, datetime
from itertools import chain

from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session

from dora_api.domain.entities.recipe import NON_EDIT_FIELDS, Recipe
from dora_api.domain.entities.recipe_ingredient import RecipeIngredient

# Ingredient-row writes that aren't the recipe changing: unlinking a product
# from a stock item clears every row's pinned product as a side effect.
_INGREDIENT_NON_EDIT_FIELDS = frozenset({"selected_product_id"})

# Recipes inserted earlier in this transaction. Create and new-version flush
# the recipe, then back-fill its ingredients' section ids before committing;
# by that last flush the recipe has left `session.new`, so without this the
# back-fill would read as an edit and stamp a brand-new recipe.
_NEW_IN_TXN = "_dora_recipes_new_in_txn"


def _content_changed(recipe: Recipe) -> bool:
    state = inspect(recipe)
    return any(
        attr.key not in NON_EDIT_FIELDS and attr.history.has_changes()
        for attr in state.attrs
    )


def _ingredient_edited(session: Session, obj: RecipeIngredient) -> bool:
    if obj in session.new or obj in session.deleted:
        return True
    return any(
        attr.key not in _INGREDIENT_NON_EDIT_FIELDS and attr.history.has_changes()
        for attr in inspect(obj).attrs
    )


def _stamp_edited_recipes(session: Session, _flush_context, _instances) -> None:
    new_in_txn: set = session.info.setdefault(_NEW_IN_TXN, set())
    new_in_txn.update(obj.id for obj in session.new if isinstance(obj, Recipe))

    edited: dict[object, Recipe] = {}
    for obj in session.dirty:
        if isinstance(obj, Recipe) and _content_changed(obj):
            edited[obj.id] = obj

    recipe_ids = {
        obj._recipe_id
        for obj in chain(session.new, session.dirty, session.deleted)
        if isinstance(obj, RecipeIngredient)
        and obj._recipe_id is not None
        and _ingredient_edited(session, obj)
    }
    missing = recipe_ids - edited.keys() - new_in_txn
    if missing:
        # One SELECT for the lot (a bulk link touches many recipes).
        with session.no_autoflush:
            for recipe in session.scalars(select(Recipe).where(Recipe.id.in_(missing))):
                edited[recipe.id] = recipe

    now = datetime.now(UTC)
    for recipe in edited.values():
        if recipe.id in new_in_txn or recipe in session.new or recipe in session.deleted:
            continue
        if inspect(recipe).attrs[Recipe.Fields.UPDATED_AT].history.has_changes():
            continue
        recipe.mark_edited(now)


def _forget_new_recipes(session: Session, *_args) -> None:
    session.info.pop(_NEW_IN_TXN, None)


def register_recipe_edit_stamp() -> None:
    """Idempotent: `event.contains` guards a second `configure_mappings`."""
    if not event.contains(Session, "before_flush", _stamp_edited_recipes):
        event.listen(Session, "before_flush", _stamp_edited_recipes)
    for name in ("after_commit", "after_rollback", "after_soft_rollback"):
        if not event.contains(Session, name, _forget_new_recipes):
            event.listen(Session, name, _forget_new_recipes)
