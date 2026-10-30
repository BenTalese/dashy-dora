"""PROPOSAL_MEAL_PLANS_PART_2 §7 — shared cook-batch grouping + validation.

The create and update write paths both accept forward entries that may carry an
optional transient `cook_key` grouping token: entries sharing a `cook_key` are
materialised under one `CookBatch` (cook once, eat across several days). This is
the single home for the grouping + structural validation of those groups (R-003),
so the two handlers can't drift.

The functions work structurally over any object exposing `.recipe_id`,
`.scheduled_for`, `.slot` and `.cook_key` — i.e. `_entry_writes.MealPlanEntryRequest`
and its update subclass.
"""
from collections import defaultdict
from typing import Optional


def group_by_cook_key(entry_requests) -> dict:
    """Return `{cook_key: [entry_request, ...]}` for every entry carrying a
    (non-null) `cook_key`. Entries without a key are standalone meals and are
    omitted."""
    groups: dict = defaultdict(list)
    for entry in entry_requests:
        key = getattr(entry, "cook_key", None)
        if key is None:
            continue
        groups[key].append(entry)
    return dict(groups)


def validate_cook_groups(entry_requests, preserved_keys: frozenset[str] = frozenset()) -> Optional[str]:
    """Structural validation of every `cook_key` group. Returns a user-facing
    error message on the first violation, or None when all groups are valid.

    A cook batch (entries sharing a `cook_key`) must:
      * link at least two days (a one-day "batch" is just a normal meal) —
        unless the key names a preserved batch (`preserved_keys`): a batch
        straddling today keeps its past cook day server-side, so one forward
        leftover day resent under its id is still a two-day batch;
      * use a single recipe (one cook produces one dish);
      * use a single meal slot (v1 links the same slot across days);
      * never repeat a day (each day is one occasion of the cook);
      * never contain a meal marked `cook_fresh` — a batch IS the cooked pool,
        and "cooked fresh on the day, outside the pool" is its negation. The
        client hides the toggle on a linked meal, so this is a contract guard
        rather than a reachable path (owner 2026-09-04).

    Past-date and recipe-existence checks stay in the handlers — they're not
    batch-specific.
    """
    for key, members in group_by_cook_key(entry_requests).items():
        if any(getattr(m, "cook_fresh", False) for m in members):
            return "A meal cooked fresh on the day can't also be part of a cook batch."
        if len(members) < 2 and str(key) not in preserved_keys:
            return "A cook batch must cover at least two days."
        if len({m.recipe_id for m in members}) > 1:
            return "A cook batch must use a single recipe across all its days."
        if len({m.slot for m in members}) > 1:
            return "A cook batch must use the same meal slot on every day."
        days = [m.scheduled_for for m in members]
        if len(set(days)) != len(days):
            return "A cook batch can't put two meals on the same day."
    return None
