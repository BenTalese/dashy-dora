"""Shared write-time meal-slot validation (C-2.A, R-003 / R-010).

`MealPlanEntry.slot` and `Recipe.time_of_day` hold the slot *name* as free
text (no FK). New writes must match the household `MealSlot` vocabulary; any
legacy/off-vocab string already stored is preserved (deleting a slot leaves
those labels intact). The vocabulary + its validation live on the server only
— callers ask here rather than re-deriving the allowed set.

**"New writes" means new VALUES, not new requests** (owner report 2026-09-01:
"getting errors 'could not update the plan' after fiddling with the meal slot
settings"). Deleting a slot deliberately leaves existing labels intact, but
every update endpoint validated its whole payload against the live vocabulary
— and the planner resends the entire forward-entry set on every edit. So one
preserved "Snack" entry made the whole week unsaveable, and the promise that
deleting a slot is non-destructive was only true until the next edit. Callers
that are UPDATING an existing record therefore pass what that record already
holds to `allowed_slot_names`, which keeps a genuinely new off-vocab slot
rejected while letting a record carry its own history forward.
"""
from typing import Iterable

from dora_api.domain.entities.meal_slot import MealSlot
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository


def get_valid_slot_names(repository: SqlAlchemyRepository) -> set[str]:
    """The current household meal-slot vocabulary, as the set of names."""
    return {s.name for s in repository.get(MealSlot).all()}


def ordered_slot_names(repository: SqlAlchemyRepository) -> list[str]:
    """The vocabulary in planner display order (sequence, then name)."""
    slots = sorted(repository.get(MealSlot).all(), key=lambda s: (s.sequence, s.name.lower()))
    return [s.name for s in slots]


def allowed_slot_names(valid: set[str], already_stored: Iterable[str]) -> set[str]:
    """The vocabulary plus whatever labels the record being updated already has.

    `already_stored` is what is on the record TODAY — the entries currently on
    the meal plan, or the recipe's current `time_of_day`. Passing it means a
    resend of an existing off-vocab label is accepted (it is not a new value)
    while a brand-new one is still refused. Create paths pass nothing, because
    a record that does not exist yet cannot have history to preserve.
    """
    return valid | {name for name in already_stored if name}


def find_invalid_slot(names: Iterable[str], valid: set[str]) -> str | None:
    """Return the first name not in the vocabulary, or None if all are valid."""
    for name in names:
        if name not in valid:
            return name
    return None


def invalid_slot_message(name: str, valid: set[str]) -> str:
    return (
        f"Invalid meal slot '{name}'. "
        f"Allowed: {', '.join(sorted(valid))}."
    )
