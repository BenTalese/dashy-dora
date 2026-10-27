"""FU-653 — surfacing the Zero-Input Pantry belief beyond the stock pages.

The belief engine (`pantry_belief.py`) has always been able to say "I think
you're out of tinned tomatoes" — but only the stock overview and the stock-item
detail ever showed it. Wherever *else* a stock item is implicated (a recipe's
ingredients, a shopping list, a planned meal) the app went on reading only the
recorded level, so a recipe could sit there looking cookable while Dora quietly
believed a required ingredient had run out days ago.

This module is the one authority for that overlay (R-003). It answers two
questions, and deliberately nothing else:

  * :func:`divergent_items` — which stock items does Dora *disagree* with the
    record about, and in which direction.
  * :func:`recipe_hint` — given one recipe's ingredients, is it **at risk**
    (reads cookable, but a required ingredient is believed out) or **maybe
    cookable after all** (reads not-cookable, but every recorded-missing
    ingredient is believed back in stock).

**The overlay never changes an answer — it only ever adds a remark.** Owner
directive (2026-08-17): cookability is still computed from the recorded levels
by `domain/recipe_cookability.py`, the cookbook is never filtered on a belief,
shopping lines are never auto-added from one, and a planned meal's shortfall is
unchanged. Everything here is additive commentary the user can switch off. That
is also why it lives beside the belief engine rather than inside
`recipe_cookability` — putting it there would invite exactly the merge we're
avoiding.

**Honesty gates** (Charter P3). A remark is only made when all of:
  * the belief is a genuine inference (`is_inferred`) — not an echo of a level
    the user confirmed this week;
  * it *differs* from the recorded level (agreement is not news); and
  * confidence is medium or better — a low-confidence guess contradicting a
    recorded fact is noise, and this overlay appears on surfaces the user came
    to for a different reason.

Per-surface opt-ins live on `User` (see :data:`SURFACE_FLAGS`). The original
`inferred_pantry_enabled` keeps its meaning as the **stock** surface's toggle;
the three new ones default off, because they add remarks to pages the user
didn't ask to have annotated.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.entities.user import User
from dora_api.domain.stock_status import is_missing, is_missing_sequence
from dora_api.features.stock_items.pantry_belief import (
    PantryBelief, compute_belief, gather_belief_inputs_for_items)
from dora_api.infrastructure.session_user import current_user


# Surface ids ↔ the `User` column that gates each. The stock entry is the
# pre-existing P8-07 toggle, kept under its original name (renaming a shipped
# column to fit a later grouping is churn for nothing).
SURFACE_STOCK = "stock"
SURFACE_RECIPES = "recipes"
SURFACE_SHOPPING = "shopping"
SURFACE_MEAL_PLAN = "meal_plan"

SURFACE_FLAGS: dict[str, str] = {
    SURFACE_STOCK: "inferred_pantry_enabled",
    SURFACE_RECIPES: "inference_recipes_enabled",
    SURFACE_SHOPPING: "inference_shopping_enabled",
    SURFACE_MEAL_PLAN: "inference_meal_plan_enabled",
}

# Bands a belief has to be in before it's worth remarking on. 'out' is the
# band that would make an ingredient *missing* for cookability (see
# `stock_status.is_missing` — low is not missing), so it's the only band that
# can put a cookable recipe at risk.
_BAND_OUT = "out"

_CONFIDENT_ENOUGH = ("high", "medium")


@dataclass(frozen=True, slots=True)
class DivergentItems:
    """Stock items whose belief contradicts the record, in both directions.

    * ``believed_out`` — recorded as available, believed out.
    * ``believed_available`` — recorded as missing, believed back in stock.

    ``reasons`` carries the belief's plain-English "why" per item so a surface
    can explain itself without recomputing anything.
    """
    believed_out: frozenset[UUID]
    believed_available: frozenset[UUID]
    reasons: dict[UUID, str]

    @property
    def is_empty(self) -> bool:
        return not self.believed_out and not self.believed_available


EMPTY_DIVERGENCE = DivergentItems(frozenset(), frozenset(), {})


def surface_enabled(user: User | None, surface: str) -> bool:
    """Whether `user` has opted this surface in. Unknown user / unknown
    surface ⇒ False (fail quiet, never fail loud with a wrong remark)."""
    column = SURFACE_FLAGS.get(surface)
    if user is None or column is None:
        return False
    return bool(getattr(user, column, False))


def resolve_divergence(repository, surface: str, items: list[StockItem]) -> DivergentItems:
    """One call for a surface: gate on the signed-in user's toggle, then
    compute. Returns the empty overlay when the surface is off, so callers
    never branch on the flag themselves — they just render whatever comes
    back, and "off" is naturally indistinguishable from "nothing to say"."""
    if not surface_enabled(current_user(repository), surface):
        return EMPTY_DIVERGENCE
    return divergent_items(repository, items)


def divergent_items(repository, items: list[StockItem]) -> DivergentItems:
    """Compute the belief overlay for `items` in bulk.

    Bulk on purpose: `gather_beliefs_for_items` is 3 queries for any number of
    items, so a surface should hand over every item it cares about at once
    rather than asking per row (the N+1 this replaces would be per *recipe*).
    """
    if not items:
        return EMPTY_DIVERGENCE
    # The recorded level comes from the gathered inputs (resolved by foreign
    # key), never `item.stock_level`: the relationship is `noload` and an
    # include doesn't reliably populate it (R-032 / FU-684; finalisation 07-R2).
    inputs = gather_belief_inputs_for_items(repository, items)
    beliefs = {item_id: compute_belief(i) for item_id, i in inputs.items()}
    recorded_missing = {
        item_id: is_missing_sequence(i.recorded_sequence) for item_id, i in inputs.items()
    }
    out: set[UUID] = set()
    available: set[UUID] = set()
    reasons: dict[UUID, str] = {}
    for item_id, belief in beliefs.items():
        if not _worth_remarking(belief):
            continue
        if belief.believed_band == _BAND_OUT and not recorded_missing.get(item_id, False):
            out.add(item_id)
            reasons[item_id] = belief.reason
        elif belief.believed_band != _BAND_OUT and recorded_missing.get(item_id, False):
            available.add(item_id)
            reasons[item_id] = belief.reason
    return DivergentItems(frozenset(out), frozenset(available), reasons)


def _worth_remarking(belief: PantryBelief) -> bool:
    return (
        belief.is_inferred
        and belief.differs_from_recorded
        and belief.confidence_band in _CONFIDENT_ENOUGH
    )


# Hint kinds. Closed set (R-010) — the SPA switches on these strings.
HINT_AT_RISK = "at_risk"
HINT_MAYBE_COOKABLE = "maybe_cookable"


@dataclass(frozen=True, slots=True)
class RecipeHint:
    kind: str                 # HINT_AT_RISK | HINT_MAYBE_COOKABLE
    stock_item_ids: list[UUID]
    stock_item_names: list[str]


@dataclass(frozen=True, slots=True)
class IngredientRow:
    """The only thing :func:`recipe_hint` needs to know about an ingredient.

    Deliberately not the entity: every caller already holds a
    ``RecipeIngredientDto`` carrying these four facts (and its ``is_missing``
    came from the `stock_status` contract), so adapting is a one-liner and the
    rule stays a pure function with no lazy-load surface.
    """
    stock_item_id: UUID | None
    name: str
    is_optional: bool
    is_missing: bool

    @classmethod
    def from_dto(cls, ingredient) -> 'IngredientRow':
        """From a ``RecipeIngredientDto`` (the cookbook path)."""
        return cls(
            stock_item_id=ingredient.stock_item_id,
            name=ingredient.stock_item_name or (ingredient.raw_text or ""),
            is_optional=ingredient.is_optional,
            is_missing=ingredient.is_missing,
        )

    @classmethod
    def from_entity(cls, ingredient) -> 'IngredientRow':
        """From a ``RecipeIngredient`` loaded with its stock item and level
        (the meal-plan path; finalisation 07-R7)."""
        item = ingredient.stock_item
        return cls(
            stock_item_id=item.id if item else None,
            name=item.name if item else (ingredient.raw_text or ""),
            is_optional=ingredient.is_optional,
            is_missing=is_missing(item.stock_level) if item else False,
        )


def recipe_hint(
    rows: list[IngredientRow],
    divergence: DivergentItems,
    *,
    missing_count: int,
    unlinked_count: int,
) -> RecipeHint | None:
    """The additive belief remark for one recipe, or None.

    `missing_count` / `unlinked_count` are **passed in, not recomputed** — they
    come from `domain/recipe_cookability.py`, which stays the single authority
    on what "missing" means (R-003). This function only decides whether the
    belief has something to *add* to that verdict.

    A recipe with an unlinked required ingredient gets nothing: its recorded
    cookability is already the honest `None`, and layering a guess on top of an
    admitted unknown is the opposite of what this is for.
    """
    if divergence.is_empty or unlinked_count > 0:
        return None

    required = [r for r in rows if not r.is_optional and r.stock_item_id is not None]
    if not required:
        return None

    if missing_count == 0:
        # Reads cookable. At risk if any required ingredient is believed out.
        flagged = _unique_rows(r for r in required if r.stock_item_id in divergence.believed_out)
        if flagged:
            return _hint(HINT_AT_RISK, flagged)
        return None

    # Reads not cookable. It's only worth saying "maybe you can after all" when
    # the belief covers *every* recorded-missing ingredient — one rescued
    # ingredient out of three still leaves you unable to cook it.
    missing = _unique_rows(r for r in required if r.is_missing)
    if not missing:
        return None
    if all(r.stock_item_id in divergence.believed_available for r in missing):
        return _hint(HINT_MAYBE_COOKABLE, missing)
    return None


def _hint(kind: str, rows: list[IngredientRow]) -> RecipeHint:
    return RecipeHint(
        kind=kind,
        stock_item_ids=[r.stock_item_id for r in rows if r.stock_item_id],
        stock_item_names=[r.name for r in rows],
    )


def _unique_rows(rows) -> list[IngredientRow]:
    """Distinct stock items, first mention wins. One ingredient listed twice is
    one item — the same rule `missing_count_for` applies to the count."""
    seen: set[UUID] = set()
    out: list[IngredientRow] = []
    for row in rows:
        if row.stock_item_id is None or row.stock_item_id in seen:
            continue
        seen.add(row.stock_item_id)
        out.append(row)
    return out
