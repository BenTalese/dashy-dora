"""A meal plan's revision: a fingerprint of the week as it stands (FU-967).

The planner saves a week by resending its whole forward entry list, built from
the copy the device last loaded. Two devices — or one phone left open on the
planner since breakfast — therefore overwrite each other's meals without a
word. The plan DTO carries this revision; a PATCH that names the revision it
started from is refused with a 409 when the week has changed since, and the
client reloads and re-applies its one edit.

A fingerprint of the stored rows rather than a counter, so every writer that
touches a week (swaps, reconcile, cook finish, templates) changes it without
each having to remember to bump anything.
"""
from __future__ import annotations

import hashlib

from dora_api.domain.entities.meal_plan import MealPlan
from dora_api.persistence.aware import as_utc


def plan_revision(plan: MealPlan) -> str:
    rows = sorted(
        (
            str(entry.id),
            str(getattr(entry, "_recipe_id", None) or getattr(entry.recipe, "id", "")),
            entry.scheduled_for.isoformat(),
            int(entry.servings),
            entry.slot,
            as_utc(entry.consumed_at).isoformat() if entry.consumed_at else "",
            str(entry.cook_batch_id or ""),
            bool(entry.cook_fresh),
        )
        for entry in (plan.entries or [])
    )
    payload = repr((plan.start_date.isoformat(), plan.name or "", rows))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
