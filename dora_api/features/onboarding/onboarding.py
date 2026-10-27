"""F1 — first-run wizard backend (`/welcome`).

  GET  /api/onboarding/state      — {first_user}: is this the install's first account
  GET  /api/onboarding/catalog    — the bundled groups / location tree / starter packs
  POST /api/onboarding/seed       — create picked default groups + locations, plus the
                                    user's own group / zone names, in one unit of work
  POST /api/onboarding/seed-items — create stock items by name (pack picks + own items)
  POST /api/onboarding/seed-demo  — one-off demo recipe + this week's meal-plan entry
  POST /api/onboarding/complete   — stamp `onboarding_completed_at`
  POST /api/onboarding/restart    — clear it (About → "Run the welcome tour again")

Seed catalogues live as JSON next to this file so designers can edit without
touching Python; they are read once per process. Every seed call is idempotent:
a second call won't duplicate groups / locations / items that already exist by
name (the visible label, never an id — a user can re-import without thinking
about the bookkeeping).
"""
import functools
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from dora_api.domain.entities.meal_plan import MealPlan
from dora_api.domain.entities.meal_plan_entry import MealPlanEntry
from dora_api.domain.entities.meal_slot import MealSlot
from dora_api.domain.entities.recipe import Recipe
from dora_api.domain.entities.recipe_ingredient import RecipeIngredient
from dora_api.domain.entities.stock_group import StockGroup
from dora_api.domain.entities.stock_item import StockItem
from dora_api.domain.entities.stock_level import StockLevel
from dora_api.domain.entities.stock_location import StockLocation
from dora_api.domain.entities.user import User
from dora_api.domain.stock_status import StockStatus, level_for_status
from dora_api.features.app_settings.clock import household_today
from dora_api.features.routers import ONBOARDING_ROUTER
from dora_api.infrastructure.api_response import (no_content, not_found, ok,
                                                  unauthorized)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository
from dora_api.infrastructure.session_user import current_user_id


_LOGGER = logging.getLogger(__name__)
_SEED_DIR = Path(__file__).parent


@functools.lru_cache(maxsize=None)
def _load_seed(name: str) -> list[dict[str, Any]]:
    """Read a bundled seed JSON once per process (the files are bundled and
    immutable at runtime — finalisation 14-R20). Callers treat the result as
    read-only. Defensive — bad JSON shouldn't 500 the wizard."""
    try:
        with open(_SEED_DIR / name, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except FileNotFoundError:
        _LOGGER.warning("Seed file missing: %s", name)
        return []
    except json.JSONDecodeError as exc:
        _LOGGER.error("Seed file invalid JSON (%s): %s", name, exc)
        return []


# ─── State ───────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class OnboardingStateDto:
    # The one fact the wizard reads: the first account gets the household
    # (features) step. `completed` / `completed_at` ride `/auth/me`, and the
    # FU-189 `store_status` hint had no reader — both dropped (finalisation
    # 14-R12, R-057).
    first_user: bool


class GetOnboardingStateHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self) -> OnboardingStateDto:
        return OnboardingStateDto(first_user=self.repository.get(User).count() <= 1)


@ONBOARDING_ROUTER.route("/state", methods=["GET"])
def get_onboarding_state():
    user_id = current_user_id()
    if user_id is None:
        return unauthorized("Sign in to use the onboarding endpoints.")
    repo = SqlAlchemyRepository()
    user = repo.get(User).by_id(user_id)
    if user is None:
        return not_found("User", user_id)
    return ok(GetOnboardingStateHandler(repo).handle())


# ─── Complete + restart ──────────────────────────────────────────────


@ONBOARDING_ROUTER.route("/complete", methods=["POST"])
def complete_onboarding():
    user_id = current_user_id()
    if user_id is None:
        return unauthorized("Sign in to use the onboarding endpoints.")
    repo = SqlAlchemyRepository()
    user = repo.get(User).by_id(user_id)
    if user is None:
        return not_found("User", user_id)
    user.onboarding_completed_at = datetime.now(timezone.utc)
    repo.save_changes()
    _LOGGER.info("Onboarding completed for user %s", user_id)
    return no_content()


@ONBOARDING_ROUTER.route("/restart", methods=["POST"])
def restart_onboarding():
    user_id = current_user_id()
    if user_id is None:
        return unauthorized("Sign in to use the onboarding endpoints.")
    repo = SqlAlchemyRepository()
    user = repo.get(User).by_id(user_id)
    if user is None:
        return not_found("User", user_id)
    user.onboarding_completed_at = None
    repo.save_changes()
    _LOGGER.info("Onboarding reset requested by user %s", user_id)
    return no_content()


# ─── Seed catalogues ─────────────────────────────────────────────────


def _stocked_level(levels: list[StockLevel]) -> StockLevel:
    """The Stocked level by status identity (`level_for_status`), the one
    authority for "which level is this role" — two sites used to take
    `sorted(levels)[0]` (finalisation 14-R6)."""
    return level_for_status(levels, StockStatus.STOCKED) or sorted(levels, key=lambda lvl: lvl.sequence)[0]


def _demo_slot_name(repository: Repository) -> str:
    """Meal slots are a user-editable vocabulary (`MEAL_SLOT_NAMES` is the
    seed, not the law): the demo entry takes the install's "Dinner" slot if
    it still exists, else the last slot by sequence (finalisation 14-R7)."""
    slots = sorted(repository.get(MealSlot).all(), key=lambda s: s.sequence)
    for slot in slots:
        if slot.name.strip().lower() == "dinner":
            return slot.name
    return slots[-1].name if slots else "Dinner"


class SeedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    groups: bool = False
    locations: bool = False
    # optional per-name filter over the bundled defaults. When
    # None (default) and the corresponding bool is True, seed all defaults
    # (original behaviour). When a list is provided, seed only those
    # defaults whose name (or path, for locations) is in the list.
    #
    # Location paths use the form "Zone" for a top-level zone alone, or
    # "Zone/Child" for a child under it. Selecting a child implicitly
    # creates its parent zone (needed for the FK), even when the parent's
    # own path is not in the list.
    group_names: list[str] | None = None
    location_paths: list[str] | None = None
    # The user's *own* entries from the stock step, created in the same unit
    # of work as the defaults and deduped by name like them. The wizard used
    # to create these client-side with per-name existence checks after the
    # seed had committed (finalisation 14-R19). Own locations are top-level
    # zones.
    extra_group_names: list[str] | None = None
    extra_location_names: list[str] | None = None


@dataclass(frozen=True, slots=True)
class SeedResultDto:
    groups_created: int
    groups_skipped: int
    locations_created: int
    locations_skipped: int


class SeedHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: SeedRequest) -> SeedResultDto:
        groups_created = groups_skipped = 0
        locations_created = locations_skipped = 0

        if request.groups:
            seed_groups = _load_seed("default_stock_groups.json")
            group_filter: set[str] | None = (
                {n.strip().lower() for n in request.group_names if (n or "").strip()}
                if request.group_names is not None
                else None
            )
            existing = {
                g.name.strip().lower()
                for g in self.repository.get(StockGroup).all()
            }
            for entry in seed_groups:
                name = (entry.get("name") or "").strip()
                if not name:
                    continue
                if group_filter is not None and name.lower() not in group_filter:
                    continue
                if name.lower() in existing:
                    groups_skipped += 1
                    continue
                self.repository.add(StockGroup(name=name))
                existing.add(name.lower())
                groups_created += 1

        for raw in request.extra_group_names or []:
            name = (raw or "").strip()
            if not name:
                continue
            if "existing" not in locals():
                existing = {g.name.strip().lower() for g in self.repository.get(StockGroup).all()}
            if name.lower() in existing:
                groups_skipped += 1
                continue
            self.repository.add(StockGroup(name=name))
            existing.add(name.lower())
            groups_created += 1

        wants_locations = request.locations or bool(request.extra_location_names)
        if wants_locations:
            seed_locations = _load_seed("default_locations.json")
            path_filter: set[str] | None = (
                {p.strip().lower() for p in request.location_paths if (p or "").strip()}
                if request.location_paths is not None
                else None
            )
            # Match the dedupe semantics of groups: skip locations whose
            # (parent_id, name) pair already exists. Top-level zones are
            # keyed by name alone.
            existing_pairs: set[tuple[str | None, str]] = set()
            # Top-level zones by name, built once from the same read — the
            # loop used to re-scan `StockLocation.all()` per existing zone
            # (finalisation 14-R25).
            existing_zones: dict[str, StockLocation] = {}
            for loc in self.repository.get(StockLocation).all():
                key_parent = str(loc.parent_id) if loc.parent_id else None
                existing_pairs.add((key_parent, loc.name.strip().lower()))
                if loc.parent_id is None:
                    existing_zones[loc.name.strip().lower()] = loc

            for zone in (seed_locations if request.locations else []):
                z_name = (zone.get("name") or "").strip()
                z_kind = zone.get("kind") or "zone"
                if not z_name:
                    continue

                # Compute the set of child names under this zone that the
                # filter accepts (empty when no filter). A zone is created
                # if it's directly named OR any of its children is named.
                zone_path = z_name.lower()
                child_entries = zone.get("children") or []
                accepted_children: list[dict[str, Any]] = []
                if path_filter is None:
                    accepted_children = list(child_entries)
                    zone_wanted = True
                else:
                    zone_wanted = zone_path in path_filter
                    for child in child_entries:
                        c_name = (child.get("name") or "").strip()
                        if not c_name:
                            continue
                        c_path = f"{zone_path}/{c_name.lower()}"
                        if c_path in path_filter:
                            accepted_children.append(child)

                # If the zone isn't named and no accepted children under
                # it, skip this zone entirely.
                if not zone_wanted and not accepted_children:
                    continue

                key = (None, z_name.lower())
                if key in existing_pairs:
                    zone_entity = existing_zones.get(z_name.lower())
                    # Only count as "skipped" when the zone itself was
                    # explicitly requested — otherwise the zone is a
                    # silent prerequisite for the accepted children.
                    if zone_wanted:
                        locations_skipped += 1
                else:
                    zone_entity = StockLocation(
                        name=z_name, kind=z_kind, parent_id=None, sequence=0
                    )
                    self.repository.add(zone_entity)
                    # FU-512 unit-of-work: child StockLocation rows below
                    # set `parent_id = zone_entity.id`. `add()` assigns the
                    # UUID client-side, but the child insert is a Core-level
                    # `db.session.execute(...)` in nothing else in this loop —
                    # the classic mapper has no `relationship()` between
                    # StockLocation self-refs, so SQLite `PRAGMA
                    # foreign_keys=ON` can fire on the child before the
                    # parent hits the wire. Flush the parent, don't commit
                    # (see the local contract in
                    # `sqlalchemy_repository.py:57-67`).
                    self.repository.flush()
                    existing_pairs.add(key)
                    existing_zones[z_name.lower()] = zone_entity
                    locations_created += 1

                for idx, child in enumerate(accepted_children):
                    c_name = (child.get("name") or "").strip()
                    c_kind = child.get("kind") or "area"
                    if not c_name or zone_entity is None:
                        continue
                    pair = (str(zone_entity.id), c_name.lower())
                    if pair in existing_pairs:
                        locations_skipped += 1
                        continue
                    self.repository.add(StockLocation(
                        name=c_name,
                        kind=c_kind,
                        parent_id=zone_entity.id,
                        sequence=idx,
                    ))
                    existing_pairs.add(pair)
                    locations_created += 1

            for raw in request.extra_location_names or []:
                name = (raw or "").strip()
                if not name:
                    continue
                if (None, name.lower()) in existing_pairs:
                    locations_skipped += 1
                    continue
                self.repository.add(StockLocation(name=name, kind="zone", parent_id=None, sequence=0))
                existing_pairs.add((None, name.lower()))
                locations_created += 1

        # FU-512 unit-of-work: single final commit across groups + locations.
        self.repository.save_changes()

        return SeedResultDto(
            groups_created=groups_created,
            groups_skipped=groups_skipped,
            locations_created=locations_created,
            locations_skipped=locations_skipped,
        )


@ONBOARDING_ROUTER.route("/seed", methods=["POST"])
@has_request_body(SeedRequest)
def seed_onboarding():
    user_id = current_user_id()
    if user_id is None:
        return unauthorized("Sign in to use the onboarding endpoints.")
    _Request: SeedRequest = get_request_body()
    if not (_Request.groups or _Request.locations or _Request.extra_group_names or _Request.extra_location_names):
        # Nothing requested — return zero-counts rather than 400 so the
        # frontend can call this unconditionally as "advance step 3".
        return ok(SeedResultDto(0, 0, 0, 0))
    result = SeedHandler(SqlAlchemyRepository()).handle(_Request)
    _LOGGER.info(
        "Onboarding seed (user %s): groups +%d/-%d, locations +%d/-%d",
        user_id,
        result.groups_created, result.groups_skipped,
        result.locations_created, result.locations_skipped,
    )
    return ok(result)


# ─── Starter catalogue (C-5.5) ───────────────────────────────────────
# The default groups/locations + starter packs the wizard previews and lets
# the user pick from. Served from the bundled JSON (the seed source of truth)
# so the client never duplicates the catalogue (R-003).


@dataclass(frozen=True, slots=True)
class LocationNodeDto:
    name: str
    kind: str
    children: list["LocationNodeDto"]


@dataclass(frozen=True, slots=True)
class StarterPackItemDto:
    name: str
    group: str | None
    location: str | None


@dataclass(frozen=True, slots=True)
class StarterPackDto:
    key: str
    label: str
    blurb: str
    items: list[StarterPackItemDto]


@dataclass(frozen=True, slots=True)
class OnboardingCatalogDto:
    groups: list[str]
    locations: list[LocationNodeDto]
    packs: list[StarterPackDto]


def _location_nodes(raw: list[dict[str, Any]]) -> list[LocationNodeDto]:
    nodes: list[LocationNodeDto] = []
    for zone in raw:
        name = (zone.get("name") or "").strip()
        if not name:
            continue
        nodes.append(LocationNodeDto(
            name=name,
            kind=zone.get("kind") or "zone",
            children=_location_nodes(zone.get("children") or []),
        ))
    return nodes


def _starter_packs() -> list[StarterPackDto]:
    packs: list[StarterPackDto] = []
    for pack in _load_seed("starter_packs.json"):
        key = (pack.get("key") or "").strip()
        if not key:
            continue
        items = [
            StarterPackItemDto(
                name=(it.get("name") or "").strip(),
                group=(it.get("group") or None),
                location=(it.get("location") or None),
            )
            for it in (pack.get("items") or [])
            if (it.get("name") or "").strip()
        ]
        packs.append(StarterPackDto(
            key=key,
            label=pack.get("label") or key,
            blurb=pack.get("blurb") or "",
            items=items,
        ))
    return packs


@ONBOARDING_ROUTER.route("/catalog", methods=["GET"])
def onboarding_catalog():
    user_id = current_user_id()
    if user_id is None:
        return unauthorized("Sign in to use the onboarding endpoints.")
    groups = [
        (g.get("name") or "").strip()
        for g in _load_seed("default_stock_groups.json")
        if (g.get("name") or "").strip()
    ]
    return ok(OnboardingCatalogDto(
        groups=groups,
        locations=_location_nodes(_load_seed("default_locations.json")),
        packs=_starter_packs(),
    ))


# ─── Seed stock items by name (C-5.5) ────────────────────────────────
# Used for both the starter-pack picks and the wizard's first stock items.
# Resolves group / location by NAME (against whatever's been created by the
# groups/locations seed, which the wizard applies first) — this is what lets
# items reference seeded groups that don't have ids yet at pick time (FU-191).
# Idempotent: skips items whose name already exists (same discipline as the
# groups/locations seed).


class SeedItemDto(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    group_name: str | None = None
    location_name: str | None = None


class SeedItemsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[SeedItemDto] = []


@dataclass(frozen=True, slots=True)
class SeedItemsResultDto:
    created: int
    skipped: int


class SeedItemsHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: SeedItemsRequest) -> SeedItemsResultDto:
        if not request.items:
            return SeedItemsResultDto(0, 0)

        levels = self.repository.get(StockLevel).all()
        if not levels:
            # No stock levels configured — can't create items. Migrations seed
            # these, so this only happens on a pathological DB; fail soft.
            _LOGGER.warning("Seed-items skipped: no stock levels configured.")
            return SeedItemsResultDto(0, 0)
        stocked = _stocked_level(levels)

        existing = {
            item.name.strip().lower()
            for item in self.repository.get(StockItem).all()
        }
        groups = {
            g.name.strip().lower(): g
            for g in self.repository.get(StockGroup).all()
        }
        locations = {
            loc.name.strip().lower(): loc
            for loc in self.repository.get(StockLocation).all()
        }

        now = datetime.now(timezone.utc)
        created = skipped = 0
        for entry in request.items:
            name = (entry.name or "").strip()
            if not name:
                continue
            if name.lower() in existing:
                skipped += 1
                continue
            group = (
                groups.get(entry.group_name.strip().lower())
                if entry.group_name else None
            )
            location = (
                locations.get(entry.location_name.strip().lower())
                if entry.location_name else None
            )
            self.repository.add(StockItem(
                name=name,
                notes=None,
                stock_group=group,
                stock_level_last_updated=now,
                stock_level=stocked,
                stock_location=location,
                # Same default as a hand-created item (2026-08-17): the
                # user typed these, so they join the stocktake rotation.
                stocktake_alerts_are_enabled=True,
            ))
            existing.add(name.lower())
            created += 1
        self.repository.save_changes()
        return SeedItemsResultDto(created=created, skipped=skipped)


@ONBOARDING_ROUTER.route("/seed-items", methods=["POST"])
@has_request_body(SeedItemsRequest)
def seed_items_onboarding():
    user_id = current_user_id()
    if user_id is None:
        return unauthorized("Sign in to use the onboarding endpoints.")
    _Request: SeedItemsRequest = get_request_body()
    result = SeedItemsHandler(SqlAlchemyRepository()).handle(_Request)
    _LOGGER.info(
        "Onboarding seed-items (user %s): +%d/-%d",
        user_id, result.created, result.skipped,
    )
    return ok(result)


# ─── Demo recipe + meal-plan (FU-194 / L38) ──────────────────────────
# Optional toggle in the wizard's starter-data step. Creates one plain
# Recipe (Aglio e Olio — three ingredients) with the StockItems it needs
# (created if missing — RecipeIngredient → StockItem FKs are non-nullable)
# and a MealPlan for the current household week with one dinner entry.
# Rows are *unmarked* — the user can rename or delete them like any other,
# per the FU's "no is_demo marking" rule. Idempotent: if the demo recipe
# (by name) already exists, the whole call is a no-op so a second click
# never duplicates anything.


# Mirrors the seed.py shape so the demo dataset matches what a dev seed
# would produce. Quantities/units kept simple — the point is a working
# end-to-end recipe + plan, not a curated cookbook.
_DEMO_RECIPE_NAME = "Spaghetti Aglio e Olio"
_DEMO_INSTRUCTIONS = (
    "1. Boil a large pot of salted water and cook the spaghetti until al dente.\n"
    "2. Meanwhile, gently heat the olive oil with the sliced garlic until fragrant, about 3 minutes.\n"
    "3. Toss the drained pasta through the garlic oil and serve."
)
# Ingredient names match the starter pack (`starter_packs.json`: "Pasta",
# "Garlic", "Olive oil") so the demo reuses the items the wizard just
# created rather than minting near-duplicates beside them ("Spaghetti pasta"
# next to "Pasta" — finalisation 14-R2). The recipe text still says
# spaghetti; the pantry item is the generic one.
_DEMO_INGREDIENTS = [
    {"name": "Pasta",     "quantity": 250.0, "unit": "g"},
    {"name": "Garlic",    "quantity":   4.0, "unit": "cloves"},
    {"name": "Olive oil", "quantity":  60.0, "unit": "ml"},
]


@dataclass(frozen=True, slots=True)
class SeedDemoResultDto:
    # `False` means the demo already existed (idempotent no-op); otherwise
    # the call wrote the rows. `items_created` counts only the StockItems
    # the demo had to create (existing items by name are reused).
    seeded: bool
    items_created: int
    recipe_created: bool
    meal_plan_created: bool


class SeedDemoHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self) -> SeedDemoResultDto:
        # Idempotency: skip the whole thing if the demo recipe already
        # exists (same by-name discipline the other seed endpoints use).
        if self._find_recipe_by_name(_DEMO_RECIPE_NAME) is not None:
            return SeedDemoResultDto(False, 0, False, False)

        # StockItems first — RecipeIngredient.stock_item_id is non-nullable.
        # We reuse existing items by name (so a user who already added
        # "Spaghetti pasta" in the starter pack doesn't get a duplicate),
        # and create the ones that don't exist yet.
        items_created = 0
        ingredient_items: list[StockItem] = []
        existing_items = {
            it.name.strip().lower(): it
            for it in self.repository.get(StockItem).all()
        }
        # Most-stocked level is the sensible default (mirrors seed-items
        # for the starter packs); migrations always seed at least one row.
        levels = self.repository.get(StockLevel).all()
        if not levels:
            _LOGGER.warning("Seed-demo skipped: no stock levels configured.")
            return SeedDemoResultDto(False, 0, False, False)
        stocked = _stocked_level(levels)
        slot_name = _demo_slot_name(self.repository)
        now = datetime.now(timezone.utc)
        for spec in _DEMO_INGREDIENTS:
            name = spec["name"]
            existing = existing_items.get(str(name).strip().lower())
            if existing is not None:
                ingredient_items.append(existing)
                continue
            item = StockItem(
                name=str(name),
                notes=None,
                stock_group=None,
                stock_level_last_updated=now,
                stock_level=stocked,
                stock_location=None,
                # Deliberately stays muted while the hand-created default is
                # on: these are scaffolding for the demo recipe, not items the
                # user chose to track, so they shouldn't fill the queue.
                stocktake_alerts_are_enabled=False,
            )
            self.repository.add(item)
            ingredient_items.append(item)
            items_created += 1

        ingredients = [
            RecipeIngredient(
                notes=None,
                quantity=float(spec["quantity"]),
                stock_item=item,
                unit=str(spec["unit"]),
            )
            for spec, item in zip(_DEMO_INGREDIENTS, ingredient_items)
        ]
        for ri in ingredients:
            self.repository.add(ri)

        recipe = Recipe(
            available_meals=0,
            category=None,
            cook_time_minutes=15,
            cuisine=None,
            difficulty="Easy",
            image=None,
            ingredients=ingredients,
            instructions=_DEMO_INSTRUCTIONS,
            is_favourite=False,
            last_made_on=None,
            name=_DEMO_RECIPE_NAME,
            prep_time_minutes=5,
            recipe_collection=None,
            servings=2,
            source=None,
            time_of_day=slot_name,
            version_group_id=None,
            kcal=None,
            steps_mode="freeform",
            created_at=now,
        )
        self.repository.add(recipe)

        # The entry is scheduled for today so the dashboard's Next-to-cook card
        # shows it immediately, on the plan for the current household week.
        # `MealPlan` has no week uniqueness, so a plan for this Monday may
        # already exist (the owner planned the week before running the demo);
        # the demo joins it rather than inserting a second plan for the same
        # week, which the planner then showed as two overlapping weeks
        # (finalisation 14-R1).
        today = household_today(self.repository)
        monday = today - timedelta(days=today.weekday())
        entry = MealPlanEntry(
            recipe=recipe,
            scheduled_for=today,
            servings=2,
            slot=slot_name,
        )
        existing_plan: MealPlan | None = self.repository.get(MealPlan).one(
            EntityField(MealPlan, MealPlan.Fields.START_DATE).eq(monday)
        )
        if existing_plan is not None:
            existing_plan.entries.append(entry)
            self.repository.add(entry)
        else:
            self.repository.add(MealPlan(
                name=None,
                start_date=monday,
                entries=[entry],
            ))
        self.repository.save_changes()
        # `meal_plan_created` keeps its contract meaning — "the demo meal is on
        # this week's plan" — whether the plan row was created or joined.
        return SeedDemoResultDto(
            seeded=True,
            items_created=items_created,
            recipe_created=True,
            meal_plan_created=True,
        )

    def _find_recipe_by_name(self, name: str) -> Recipe | None:
        target = name.strip().lower()
        for r in self.repository.get(Recipe).all():
            if (r.name or "").strip().lower() == target:
                return r
        return None


@ONBOARDING_ROUTER.route("/seed-demo", methods=["POST"])
def seed_demo_onboarding():
    user_id = current_user_id()
    if user_id is None:
        return unauthorized("Sign in to use the onboarding endpoints.")
    result = SeedDemoHandler(SqlAlchemyRepository()).handle()
    _LOGGER.info(
        "Onboarding seed-demo (user %s): seeded=%s items=+%d recipe=%s plan=%s",
        user_id, result.seeded, result.items_created,
        result.recipe_created, result.meal_plan_created,
    )
    return ok(result)
