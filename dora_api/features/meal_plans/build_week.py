"""FU-596 — "Build my week" auto-planner (server-owned meal selection + placement).

The old "Plan step-by-step" builder was just the planner's recipe picker in a
modal — the user hand-picked every meal and the client spread them across days
(dropping every one into the first slot, hence FU-596). This replaces it with a
genuine *generator*: given light guidance (which days, which meal slots, an
emphasis, an optional budget cap) Dora proposes a week — the client renders it
as an editable preview and commits through the existing create/update path.

The shape the user drives is deliberately flat: two independent sets of toggles
(days, then slots) whose cross-product *is* the plan — one meal per day×slot
cell, no separate meal-count knob. `repeat_same_day` builds one day's line-up
and duplicates it across the rest.

  POST /api/meal-plans/auto-build  — preview only; never persists.

**R-003 / state-ownership:** recipe *selection* and slot/day *placement* are
cross-entity domain rules, so they live here, not in the SPA — mirroring the
`swap_suggestions.py` shape: a **pure ranker** (`select_recipes` / `place_entries`,
driven by fixtures in the unit tests) + a thin repo-touching orchestrator
(`compute_auto_build`).

**Not a Decision-7 regression:** PROPOSAL_MEAL_PLANS §3.6 cut the *"Suggest meals
I can cook now"* browse surface (that belongs on Cookbook). This is a plan
generator; it only *uses* the cookable / expiring signals to rank, it does not
resurrect a cookable-now list page.
"""
import logging
import random
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional
from uuid import UUID

from flask import request as flask_request
from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.app_setting import AppSetting
from dora_api.domain.entities.meal_plan_entry import MealPlanEntry
from dora_api.features.app_settings.access import money_features_enabled
from dora_api.features.app_settings.clock import household_today
from dora_api.features.budget.budget import household_budget, period_headroom
from dora_api.features.meal_slots.slot_validation import ordered_slot_names
from dora_api.features.recipes.all_recipes import load_all_recipe_dtos
from dora_api.features.recipes.get_recipes import count_expiring_ingredients_per_recipe
from dora_api.features.recipes.recipe_cost import estimate_costs_for
from dora_api.features.routers import MEAL_PLAN_ROUTER
from dora_api.infrastructure.api_response import bad_request, ok
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

_LOGGER = logging.getLogger(__name__)

WEEK_LENGTH_DAYS = 7
# "expiring soon" horizon for the use-up-stock emphasis — matches the cookbook
# "Uses expiring ingredients" filter (get_recipes / rescue feed, R-003).
EXPIRING_HORIZON_DAYS = 14
# Hard ceiling so a bad client can't ask us to place 500 meals. The builder is
# a *week* tool, so the real bound is `days` (≤ 7, validated) × the household
# slot vocabulary (server-resolved, so a client can't inflate it); this is the
# backstop for an install with an unusually long slot list.
MAX_MEALS = 42
# How Reshuffle varies a plan (owner, 2026-09-12: *"reshuffle doesn't do
# anything on the current dev data — I'd at least expect a couple of meals to
# swap or days to rotate"*).
#
# It used to be a per-candidate random tiebreak of up to 1.5 added to the
# score. That is invisible on a real cookbook: one expiring ingredient is worth
# 3.0 and cookable-now 2.0, so the same recipes won every single time and only
# a pool of genuinely equal candidates (which the unit tests build, and a
# kitchen doesn't) ever shuffled.
#
# Instead of nudging the score, the *pick* is now a sample: at each step take
# the candidates within `NEAR_BEST_WINDOW` of the leader — capped, so a flat
# pool doesn't turn selection into a lottery — and choose one at random. A
# strong signal still wins outright, because nothing else is near it. With no
# rng (the fixture unit tests) it is the plain argmax, exactly as before.
NEAR_BEST_WINDOW = 1.5
NEAR_BEST_MAX = 4
# PROPOSAL_MEAL_PLANS_PART_2 §9 — for Batch-cook-style households the builder
# proposes *cook batches* (one cook feeds a run of days in a slot) instead of a
# distinct recipe per day. Each cook spans up to this many days — a middle
# ground between variety and effort, and within the ~4-day freshness horizon
# (§10). Fresh households cook one distinct recipe per day (span 1).
BATCH_COOK_SPAN_DAYS = 3

# ── Emphasis + reason-chip vocabulary (frozen server-side, R-003) ──────────

EMPHASIS_USE_UP_STOCK = "use_up_stock"
EMPHASIS_VARIETY = "variety"
EMPHASIS_FAVOURITES = "favourites"
EMPHASIS_SURPRISE = "surprise"
_EMPHASES = frozenset({
    EMPHASIS_USE_UP_STOCK, EMPHASIS_VARIETY, EMPHASIS_FAVOURITES, EMPHASIS_SURPRISE,
})

CHIP_USES_EXPIRING = "uses_expiring"        # "Uses stock that's expiring"
CHIP_COOKABLE_NOW = "cookable_now"          # "You have everything for this"
CHIP_FAVOURITE = "favourite"                # "A favourite"
CHIP_NOT_MADE_RECENTLY = "not_made_recently"  # "Haven't had in a while"
CHIP_VARIETY = "variety"                    # "Adds variety"
CHIP_BUDGET = "budget_friendly"             # "Cheaper — keeps you on budget"
CHIP_PICKED = "picked"                      # neutral fallback


@dataclass(frozen=True, slots=True)
class RecipeCandidate:
    """The slim view the pure ranker needs — deliberately decoupled from
    `RecipeDto` so the ranker's unit tests can drive it with plain fixtures."""
    recipe_id: UUID
    name: str
    time_of_day: Optional[str]
    cookable: Optional[bool]
    expiring_count: int
    is_favourite: bool
    plan_count: int
    not_made_recently: bool
    cuisine_id: Optional[UUID]
    category_id: Optional[UUID]
    estimated_cost: Optional[float]
    servings: Optional[int]
    missing_stock_item_names: tuple


@dataclass(frozen=True, slots=True)
class ProposedEntry:
    recipe_id: UUID
    recipe_name: str
    scheduled_for: date
    slot: str
    servings: int
    reason_chip: str
    cookable: Optional[bool]
    missing_stock_item_names: List[str]
    estimated_cost: Optional[float]
    # PROPOSAL_MEAL_PLANS_PART_2 §9 — grouping token for a proposed cook batch
    # (entries sharing it are one cook, several days). None = a standalone meal.
    cook_key: Optional[str] = None


@dataclass(frozen=True, slots=True)
class AutoBuildResponse:
    entries: List[ProposedEntry]
    days_used: List[date]
    slots_used: List[str]
    cost_total: Optional[float]
    budget_amount: Optional[float]
    projected_over: bool


# ── Pure ranker (no repo — driven by fixtures in the unit tests) ───────────


def _base_score(c: RecipeCandidate, emphasis: str, rng: Optional[random.Random]) -> float:
    """How strongly this recipe fits the chosen emphasis (higher = better).
    Variety spread is applied on top of this during selection, not here."""
    if emphasis == EMPHASIS_USE_UP_STOCK:
        return (
            3.0 * c.expiring_count
            + (2.0 if c.cookable is True else 0.0)
            + (0.5 if c.not_made_recently else 0.0)
        )
    if emphasis == EMPHASIS_FAVOURITES:
        return (
            (3.0 if c.is_favourite else 0.0)
            + 0.2 * c.plan_count
            + (0.5 if c.not_made_recently else 0.0)
        )
    if emphasis == EMPHASIS_VARIETY:
        return (1.0 if c.not_made_recently else 0.0) + (0.3 if c.is_favourite else 0.0)
    if emphasis == EMPHASIS_SURPRISE:
        # Mostly random, with a gentle lean toward recipes not made recently.
        jitter = rng.random() if rng is not None else 0.0
        return jitter + (0.5 if c.not_made_recently else 0.0)
    return 0.0


def _variety_weight(emphasis: str) -> float:
    """How hard to penalise repeating a cuisine/category already picked. Strong
    for the Variety emphasis; a mild anti-repeat nudge for everything else."""
    return 2.0 if emphasis == EMPHASIS_VARIETY else 0.5


def select_recipes(
    candidates: List[RecipeCandidate],
    emphasis: str,
    count: int,
    exclude_ids: set,
    rng: Optional[random.Random] = None,
) -> List[RecipeCandidate]:
    """Greedily pick `count` **distinct** recipes best matching `emphasis`,
    excluding `exclude_ids` (already on the plan), spreading cuisine/category so
    the week isn't four pastas. Deterministic for a given input + rng."""
    # Stable ordering so ties resolve predictably (and tests are deterministic).
    eligible = sorted(
        (c for c in candidates if c.recipe_id not in exclude_ids),
        key=lambda c: (c.name.lower(), str(c.recipe_id)),
    )
    selected: List[RecipeCandidate] = []
    used_cuisine: Counter = Counter()
    used_category: Counter = Counter()
    vweight = _variety_weight(emphasis)

    while len(selected) < count and eligible:
        scored = [
            (
                _base_score(c, emphasis, rng)
                - vweight * (used_cuisine[c.cuisine_id] + used_category[c.category_id]),
                c,
            )
            for c in eligible
        ]
        leader = max(score for score, _ in scored)
        if rng is None:
            # Plain argmax; `eligible` is name-sorted, so ties resolve stably.
            best = next(c for score, c in scored if score == leader)
        else:
            # Best-first, so the cap keeps the strongest few rather than
            # whichever names happen to sort first.
            near = [
                c for score, c in sorted(scored, key=lambda t: -t[0])
                if score >= leader - NEAR_BEST_WINDOW
            ]
            best = rng.choice(near[:NEAR_BEST_MAX])
        selected.append(best)
        eligible.remove(best)
        used_cuisine[best.cuisine_id] += 1
        used_category[best.category_id] += 1
    return selected


def cost_per_serving(c: RecipeCandidate) -> Optional[float]:
    """One serving of this recipe, or None when it couldn't be priced.

    `estimated_cost` is what the whole pot costs — the recipe's own yield. A
    plan schedules *servings*, so every figure this module quotes is built from
    this one, exactly as `get_meal_plans._hydrate_cost` does for a saved week
    (R-003). Before 2026-09-12 the builder quoted the pot per entry, which
    ignored the servings control on step 1 and counted a three-day cook batch
    three times over — the budget cap was then swapping meals on that inflated
    figure (owner: *"are linked meal slots accounted for properly when
    calculating cost?"* — they were not).
    """
    if c.estimated_cost is None:
        return None
    return c.estimated_cost / float(max(c.servings or 1, 1))


def _entry_cost(c: RecipeCandidate, servings: int) -> Optional[float]:
    """What one proposed meal costs at the servings it's planned for."""
    per_serving = cost_per_serving(c)
    return None if per_serving is None else round(per_serving * servings, 2)


def apply_budget_cap(
    selected: List[RecipeCandidate],
    pool: List[RecipeCandidate],
    budget_remaining: float,
    servings_per_meal: int = 1,
    meals_per_pick: int = 1,
) -> tuple[List[RecipeCandidate], set]:
    """Best-effort: while the selection's priced cost exceeds what's left of the
    budget, swap the dearest picked recipe for the cheapest cheaper alternative
    from `pool`. Returns the (possibly changed) list + the set of swapped-in ids
    (for the budget reason chip). Never guarantees under-budget — same honest
    posture as the FU-451 swap ranker.

    The comparison is against **what the plan will cost**, not what the pots are
    worth: each pick is counted at the servings the week is being built for,
    multiplied by how many meals that one pick fills (a repeated day, or the
    run of days a batch cook spans). `meals_per_pick` is uniform because it is
    a property of the placement *shape*, which is decided before placement
    runs; a final short batch chunk therefore rounds up. Best-effort is the
    contract.

    Owner call 2026-09-12: the basis stays the **full value of the meals**
    rather than only what you'd have to buy — what changed is that the review
    step now states the to-buy figure beside it, so "under budget" is no longer
    a number with an unstated meaning.
    """

    def cost(c: RecipeCandidate) -> Optional[float]:
        per_serving = cost_per_serving(c)
        if per_serving is None:
            return None
        return per_serving * servings_per_meal * meals_per_pick

    def total(items: List[RecipeCandidate]) -> float:
        return sum((cost(x) or 0.0) for x in items)

    swapped: set = set()
    # Cheapest-first pool of priced alternatives not already selected.
    cheap_pool = sorted(
        (c for c in pool if cost(c) is not None),
        key=lambda c: cost(c),  # type: ignore[arg-type]
    )
    guard = 0
    while total(selected) > budget_remaining and guard < len(selected):
        guard += 1
        priced = [c for c in selected if cost(c) is not None]
        if not priced:
            break
        dearest = max(priced, key=lambda c: cost(c))  # type: ignore[arg-type]
        selected_ids = {s.recipe_id for s in selected}
        replacement = next(
            (c for c in cheap_pool
             if c.recipe_id not in selected_ids and cost(c) < cost(dearest)),  # type: ignore[operator]
            None,
        )
        if replacement is None:
            break
        selected[selected.index(dearest)] = replacement
        cheap_pool.remove(replacement)
        swapped.add(replacement.recipe_id)
    return selected, swapped


def _fill_one_day(pool: List[RecipeCandidate], slots: List[str]) -> List[tuple]:
    """Assign one recipe per slot for a single day, consuming `pool` (which is
    in selection-rank order). A recipe whose own `time_of_day` names the slot
    wins it (the FU-596 fix); otherwise the next-best-ranked recipe takes it.
    Returns `(candidate, slot)` pairs, short if the pool runs dry."""
    out: List[tuple] = []
    for slot in slots:
        if not pool:
            break
        index = next(
            (i for i, c in enumerate(pool) if c.time_of_day == slot),
            0,
        )
        out.append((pool.pop(index), slot))
    return out


def place_entries(
    selected: List[RecipeCandidate],
    days: List[date],
    allowed_slots: List[str],
    repeat_same_day: bool = False,
) -> List[tuple]:
    """Fill the day×slot cells the user toggled on — exactly one meal per cell.

    `repeat_same_day` builds a single day's line-up and duplicates it to every
    other selected day (the "I eat the same thing all week" case); otherwise
    each day gets its own distinct recipes. Returns `(candidate, day, slot)`
    triples in day-major order.
    """
    if not days or not allowed_slots:
        return []
    slots = allowed_slots
    if repeat_same_day:
        pattern = _fill_one_day(list(selected), slots)
        return [(c, day, slot) for day in days for (c, slot) in pattern]
    pool = list(selected)
    placements: List[tuple] = []
    for day in days:
        for (c, slot) in _fill_one_day(pool, slots):
            placements.append((c, day, slot))
    return placements


def place_entries_batched(
    selected: List[RecipeCandidate],
    days: List[date],
    allowed_slots: List[str],
    span: int,
) -> List[tuple]:
    """PROPOSAL_MEAL_PLANS_PART_2 §9 — Batch-cooker placement: within each slot,
    chunk the selected days into runs of up to `span` and cook ONE recipe across
    each run. Returns `(candidate, day, slot, cook_key)` quads — the `cook_key`
    is shared across a run's days (None for a 1-day run, which is a normal meal).
    A recipe whose `time_of_day` names the slot is preferred, mirroring
    `_fill_one_day`. Consumes `pool` so each cook uses a distinct recipe.
    """
    slots = allowed_slots
    pool = list(selected)
    placements: List[tuple] = []
    seq = 0
    for slot in slots:
        for start in range(0, len(days), max(span, 1)):
            if not pool:
                break
            chunk = days[start:start + span]
            index = next((i for i, c in enumerate(pool) if c.time_of_day == slot), 0)
            candidate = pool.pop(index)
            cook_key = f"cook{seq}" if len(chunk) > 1 else None
            seq += 1
            for day in chunk:
                placements.append((candidate, day, slot, cook_key))
    return placements


def reason_chip(c: RecipeCandidate, emphasis: str, budget_swapped: bool) -> str:
    if budget_swapped:
        return CHIP_BUDGET
    if c.expiring_count > 0:
        return CHIP_USES_EXPIRING
    if emphasis == EMPHASIS_USE_UP_STOCK and c.cookable is True:
        return CHIP_COOKABLE_NOW
    if emphasis == EMPHASIS_FAVOURITES and c.is_favourite:
        return CHIP_FAVOURITE
    if c.not_made_recently:
        return CHIP_NOT_MADE_RECENTLY
    if c.is_favourite:
        return CHIP_FAVOURITE
    return CHIP_VARIETY if emphasis == EMPHASIS_VARIETY else CHIP_PICKED


# ── Request / repo-touching orchestration ──────────────────────────────────


class AutoBuildRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # The days the user toggled on. One meal is placed per day × slot cell, so
    # there is no separate meal count — the toggles *are* the count.
    days: List[date] = Field(min_length=1, max_length=WEEK_LENGTH_DAYS)
    emphasis: str = EMPHASIS_USE_UP_STOCK
    # Empty ⇒ every household slot. A subset ⇒ just those, household-ordered.
    slot_names: List[str] = Field(default_factory=list)
    # Build one day's line-up and duplicate it to every other selected day.
    repeat_same_day: bool = False
    budget_cap: bool = False
    # Owner feedback 2026-09-03 — *"the auto builder should have affordance for
    # setting default servings for each entry, and we default that to the
    # how-many-people-we-cook-for number from settings"*. Every proposed meal
    # is created at this many servings; the review step still edits each row.
    # The household headcount lives on `AppSetting` (FU-615) and the client
    # seeds the control from it, so the default here is the neutral 1 rather
    # than a second copy of that lookup.
    default_servings: int = Field(default=1, ge=1, le=99)




def _buildable_days(requested: List[date], today: date) -> List[date]:
    """The requested days, de-duplicated and ordered, with past days dropped so
    we never schedule into yesterday (create_meal_plan rejects past entries
    anyway). The client disables past toggles; this is the server-side guard."""
    return sorted({d for d in requested if d >= today})


def _resolve_allowed_slots(requested: List[str], household_slots: List[str]) -> List[str]:
    """The pool of slots to place into: the requested subset (intersected with
    the live vocabulary, preserving household order) or all household slots."""
    if requested:
        wanted = set(requested)
        pool = [s for s in household_slots if s in wanted]
        if pool:
            return pool
    return list(household_slots)


def _planned_recipe_ids_in_range(repository, days: List[date]) -> set:
    """Recipe ids already scheduled (unconsumed) within the build's day range —
    excluded so a build never re-suggests a meal you've already planned there."""
    if not days:
        return set()
    lo, hi = min(days), max(days)
    entries = (
        repository.get(MealPlanEntry)
        .include(MealPlanEntry.Fields.RECIPE)
        .all(
            EntityField(MealPlanEntry, MealPlanEntry.Fields.SCHEDULED_FOR).gte(lo)
            & EntityField(MealPlanEntry, MealPlanEntry.Fields.SCHEDULED_FOR).lte(hi)
            & EntityField(MealPlanEntry, MealPlanEntry.Fields.CONSUMED_AT).is_null()
        )
    )
    return {e.recipe.id for e in entries if e.recipe}


def _batch_cook_span(repository: SqlAlchemyRepository) -> int:
    """`BATCH_COOK_SPAN_DAYS` for a Batch-cook-style household, else 1 (a distinct
    recipe per day — the Fresh default). Reads the install-wide cook-style flag
    (`AppSetting.batch_features_enabled`, FU-615) — the same gate the SPA reads
    via `/api/health.cooking_policy`."""
    settings = repository.get(AppSetting).all()
    if settings and settings[0].batch_features_enabled:
        return BATCH_COOK_SPAN_DAYS
    return 1


def build_candidates(repository: SqlAlchemyRepository) -> List[RecipeCandidate]:
    """Every recipe, shaped for the pure ranker.

    Extracted from `compute_auto_build` on 2026-08-30 so the meal planner's
    rail suggestions can reuse it (BRIEF_MEAL_PLANNER_RAIL_AND_SHELL §4.4).
    Both callers must build candidates the SAME way or the rail would recommend
    on different evidence than the week builder — which is the drift R-003
    exists to prevent. This is the one place that assembles them.
    """
    recipes = load_all_recipe_dtos(repository)
    # The soonest-expiry map is the cookbook's urgency ranking input; the
    # week builder only needs "how much would this rescue", so it ignores it.
    _, expiring_counts, _ = count_expiring_ingredients_per_recipe(
        repository, EXPIRING_HORIZON_DAYS,
    )
    cost_est = estimate_costs_for(repository, recipes)

    return [
        RecipeCandidate(
            recipe_id=r.recipe_id,
            name=r.name,
            time_of_day=r.time_of_day,
            cookable=r.cookable,
            expiring_count=expiring_counts.get(r.recipe_id, 0),
            is_favourite=r.is_favourite,
            plan_count=r.plan_count,
            not_made_recently=r.not_made_recently,
            cuisine_id=r.cuisine_id,
            category_id=r.category_id,
            estimated_cost=cost_est[r.recipe_id].estimated_cost,
            servings=r.servings,
            missing_stock_item_names=tuple(r.missing_stock_item_names),
        )
        for r in recipes
    ]


def compute_auto_build(
    repository: SqlAlchemyRepository,
    request: AutoBuildRequest,
    rng: Optional[random.Random] = None,
) -> AutoBuildResponse:
    today = household_today(repository)
    days = _buildable_days(request.days, today)

    household_slots = ordered_slot_names(repository)
    allowed_slots = _resolve_allowed_slots(request.slot_names, household_slots)

    candidates = build_candidates(repository)

    excluded = _planned_recipe_ids_in_range(repository, days)
    emphasis = request.emphasis if request.emphasis in _EMPHASES else EMPHASIS_USE_UP_STOCK
    # How many DISTINCT recipes to select. One per cell normally; a Batch-cook
    # household cooks one recipe per run of `span` days in a slot (§9), so it
    # needs fewer. Repeating a single day only needs one day's worth.
    per_slot = max(len(allowed_slots), 1)
    span = 1 if request.repeat_same_day else _batch_cook_span(repository)
    if request.repeat_same_day:
        wanted = per_slot
    elif span > 1 and days:
        cooks_per_slot = (len(days) + span - 1) // span  # ceil
        wanted = per_slot * cooks_per_slot
    else:
        wanted = len(days) * per_slot
    count = min(wanted, MAX_MEALS) if days else 0

    selected = select_recipes(candidates, emphasis, count, excluded, rng)

    swapped: set = set()
    money_on = money_features_enabled(repository)
    budget = household_budget(repository)
    # Measured against the period the built days start in, not today's.
    remaining = period_headroom(min(days) if days else today, repository)
    if request.budget_cap and remaining is not None:
        selected_ids = {c.recipe_id for c in selected}
        pool = [c for c in candidates if c.recipe_id not in selected_ids and c.recipe_id not in excluded]
        # How many meals one pick fills: every selected day when the line-up is
        # repeated, the batch span when a batch household cooks once for a run,
        # one otherwise.
        if request.repeat_same_day:
            meals_per_pick = max(len(days), 1)
        else:
            meals_per_pick = span
        selected, swapped = apply_budget_cap(
            selected, pool, remaining,
            servings_per_meal=request.default_servings,
            meals_per_pick=meals_per_pick,
        )

    # Which recipe lands on which day is otherwise selection rank order, so the
    # best pick always took the earliest day and a reshuffle left the week
    # looking untouched even when the set had changed. Shuffling only the
    # placement order leaves the *set* — and `_fill_one_day`'s time-of-day
    # preference — exactly as ranked.
    if rng is not None:
        rng.shuffle(selected)

    # Batch households get grouped cooks (one recipe across a run of days);
    # everyone else keeps the distinct-per-day placement (cook_key None).
    if span > 1 and not request.repeat_same_day and days:
        placements = place_entries_batched(selected, days, allowed_slots, span)
    else:
        placements = [
            (c, day, slot, None)
            for (c, day, slot) in place_entries(selected, days, allowed_slots, request.repeat_same_day)
        ]
    entries = [
        ProposedEntry(
            recipe_id=c.recipe_id,
            recipe_name=c.name,
            scheduled_for=day,
            slot=slot,
            servings=request.default_servings,
            reason_chip=reason_chip(c, emphasis, c.recipe_id in swapped),
            cookable=c.cookable,
            missing_stock_item_names=list(c.missing_stock_item_names),
            # R-058 — a dollar figure never leaves the server when money is
            # off install-wide. It used to travel and be hidden by a client
            # `v-if`, which is a render gate, not a feature gate (owner
            # 2026-09-03: *"ensure the money text and budget setting in the
            # auto builder respect feature gates"*).
            # Priced at the servings this entry is planned for, so a batch's
            # days each carry their share and sum to the one cook — see
            # `cost_per_serving`.
            estimated_cost=_entry_cost(c, request.default_servings) if money_on else None,
            cook_key=cook_key,
        )
        for (c, day, slot, cook_key) in placements
    ]

    priced = [e.estimated_cost for e in entries if e.estimated_cost is not None]
    cost_total = round(sum(priced), 2) if priced else None
    projected_over = (
        remaining is not None
        and cost_total is not None
        and cost_total > remaining
    )

    return AutoBuildResponse(
        entries=entries,
        days_used=days,
        slots_used=allowed_slots,
        cost_total=cost_total,
        budget_amount=budget.amount if budget is not None else None,
        projected_over=projected_over,
    )


def _entry_payload(e: ProposedEntry) -> dict:
    return {
        "recipe_id": str(e.recipe_id),
        "recipe_name": e.recipe_name,
        "scheduled_for": e.scheduled_for.isoformat(),
        "slot": e.slot,
        "servings": e.servings,
        "reason_chip": e.reason_chip,
        "cookable": e.cookable,
        "missing_stock_item_names": e.missing_stock_item_names,
        "estimated_cost": e.estimated_cost,
        "cook_key": e.cook_key,
    }


def _response_payload(r: AutoBuildResponse) -> dict:
    return {
        "entries": [_entry_payload(e) for e in r.entries],
        "days_used": [d.isoformat() for d in r.days_used],
        "slots_used": r.slots_used,
        "cost_total": r.cost_total,
        "budget_amount": r.budget_amount,
        "projected_over": r.projected_over,
    }


#: How many recipes the rail's "Dora suggests" chip offers. Small on purpose —
#: this is a shortlist you scan, not a second cookbook. Callers may ask for
#: fewer; they may not ask for more, or the chip stops being a shortlist.
SUGGESTIONS_DEFAULT_COUNT = 8
SUGGESTIONS_MAX_COUNT = 20


@MEAL_PLAN_ROUTER.route("/suggestions", methods=["GET"])
def week_suggestions():
    """Ranked recipe suggestions for the meal planner's rail
    (BRIEF_MEAL_PLANNER_RAIL_AND_SHELL §4.4).

    Read-only, and deliberately **no new domain logic**: it reuses
    `build_candidates` + `select_recipes` + `reason_chip`, calls the default
    emphasis, and returns the server's own frozen chip tokens rather than
    prose. The client maps token → copy; the vocabulary stays server-side
    (R-003), which is why this endpoint ships tokens and not sentences.

    `rng` is deliberately omitted, so the ranking is deterministic: a rail that
    reshuffled itself on every render would be unusable to scan.

    Recipes already planned in the focused week are excluded — suggesting
    something you have already scheduled that week is noise, and it is the same
    exclusion the week builder applies.
    """
    week_start_raw = flask_request.args.get("week_start")
    if not week_start_raw:
        return bad_request("A week_start date (YYYY-MM-DD) is required.")
    try:
        week_start = date.fromisoformat(week_start_raw)
    except ValueError:
        return bad_request("week_start must be an ISO date (YYYY-MM-DD).")

    try:
        count = int(flask_request.args.get("count", SUGGESTIONS_DEFAULT_COUNT))
    except ValueError:
        return bad_request("count must be a whole number.")
    count = max(1, min(count, SUGGESTIONS_MAX_COUNT))

    repo = SqlAlchemyRepository()
    days = [week_start + timedelta(days=offset) for offset in range(7)]

    candidates = build_candidates(repo)
    excluded = _planned_recipe_ids_in_range(repo, days)
    picked = select_recipes(
        candidates, EMPHASIS_USE_UP_STOCK, count, excluded,
    )

    return ok({
        "suggestions": [
            {
                "recipe_id": str(c.recipe_id),
                "reason_chip": reason_chip(c, EMPHASIS_USE_UP_STOCK, budget_swapped=False),
            }
            for c in picked
        ],
    })


@MEAL_PLAN_ROUTER.route("/auto-build", methods=["POST"])
@has_request_body(AutoBuildRequest)
def auto_build():
    request: AutoBuildRequest = get_request_body()

    repo = SqlAlchemyRepository()

    today = household_today(repo)
    if not _buildable_days(request.days, today):
        return bad_request("Pick at least one day that isn't in the past.")

    result = compute_auto_build(repo, request, rng=random.Random())
    _LOGGER.info(
        "Auto-build (%d day(s), emphasis=%s, repeat=%s, budget_cap=%s) proposed %d meal(s).",
        len(result.days_used), request.emphasis, request.repeat_same_day,
        request.budget_cap, len(result.entries),
    )
    return ok(_response_payload(result))
