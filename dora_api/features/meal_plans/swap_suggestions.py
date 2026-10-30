"""Meal-plan recipe swaps — two axes over one machine.

**Budget defense (FU-451)** — when a week is *projected* to blow the grocery
budget, Dora suggests cheaper recipes to bring it back under. Dora raises this
one herself, because going over budget is a fact she can see.

**Lighter alternatives (FU-637)** — "show me a lighter version of this meal",
asked for **per entry, on demand**. Deliberately never volunteered: the owner's
call is that Dora displays nutrition where it helps a decision and holds no
calorie target, so there is no threshold at which she'd start suggesting you eat
less. You ask, she answers.

Both axes share the household-affinity rule (`_affinity_for` — never push a
stranger recipe), the apply/undo path, and the `MealPlanSwapLedger`; only the
ranking metric and the reason-chip vocabulary differ.

When a meal-plan week is *projected* to blow the grocery budget, Dora suggests
cheaper **recipe** swaps to bring it back under — a non-destructive alternative
to trimming the shopping list. Preview → confirm → apply, with a deterministic
undo backed by `MealPlanSwapLedger`.

  GET  /api/meal-plans/<id>/swap-suggestions  — ranked candidates + week cost
  POST /api/meal-plans/<id>/apply-swap        — apply one swap (records ledger)
  POST /api/meal-plans/<id>/undo-swap         — reverse a ledger entry

**Scope (locked 2026-07-09):** recipe swaps only. Product/brand swaps were CUT —
they need a per-item "usual product" concept (with price) that the product owner
deliberately rejected as too much upkeep. See PROPOSAL_BUDGET_DEFENSE_SWAPS.md
scope-update note. FU-450's deal-quality signal ships independently.

Design lock: PROPOSAL_BUDGET_DEFENSE_SWAPS.md §4c / §5 / §7.

Structure mirrors `get_buy_verdict.py`: a pure ranker (`rank_recipe_swaps`,
driven by fixture data in the unit tests) + a thin repo-touching orchestrator.
"""
import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from dora_api.domain.entities.meal_plan import MealPlan
from dora_api.domain.entities.meal_plan_entry import MealPlanEntry
from dora_api.domain.entities.meal_plan_swap_ledger import MealPlanSwapLedger
from dora_api.domain.entities.recipe import Recipe
from dora_api.features.app_settings.access import money_features_enabled
from dora_api.features.budget.budget import household_budget, period_headroom
from dora_api.features.meal_plans.get_meal_plans import GetMealPlansHandler
from dora_api.features.recipes.all_recipes import load_all_recipe_dtos
from dora_api.features.recipes.recipe_cost import CostEstimate, estimate_costs_for
from dora_api.features.routers import MEAL_PLAN_ROUTER
from dora_api.infrastructure.api_response import (bad_request,
                                                  business_rule_violation,
                                                  conflict, not_found, ok,
                                                  unauthorized)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.session_user import current_user_id


_LOGGER = logging.getLogger(__name__)

WEEK_LENGTH_DAYS = 7
# Top-N across the week — more than a handful is overwhelm, not choice
# (proposal §4c). One suggestion per meal, best-saving first.
MAX_CANDIDATES = 5

# Why a candidate is a *plausible* swap at all, independent of which axis is
# ranking it: it's cookable right now, it's the same style of meal, or the
# household has cooked it before. A candidate with no affinity is a stranger and
# is never suggested (proposal §4c).
AFFINITY_COOKABLE = "cookable"
AFFINITY_SIMILAR = "similar"
AFFINITY_HOUSEHOLD_FAV = "household_fav"

# Tier ranking for affinities (higher = preferred when the metric ties).
_AFFINITY_TIER = {AFFINITY_COOKABLE: 3, AFFINITY_SIMILAR: 2, AFFINITY_HOUSEHOLD_FAV: 1}

# Frozen reason-chip vocabulary (proposal §5). The chip is decided at rank
# time and frozen on the DTO — the SPA never re-derives it. One vocabulary per
# axis: the affinity is the same fact, but "Cheaper — uses stock you have" and
# "Lighter — uses stock you have" are different sentences.
CHIP_COOKABLE = "cheaper_recipe_cookable"        # "Cheaper — uses stock you have"
CHIP_SIMILAR = "cheaper_recipe_similar"          # "Cheaper — same style meal"
CHIP_HOUSEHOLD_FAV = "cheaper_recipe_household_fav"  # "Cheaper — you've cooked it before"
_BUDGET_CHIP = {
    AFFINITY_COOKABLE: CHIP_COOKABLE,
    AFFINITY_SIMILAR: CHIP_SIMILAR,
    AFFINITY_HOUSEHOLD_FAV: CHIP_HOUSEHOLD_FAV,
}

CHIP_LIGHTER_COOKABLE = "lighter_recipe_cookable"
CHIP_LIGHTER_SIMILAR = "lighter_recipe_similar"
CHIP_LIGHTER_HOUSEHOLD_FAV = "lighter_recipe_household_fav"
_LIGHTER_CHIP = {
    AFFINITY_COOKABLE: CHIP_LIGHTER_COOKABLE,
    AFFINITY_SIMILAR: CHIP_LIGHTER_SIMILAR,
    AFFINITY_HOUSEHOLD_FAV: CHIP_LIGHTER_HOUSEHOLD_FAV,
}

# Top-N lighter alternatives for one meal. Same reasoning as MAX_CANDIDATES:
# a wall of options is overwhelm, not choice.
MAX_LIGHTER_CANDIDATES = 5


@dataclass(frozen=True, slots=True)
class RecipeSwapCandidate:
    entry_id: UUID
    entry_scheduled_for: date
    entry_slot: str
    from_recipe_id: UUID
    from_recipe_name: str
    to_recipe_id: UUID
    to_recipe_name: str
    saved: float
    reason_chip: str
    missing_ingredient_names: List[str]
    kind: str = "recipe"


@dataclass(frozen=True, slots=True)
class SwapSuggestionsResponse:
    projected_over: bool
    cost_per_week: float
    cost_per_week_priced_ratio: dict     # {"priced", "total", "unpriced_recipe_ids"}
    budget_amount: Optional[float]
    overshoot: float
    projected_after_applying_all: float
    candidates: List[RecipeSwapCandidate]


# ── Pure ranker (no repo — driven by fixtures in the unit tests) ───────


def _entry_cost(recipe, cost: Optional[CostEstimate], servings: int) -> Optional[float]:
    """Cost of cooking `recipe` for `servings` people. Scales the recipe's
    estimated cost by servings ÷ the recipe's own default servings so a swap
    is compared at the *entry's* headcount. Falls back to the raw estimate
    when the recipe has no serving count. None ⇒ unpriced."""
    if cost is None or cost.estimated_cost is None:
        return None
    base = cost.estimated_cost
    recipe_servings = getattr(recipe, "servings", None)
    if recipe_servings and recipe_servings > 0:
        return base * (servings / recipe_servings)
    return base


def _affinity_for(from_recipe, candidate) -> Optional[str]:
    """Which household affinity a candidate earns, or None if it's a "stranger"
    (not cookable-now, not tag-similar, never cooked) — those are filtered out
    so Dora never pushes an unfamiliar recipe as the answer, on either axis
    (proposal §4c household-affinity rule)."""
    if candidate.cookable is True:
        return AFFINITY_COOKABLE
    same_cuisine = (
        candidate.cuisine_id is not None
        and candidate.cuisine_id == from_recipe.cuisine_id
    )
    same_category = (
        candidate.category_id is not None
        and candidate.category_id == from_recipe.category_id
    )
    if same_cuisine or same_category:
        return AFFINITY_SIMILAR
    if getattr(candidate, "last_made_on", None) is not None:
        return AFFINITY_HOUSEHOLD_FAV
    return None


def rank_recipe_swaps(
    week_entries: list,
    recipes_by_id: dict,
    cost_by_id: dict,
    planned_recipe_ids: set,
) -> List[RecipeSwapCandidate]:
    """Pure two-pass-A ranker. For each uncooked week entry, find the single
    best cheaper recipe swap; rank the winners across the week by saving.

    * `week_entries` — entry objects with `.meal_plan_entry_id`, `.recipe_id`,
      `.recipe_name`, `.scheduled_for`, `.slot`, `.servings`, `.consumed_at`.
    * `recipes_by_id` — `recipe_id → RecipeDto` (cookable, tags, servings,
      last_made_on, missing_stock_item_names).
    * `cost_by_id` — `recipe_id → CostEstimate`.
    * `planned_recipe_ids` — recipes already on the plan; never suggested
      (avoids "cook this Tuesday AND Thursday").
    """
    winners: List[RecipeSwapCandidate] = []

    for entry in week_entries:
        if entry.consumed_at is not None:
            continue  # ate it, can't swap it
        from_recipe = recipes_by_id.get(entry.recipe_id)
        if from_recipe is None:
            continue
        from_cost = _entry_cost(from_recipe, cost_by_id.get(entry.recipe_id), entry.servings)
        if from_cost is None:
            continue  # no baseline → can't rank a saving honestly

        best: Optional[RecipeSwapCandidate] = None
        best_tier = -1
        for rid, candidate in recipes_by_id.items():
            if rid == entry.recipe_id or rid in planned_recipe_ids:
                continue
            cand_cost = _entry_cost(candidate, cost_by_id.get(rid), entry.servings)
            if cand_cost is None or cand_cost >= from_cost:
                continue
            affinity = _affinity_for(from_recipe, candidate)
            if affinity is None:
                continue
            chip = _BUDGET_CHIP[affinity]
            saved = round(from_cost - cand_cost, 2)
            if saved <= 0:
                continue
            tier = _AFFINITY_TIER[affinity]
            # Best per entry: most saved, then best chip tier.
            if best is None or (saved, tier) > (best.saved, best_tier):
                best = RecipeSwapCandidate(
                    entry_id=entry.meal_plan_entry_id,
                    entry_scheduled_for=entry.scheduled_for,
                    entry_slot=entry.slot,
                    from_recipe_id=entry.recipe_id,
                    from_recipe_name=entry.recipe_name,
                    to_recipe_id=rid,
                    to_recipe_name=candidate.name,
                    saved=saved,
                    reason_chip=chip,
                    missing_ingredient_names=list(
                        getattr(candidate, "missing_stock_item_names", []) or []
                    ),
                )
                best_tier = tier
        if best is not None:
            winners.append(best)

    # Rank across the week: biggest saving first, then chip tier.
    _budget_tier = {chip: _AFFINITY_TIER[a] for a, chip in _BUDGET_CHIP.items()}
    winners.sort(
        key=lambda c: (c.saved, _budget_tier[c.reason_chip]), reverse=True,
    )
    return winners[:MAX_CANDIDATES]


@dataclass(frozen=True, slots=True)
class LighterSwapCandidate:
    """FU-637 — a lighter alternative for one planned meal."""
    to_recipe_id: UUID
    to_recipe_name: str
    kcal_per_serving: float
    saved_kcal: float
    reason_chip: str
    missing_ingredient_names: List[str]


def rank_lighter_swaps(
    from_recipe,
    recipes_by_id: dict,
    planned_recipe_ids: set,
) -> List[LighterSwapCandidate]:
    """Pure ranker: recipes with fewer calories per serving than *from_recipe*,
    best reduction first, ties broken by household affinity.

    Both sides must carry a **reliable** figure (`kcal_is_reliable`). Ranking a
    meal against a one-of-eight estimate would answer "which is lighter?" with
    arithmetic on missing data — the R-041 rule, applied where it bites hardest,
    since the whole point of the question is to trust the comparison.

    Recipes already on the plan are skipped, same as the budget axis: swapping
    Tuesday's dinner for Thursday's isn't variety.
    """
    baseline = getattr(from_recipe, "kcal_per_serving", None)
    if baseline is None or not getattr(from_recipe, "kcal_is_reliable", False):
        return []

    out: List[LighterSwapCandidate] = []
    for rid, candidate in recipes_by_id.items():
        if rid == from_recipe.recipe_id or rid in planned_recipe_ids:
            continue
        kcal = getattr(candidate, "kcal_per_serving", None)
        if kcal is None or not getattr(candidate, "kcal_is_reliable", False):
            continue
        if kcal >= baseline:
            continue
        affinity = _affinity_for(from_recipe, candidate)
        if affinity is None:
            continue
        out.append(LighterSwapCandidate(
            to_recipe_id = rid,
            to_recipe_name = candidate.name,
            kcal_per_serving = kcal,
            saved_kcal = round(baseline - kcal),
            reason_chip = _LIGHTER_CHIP[affinity],
            missing_ingredient_names = list(
                getattr(candidate, "missing_stock_item_names", []) or []
            ),
        ))

    _lighter_tier = {chip: _AFFINITY_TIER[a] for a, chip in _LIGHTER_CHIP.items()}
    out.sort(key=lambda c: (c.saved_kcal, _lighter_tier[c.reason_chip]), reverse=True)
    return out[:MAX_LIGHTER_CANDIDATES]


# ── Repo-touching orchestration ────────────────────────────────────────


def _week_entries(plan_dto, start: date):
    end = date.fromordinal(start.toordinal() + WEEK_LENGTH_DAYS)
    return [
        e for e in plan_dto.entries
        if start <= e.scheduled_for < end and e.consumed_at is None
    ]


def compute_suggestions(
    repository: SqlAlchemyRepository, meal_plan_id: UUID,
) -> Optional[SwapSuggestionsResponse]:
    """Returns None when the plan doesn't exist. Returns a zeroed response
    (projected_over False, no candidates) when money features are off — the
    surface is hidden client-side, this is the defensive server mirror.
    Budget is the household value (moved off User)."""
    plan_dto = GetMealPlansHandler(repository).handle_by_id(meal_plan_id)
    if plan_dto is None:
        return None

    if not money_features_enabled(repository):
        return SwapSuggestionsResponse(
            projected_over=False, cost_per_week=0.0,
            cost_per_week_priced_ratio={"priced": 0, "total": 0, "unpriced_recipe_ids": []},
            budget_amount=None, overshoot=0.0,
            projected_after_applying_all=0.0, candidates=[],
        )

    recipes = load_all_recipe_dtos(repository)
    recipes_by_id = {r.recipe_id: r for r in recipes}
    cost_by_id = estimate_costs_for(repository, recipes)

    week_entries = _week_entries(plan_dto, plan_dto.start_date)
    priced = 0
    unpriced_recipe_ids: list = []
    cost_per_week = 0.0
    for e in week_entries:
        recipe = recipes_by_id.get(e.recipe_id)
        ecost = _entry_cost(recipe, cost_by_id.get(e.recipe_id), e.servings) if recipe else None
        if ecost is None:
            unpriced_recipe_ids.append(str(e.recipe_id))
        else:
            cost_per_week += ecost
            priced += 1
    cost_per_week = round(cost_per_week, 2)

    budget = household_budget(repository)
    budget_amount = budget.amount if budget is not None else None
    # The money left in the period the plan's week falls in, not today's —
    # planning next week is measured against next week's budget.
    remaining = period_headroom(plan_dto.start_date, repository)
    projected_over = remaining is not None and cost_per_week > remaining
    overshoot = round(max(0.0, cost_per_week - remaining), 2) if remaining is not None else 0.0

    candidates: List[RecipeSwapCandidate] = []
    if projected_over:
        planned_recipe_ids = {e.recipe_id for e in plan_dto.entries}
        # A cook-batch day can't be swapped on its own (FU-956), so it is
        # never offered; its cost still counts toward the week above.
        candidates = rank_recipe_swaps(
            [e for e in week_entries if e.cook_batch_id is None],
            recipes_by_id, cost_by_id, planned_recipe_ids,
        )
    total_saved = round(sum(c.saved for c in candidates), 2)

    return SwapSuggestionsResponse(
        projected_over=projected_over,
        cost_per_week=cost_per_week,
        cost_per_week_priced_ratio={
            "priced": priced,
            "total": len(week_entries),
            "unpriced_recipe_ids": unpriced_recipe_ids,
        },
        budget_amount=budget_amount,
        overshoot=overshoot,
        projected_after_applying_all=round(cost_per_week - total_saved, 2),
        candidates=candidates,
    )


def _candidate_payload(c: RecipeSwapCandidate) -> dict:
    return {
        "kind": c.kind,
        "entry_id": str(c.entry_id),
        "entry_scheduled_for": c.entry_scheduled_for.isoformat(),
        "entry_slot": c.entry_slot,
        "from_recipe_id": str(c.from_recipe_id),
        "from_recipe_name": c.from_recipe_name,
        "to_recipe_id": str(c.to_recipe_id),
        "to_recipe_name": c.to_recipe_name,
        "saved": c.saved,
        "reason_chip": c.reason_chip,
        "missing_ingredient_names": c.missing_ingredient_names,
    }


def _suggestions_payload(r: SwapSuggestionsResponse) -> dict:
    return {
        "projected_over": r.projected_over,
        "cost_per_week": r.cost_per_week,
        "cost_per_week_priced_ratio": r.cost_per_week_priced_ratio,
        "budget_amount": r.budget_amount,
        "overshoot": r.overshoot,
        "projected_after_applying_all": r.projected_after_applying_all,
        "candidates": [_candidate_payload(c) for c in r.candidates],
    }


# ── Apply / undo ───────────────────────────────────────────────────────


# Why a swap was applied. Closed set (R-010); recorded on the ledger so the
# audit trail says which question the user was answering.
SWAP_REASON_BUDGET = "budget"
SWAP_REASON_LIGHTER = "lighter"
SWAP_REASONS = (SWAP_REASON_BUDGET, SWAP_REASON_LIGHTER)


class ApplySwapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = "recipe"
    entry_id: UUID
    to_recipe_id: UUID
    # FU-637 — which axis suggested this. Defaults to the original budget axis
    # so existing callers are unchanged. It decides which feature gate applies:
    # a lighter swap has nothing to do with money, and blocking it on
    # `money_enabled` would have been a gate inherited by accident.
    reason: str = SWAP_REASON_BUDGET
    # Optional stale-guard: the recipe the client believed the entry held. When
    # present and it no longer matches, the apply 409s so a stale card can't
    # silently swap the wrong meal (proposal §11 verify).
    expected_from_recipe_id: UUID | None = None


class UndoSwapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    swap_ledger_id: UUID


def _load_plan_with_entries(repository: SqlAlchemyRepository, meal_plan_id: UUID):
    return (
        repository.get(MealPlan)
        .include(MealPlan.Fields.ENTRIES)
        .then_include(MealPlanEntry.Fields.RECIPE)
        .by_id(meal_plan_id)
    )


def _recompute_after(repository, meal_plan_id) -> tuple[float, bool]:
    resp = compute_suggestions(repository, meal_plan_id)
    if resp is None:
        return 0.0, False
    return resp.cost_per_week, resp.projected_over


# ── Endpoints ──────────────────────────────────────────────────────────


@MEAL_PLAN_ROUTER.route("/<uuid:meal_plan_id>/swap-suggestions", methods=["GET"])
def get_swap_suggestions(meal_plan_id: UUID):
    repo = SqlAlchemyRepository()
    result = compute_suggestions(repo, meal_plan_id)
    if result is None:
        return not_found(MealPlan.__name__, meal_plan_id)
    return ok(_suggestions_payload(result))


def compute_lighter_alternatives(
    repository: SqlAlchemyRepository, meal_plan_id: UUID, entry_id: UUID,
) -> Optional[dict]:
    """FU-637 — lighter alternatives for one planned meal. None ⇒ plan or entry
    not found. Returns an empty candidate list (not an error) when nutrition is
    off or the meal has no reliable figure — "nothing to offer" is a normal
    answer here, not a failure."""
    from dora_api.domain.entities.app_setting import NUTRITION_MODE_OFF
    from dora_api.features.app_settings.access import get_or_create_app_setting
    from dora_api.features.nutrition.sources import nutrition_mode

    plan_dto = GetMealPlansHandler(repository).handle_by_id(meal_plan_id)
    if plan_dto is None:
        return None
    entry = next(
        (e for e in plan_dto.entries if e.meal_plan_entry_id == entry_id), None
    )
    if entry is None:
        return None

    empty = {
        "entry_id": str(entry_id),
        "from_recipe_id": str(entry.recipe_id),
        "from_recipe_name": entry.recipe_name,
        "from_kcal_per_serving": entry.kcal_per_serving,
        "candidates": [],
    }
    if nutrition_mode(get_or_create_app_setting(repository)) == NUTRITION_MODE_OFF:
        return empty
    # One day of a cook batch can't take a different recipe (FU-956).
    if entry.cook_batch_id is not None:
        return empty

    recipes = load_all_recipe_dtos(repository)
    recipes_by_id = {r.recipe_id: r for r in recipes}
    from_recipe = recipes_by_id.get(entry.recipe_id)
    if from_recipe is None:
        return empty

    candidates = rank_lighter_swaps(
        from_recipe, recipes_by_id, {e.recipe_id for e in plan_dto.entries},
    )
    return {
        **empty,
        "from_kcal_per_serving": from_recipe.kcal_per_serving,
        "candidates": [
            {
                "to_recipe_id": str(c.to_recipe_id),
                "to_recipe_name": c.to_recipe_name,
                "kcal_per_serving": c.kcal_per_serving,
                "saved_kcal": c.saved_kcal,
                "reason_chip": c.reason_chip,
                "missing_ingredient_names": c.missing_ingredient_names,
            }
            for c in candidates
        ],
    }


@MEAL_PLAN_ROUTER.route("/<uuid:meal_plan_id>/lighter-alternatives", methods=["GET"])
def get_lighter_alternatives(meal_plan_id: UUID):
    """On-demand, per entry — never volunteered (see the module docstring)."""
    # Aliased: this module binds the *parsed body* to `request` in the apply /
    # undo handlers (house convention), so flask's own object needs a name of
    # its own here rather than a module-level import that would read ambiguously.
    from flask import request as flask_request

    raw_entry_id = flask_request.args.get("entry_id")
    try:
        entry_id = UUID(str(raw_entry_id))
    except (TypeError, ValueError):
        return bad_request("entry_id must be a valid id.")
    result = compute_lighter_alternatives(SqlAlchemyRepository(), meal_plan_id, entry_id)
    if result is None:
        return not_found(MealPlanEntry.__name__, entry_id)
    return ok(result)


@MEAL_PLAN_ROUTER.route("/<uuid:meal_plan_id>/apply-swap", methods=["POST"])
@has_request_body(ApplySwapRequest)
def apply_swap(meal_plan_id: UUID):
    repo = SqlAlchemyRepository()
    user_id = current_user_id()
    if user_id is None:
        return unauthorized()
    request: ApplySwapRequest = get_request_body()
    if request.kind != "recipe":
        return bad_request("Only recipe swaps are supported.")
    if request.reason not in SWAP_REASONS:
        return bad_request("Unknown swap reason.")

    if request.reason == SWAP_REASON_BUDGET and not money_features_enabled(repo):
        return business_rule_violation("Money features are off; swaps are unavailable.")

    plan = _load_plan_with_entries(repo, meal_plan_id)
    if plan is None:
        return not_found(MealPlan.__name__, meal_plan_id)
    entry = next(
        (e for e in (plan.entries or []) if e.id == request.entry_id), None
    )
    if entry is None:
        return not_found(MealPlanEntry.__name__, request.entry_id)
    if entry.consumed_at is not None:
        return business_rule_violation("That meal has already been cooked, so it can't be swapped.")
    # FU-956 (owner, 2026-10-30): a cook batch is one recipe cooked once and
    # eaten over several days, so changing one day's recipe would leave the
    # batch mixing recipes (the rule `validate_cook_groups` enforces on every
    # plan save) and its `CookBatch.recipe_id` pointing at the old one.
    if entry.cook_batch_id is not None:
        return business_rule_violation(
            "That meal is one day of a cook batch, so it can't be swapped on "
            "its own. Take it out of the batch first, or change the whole cook "
            "in the planner."
        )

    from_recipe_id = entry.recipe.id if entry.recipe else None
    if (
        request.expected_from_recipe_id is not None
        and from_recipe_id != request.expected_from_recipe_id
    ):
        # Stale card — the week drifted since the suggestion was fetched.
        return conflict("This suggestion is out of date. Refresh and try again.")

    to_recipe = repo.get(Recipe).by_id(request.to_recipe_id)
    if to_recipe is None:
        return not_found(Recipe.__name__, request.to_recipe_id)

    entry.recipe = to_recipe
    ledger = MealPlanSwapLedger(
        meal_plan_id=meal_plan_id if isinstance(meal_plan_id, UUID) else UUID(str(meal_plan_id)),
        applied_by_user_id=user_id,
        applied_at=datetime.now(timezone.utc),
        kind="recipe",
        payload_json=json.dumps({
            "entry_id": str(entry.id),
            "from_recipe_id": str(from_recipe_id) if from_recipe_id else None,
            "from_servings": entry.servings,
            "reason": request.reason,
        }),
    )
    repo.add(ledger)
    repo.save_changes()

    new_cost, new_over = _recompute_after(repo, meal_plan_id)
    return ok({
        "swap_ledger_id": str(ledger.id),
        "new_cost_per_week": new_cost,
        "new_projected_over": new_over,
    })


@MEAL_PLAN_ROUTER.route("/<uuid:meal_plan_id>/undo-swap", methods=["POST"])
@has_request_body(UndoSwapRequest)
def undo_swap(meal_plan_id: UUID):
    repo = SqlAlchemyRepository()
    user_id = current_user_id()
    if user_id is None:
        return unauthorized()

    request: UndoSwapRequest = get_request_body()
    ledger = repo.get(MealPlanSwapLedger).by_id(request.swap_ledger_id)
    if ledger is None:
        return not_found(MealPlanSwapLedger.__name__, request.swap_ledger_id)
    if ledger.undone:
        return business_rule_violation("That swap has already been undone.")

    payload = json.loads(ledger.payload_json)
    from_recipe_id = payload.get("from_recipe_id")
    entry_id = payload.get("entry_id")
    if not from_recipe_id or not entry_id:
        return business_rule_violation("This swap can't be undone (missing prior state).")

    plan = _load_plan_with_entries(repo, meal_plan_id)
    if plan is None:
        return not_found(MealPlan.__name__, meal_plan_id)
    entry = next(
        (e for e in (plan.entries or []) if str(e.id) == entry_id), None
    )
    if entry is None:
        return not_found(MealPlanEntry.__name__, UUID(entry_id))

    from_recipe = repo.get(Recipe).by_id(UUID(from_recipe_id))
    if from_recipe is None:
        return business_rule_violation("The original recipe no longer exists.")

    entry.recipe = from_recipe
    ledger.undone = True
    ledger.undone_at = datetime.now(timezone.utc)
    repo.save_changes()

    new_cost, new_over = _recompute_after(repo, meal_plan_id)
    return ok({
        "new_cost_per_week": new_cost,
        "new_projected_over": new_over,
    })
