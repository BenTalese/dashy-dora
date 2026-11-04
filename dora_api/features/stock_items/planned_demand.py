"""Planned demand — "the plan needs this, and you haven't got it".

Owner, 2026-09-03, asked whether one of Dora's belief metrics was based on how
many planned meals a stock item is involved in, reasoning that it would be a
good indicator when an item is Low or Out. Read literally as a *belief* input
it is wrong, and instructively so: planning to cook rice on Thursday tells you
nothing about how much rice is in the cupboard today. It is a statement about
**demand**, not about the shelf — a different question, on a different clock,
from the one `pantry_belief.py` answers.

So it is its own signal, computed here, and the two are deliberately never
mixed. The belief says *what you have*; this says *what you are going to need,
and by when*. They are only interesting together, which is where the sentence
the owner asked for comes from:

    "3 planned meals in the next fortnight need Rice (2 already covered by
     cooked batches) — the first is Thursday, and you're Low."

**Coverage comes from the shared pool model** (`meal_plans/planned_meals.py`),
so the batch-cooking variant the owner described — *"2 have been allocated a
meal"* — is the same allocation the shortfall report uses rather than a second
guess at it (R-003). A household that doesn't batch-cook has an empty pool and
every planned meal counts, which is the right degenerate case.

**Only required, linked ingredients count.** An optional ingredient is not
demand (the same rule `recipe_cookability` applies), and an unlinked one has
no stock item to attach to.

**Urgency is a function of the recorded level, and Out outranks Low** (owner:
*"Out would be higher confidence than low"*). An Out item with planned meals
against it is a hard blocker — the meal cannot be cooked — whereas a Low one
is a warning that it might not stretch. That grading is exposed as `urgency`
rather than left for each caller to re-derive from `level + count`, which is
how a domain rule ends up written four times in two languages (R-003).

This is a **plain fact about the user's own plan**, not an inference, so
unlike the belief overlay it is not gated on the inference opt-outs. It is
gated on the meal planner being switched on at all: with no planner there is
no plan, and the signal is vacuous rather than merely off.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from dora_api.domain.entities.recipe_ingredient import RecipeIngredient
from dora_api.domain.stock_status import (LOW_STOCK_SEQUENCE,
                                          OUT_OF_STOCK_SEQUENCE)
from dora_api.features.meal_plans.planned_meals import upcoming_planned_meals
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.domain.locale_format import DEFAULT_LOCALE, format_day
from dora_api.features.app_settings.clock import household_locale


# How far ahead "coming week(s)" reaches. Two weeks rather than one: the
# planner's own horizon is a rolling set of weeks, and a demand signal that
# stopped at Sunday would go quiet every Friday — exactly when the shop that
# would fix it is about to happen. Coarse and tunable, like every other
# threshold in this corner of the app.
PLANNED_DEMAND_HORIZON_DAYS = 14

# How many recipe names the sentence names before it says "and N others". A
# list of five recipe names is not a sentence anybody reads.
_MAX_NAMED_RECIPES = 2

URGENCY_NONE = "none"
URGENCY_WATCH = "watch"      # recorded Low, and the plan wants it
URGENCY_BLOCKING = "blocking"  # recorded Out, and the plan wants it


@dataclass(frozen=True, slots=True)
class PlannedDemand:
    """What the upcoming plan wants of one stock item."""
    planned_meals: int          # upcoming un-consumed entries whose recipe needs it
    covered_meals: int          # of those, already covered by a cooked-batch pool
    needed_meals: int           # planned - covered: still have to be cooked
    earliest_needed: date | None  # first uncovered date; None when all covered
    recipe_names: list[str] = field(default_factory=list)
    urgency: str = URGENCY_NONE
    reason: str = ""


def urgency_for(recorded_sequence: int | None, needed_meals: int) -> str:
    """Grade the demand against the recorded level. Out outranks Low."""
    if needed_meals <= 0 or recorded_sequence is None:
        return URGENCY_NONE
    if recorded_sequence >= OUT_OF_STOCK_SEQUENCE:
        return URGENCY_BLOCKING
    if recorded_sequence == LOW_STOCK_SEQUENCE:
        return URGENCY_WATCH
    return URGENCY_NONE


def _plural(n: int, unit: str) -> str:
    return f"{n} {unit}{'' if n == 1 else 's'}"


def build_reason(
    *,
    planned_meals: int,
    covered_meals: int,
    recipe_names: list[str],
    earliest_needed: date | None,
    locale: str = DEFAULT_LOCALE,
) -> str:
    """The one-line "why" the UI surfaces. Same shape as the belief's `reason`.

    Deliberately says nothing about the stock level: the level is already on
    screen beside this, and repeating it is how a two-line card becomes an
    essay. This sentence's job is the *plan* half.
    """
    if planned_meals <= 0:
        return ""
    named = recipe_names[:_MAX_NAMED_RECIPES]
    rest = len(recipe_names) - len(named)
    if not named:
        what = "meals"
    elif rest > 0:
        # "A, B and 2 others" — the tail is what the "and" belongs to.
        what = ", ".join(named) + f" and {_plural(rest, 'other')}"
    else:
        # No tail, so the last comma becomes an "and": "A and B", not "A, B".
        what = " and ".join(named)
    head = f"{_plural(planned_meals, 'planned meal')} coming up need this: {what}"
    if covered_meals > 0:
        head += f"; {covered_meals} already covered by a cooked batch"
    if earliest_needed is not None:
        # In the household's region format (FU-969).
        head += f". First needed {format_day(earliest_needed, locale)}"
    return head + "."


def gather_planned_demand(
    repository: SqlAlchemyRepository,
    *,
    recorded_by_item: dict[UUID, int] | None = None,
    horizon_days: int = PLANNED_DEMAND_HORIZON_DAYS,
) -> dict[UUID, PlannedDemand]:
    """Planned demand per stock item, keyed by id. Items with none are absent.

    `recorded_by_item` supplies each item's recorded level sequence so the
    urgency can be graded. Callers already holding those levels (the stock
    overview resolves them for the belief overlay) should pass them; omit it
    and every entry comes back at `URGENCY_NONE`, which is the honest answer
    when nobody said what the level is.
    """
    locale = household_locale(repository)
    snapshot = upcoming_planned_meals(repository, horizon_days=horizon_days)
    if not snapshot.meals:
        return {}

    recipe_ids = list({m.recipe_id for m in snapshot.meals})
    # R-032: `RecipeIngredient.stock_item` is `lazy="noload"` and reading it
    # returns None silently, so the link is resolved off the private mapped FK
    # column — the idiom `_level_access.py` established after the same trap
    # made the buy-verdict endpoint answer "unsure" for every item. The FK is
    # all we need here: this signal counts items, it never renders one.
    ingredients: list[RecipeIngredient] = repository.get(RecipeIngredient).all(
        EntityField(RecipeIngredient, "_recipe_id").in_(recipe_ids)
    )
    # recipe -> the stock items it *requires*. A set, because one recipe can
    # list the same stock item twice (two ingredient rows, e.g. "1 onion,
    # diced" and "1 onion, sliced") and that is one item's worth of demand
    # per meal, not two.
    items_by_recipe: dict[UUID, set[UUID]] = {}
    for ing in ingredients:
        if ing.is_optional or ing._stock_item_id is None:
            continue
        items_by_recipe.setdefault(ing._recipe_id, set()).add(ing._stock_item_id)

    planned: dict[UUID, int] = {}
    covered: dict[UUID, int] = {}
    earliest: dict[UUID, date] = {}
    names: dict[UUID, list[tuple[date, str]]] = {}
    for meal in snapshot.meals:
        for item_id in items_by_recipe.get(meal.recipe_id, set()):
            planned[item_id] = planned.get(item_id, 0) + 1
            if meal.covered:
                covered[item_id] = covered.get(item_id, 0) + 1
                continue
            names.setdefault(item_id, []).append((meal.scheduled_for, meal.recipe_name))
            current = earliest.get(item_id)
            if current is None or meal.scheduled_for < current:
                earliest[item_id] = meal.scheduled_for

    recorded_by_item = recorded_by_item or {}
    out: dict[UUID, PlannedDemand] = {}
    for item_id, count in planned.items():
        covered_count = covered.get(item_id, 0)
        needed = count - covered_count
        # Distinct recipe names, soonest first — the sentence names the meal
        # you will hit first, which is the one that makes the point.
        ordered: list[str] = []
        for _when, name in sorted(names.get(item_id, []), key=lambda r: r[0]):
            if name not in ordered:
                ordered.append(name)
        out[item_id] = PlannedDemand(
            planned_meals=count,
            covered_meals=covered_count,
            needed_meals=needed,
            earliest_needed=earliest.get(item_id),
            recipe_names=ordered,
            urgency=urgency_for(recorded_by_item.get(item_id), needed),
            reason=build_reason(
                planned_meals=count,
                covered_meals=covered_count,
                recipe_names=ordered,
                earliest_needed=earliest.get(item_id),
                locale=locale,
            ),
        )
    return out

