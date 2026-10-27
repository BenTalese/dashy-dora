"""Nutrition complex-mode endpoints — source status, dataset import, matching.

    GET  /api/nutrition/sources                  — what can answer a lookup now
    POST /api/nutrition/datasets/import          — start a bulk import (admin)
    GET  /api/nutrition/unmatched-items          — unlinked items + suggestions
    POST /api/nutrition/suggestions/accept-all   — link every confident match

Status is deliberately a *read of reality* rather than a stored flag: a
dataset is "available" iff it holds rows. The transient import phase is
in-memory (the import runs on a daemon thread), so a server restart mid-import
reports `idle` with whatever rows had been committed — honest, and recoverable
by starting again.
"""
import logging

from flask import request
from pydantic import BaseModel, ConfigDict, Field

from dora_api.features.app_settings.access import get_or_create_app_setting
from dora_api.features.nutrition.lookup import resolve_food, search_foods
from dora_api.features.nutrition.nutrients import NUTRIENT_ATTRS
from dora_api.features.nutrition.dataset_import import (
    dataset_label, default_url, start_import, state_for,
)
from dora_api.features.nutrition.sources import (
    local_catalogue_size, nutrition_mode, source_statuses,
)
from dora_api.features.nutrition.suggestions import (
    ignored_item_count, ignored_items, unmatched_items,
)
from dora_api.domain.entities.stock_item import StockItem
from dora_api.persistence.field import EntityField
from dora_api.features.routers import NUTRITION_ROUTER
from dora_api.features.auth.admin_gate import require_admin
from dora_api.infrastructure.api_response import bad_request, ok
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.domain.entities.nutrition_food import (
    NUTRITION_DATASET_SOURCES, NUTRITION_SOURCE_LABELS,
)
from dora_api.domain.entities.app_setting import NUTRITION_MODE_COMPLEX

_LOGGER = logging.getLogger(__name__)


class StartDatasetImportRequest(BaseModel):
    """Body schema for the dataset-import endpoint.

    Declaring it is not optional: `get_request_body()` reads what the
    deserialisation middleware parsed, and the middleware only parses for
    endpoints registered via `@has_request_body`. Without both halves the body
    is silently `None` — which is exactly how the download button shipped
    broken (every request became "unknown dataset ''").
    """
    model_config = ConfigDict(extra="forbid")
    source: str = Field(min_length=1, max_length=32)
    # Optional override so a superseded release URL (or a local mirror on an
    # air-gapped install) doesn't turn the button into a dead end.
    url: str | None = Field(default=None, max_length=500)


class ResolveFoodRequest(BaseModel):
    """Body schema for persisting a picked live suggestion. Only the source and
    its ref travel — the values are re-fetched server-side."""
    model_config = ConfigDict(extra="forbid")
    source: str = Field(min_length=1, max_length=32)
    source_ref: str = Field(min_length=1, max_length=100)


def _source_payload():
    repository = SqlAlchemyRepository()
    setting = get_or_create_app_setting(repository)
    statuses = source_statuses(repository, setting)

    sources = []
    for status in statuses:
        entry = {
            "id": status.id,
            "label": status.label,
            "kind": status.kind,
            "available": status.available,
            "food_count": status.food_count,
        }
        if status.kind == "dataset":
            state = state_for(status.id)
            entry.update({
                "phase": state.phase,
                "error": state.error,
                "default_url": default_url(status.id),
                # Live counters so the page can draw a real bar instead of an
                # open-ended spinner. `bytes_total` is 0 when the origin sent
                # no Content-Length, which the client reads as "indeterminate"
                # — it must not be treated as a denominator.
                "bytes_done": state.bytes_done,
                "bytes_total": state.bytes_total,
                "rows_done": state.rows_done,
                "foods": state.foods,
                "portions": state.portions,
            })
        sources.append(entry)

    return {
        "mode": nutrition_mode(setting),
        "sources": sources,
        # Any source at all can answer — the page uses this to explain a
        # `complex` mode that has nothing behind it yet.
        "any_available": any(s.available for s in statuses),
    }


@NUTRITION_ROUTER.route("/sources", methods=["GET"])
def get_nutrition_sources():
    return ok(_source_payload())


@NUTRITION_ROUTER.route("/lookup", methods=["GET"])
def lookup_foods():
    """Unified search across every enabled source. Not admin-gated — any
    member linking a stock item needs it."""
    _Query = (request.args.get("q") or "").strip()
    _Repository = SqlAlchemyRepository()
    _Setting = get_or_create_app_setting(_Repository)
    return ok(search_foods(_Repository, _Setting, _Query))


@NUTRITION_ROUTER.route("/foods/resolve", methods=["POST"])
@has_request_body(ResolveFoodRequest)
def resolve_food_endpoint():
    """Persist a picked live suggestion and return the saved food.

    Takes only (source, source_ref) — the values are re-fetched server-side
    rather than trusted from the request, so this can't be used to write
    arbitrary nutrition numbers into the catalogue.
    """
    _Body: ResolveFoodRequest = get_request_body()
    _Source = _Body.source.strip()
    _Ref = _Body.source_ref.strip()

    _Repository = SqlAlchemyRepository()
    _Setting = get_or_create_app_setting(_Repository)
    _Food = resolve_food(_Repository, _Setting, _Source, _Ref)
    if _Food is None:
        return bad_request(
            "That food couldn't be fetched from its source."
        )
    return ok({
        "id": str(_Food.id),
        "source": _Food.source,
        "source_label": NUTRITION_SOURCE_LABELS.get(_Food.source, _Food.source),
        "source_ref": _Food.source_ref,
        "name": _Food.name,
        "brand": _Food.brand,
        "barcode": _Food.barcode,
        # Driven off the nutrient table rather than hand-listed — this payload
        # is the third place the set was written out by hand, and the one most
        # likely to be forgotten when a nutrient is added (R-002).
        **{attr: getattr(_Food, attr, None) for attr in NUTRIENT_ATTRS},
    })


def _suggestion_payload(suggestion) -> dict | None:  # noqa: ANN001
    if suggestion is None:
        return None
    return {
        "nutrition_food_id": str(suggestion.nutrition_food_id),
        "name": suggestion.name,
        "brand": suggestion.brand,
        "source": suggestion.source,
        "source_label": suggestion.source_label,
        "kcal_per_100g": suggestion.kcal_per_100g,
        # Both travel: the raw score for anyone debugging a bad match, and the
        # band the UI actually renders. Deriving the band client-side would put
        # the threshold in two languages (R-003).
        "confidence": suggestion.confidence,
        "is_strong": suggestion.is_strong,
    }


def _item_payload(item) -> dict:  # noqa: ANN001
    return {
        "stock_item_id": str(item.stock_item_id),
        "name": item.name,
        "suggestion": _suggestion_payload(item.suggestion),
    }


@NUTRITION_ROUTER.route("/unmatched-items", methods=["GET"])
def get_unmatched_items():
    """Stock items with no nutrition food, each with its best local match.

    Not admin-gated — the matching page is user-facing work (the same call the
    owner made for the recipe bulk-linker), and nothing here writes.
    """
    _Repository = SqlAlchemyRepository()
    _Setting = get_or_create_app_setting(_Repository)
    if nutrition_mode(_Setting) != NUTRITION_MODE_COMPLEX:
        # Off/simple installs have no catalogue to match against. Answering
        # with an empty set rather than an error keeps the SPA's gate and the
        # API's gate saying the same thing.
        return ok({
            "items": [], "suggested_count": 0, "strong_count": 0,
            "ignored_count": 0, "ignored_items": [], "catalogue_size": 0,
        })

    _Items = unmatched_items(_Repository)
    _IncludeIgnored = (request.args.get("include_ignored") or "").lower() in ("1", "true")

    return ok({
        "items": [_item_payload(item) for item in _Items],
        # Counted server-side so the page's summary line and its "accept all"
        # button agree with what the list actually holds (R-003).
        "suggested_count": sum(1 for item in _Items if item.suggestion is not None),
        "strong_count": sum(
            1 for item in _Items
            if item.suggestion is not None and item.suggestion.is_strong
        ),
        "ignored_count": ignored_item_count(_Repository),
        "ignored_items": (
            [_item_payload(item) for item in ignored_items(_Repository)]
            if _IncludeIgnored else []
        ),
        # How many foods the matcher had to choose from. Zero is the difference
        # between "nothing left to match" and "nothing to match *against*" —
        # two states that otherwise render identically as an empty suggestion
        # column, which is exactly how a missing dataset gets mistaken for a
        # broken feature.
        "catalogue_size": local_catalogue_size(_Repository),
    })


@NUTRITION_ROUTER.route("/suggestions/accept-all", methods=["POST"])
def accept_all_suggestions():
    """Link every item whose suggestion is a near-certainty, in one write.

    Only `is_strong` matches are taken. The weaker ones are exactly the rows a
    human needs to look at, and sweeping them up in a bulk action is how a
    pantry ends up quietly full of wrong calories (P12 No-invent — the button
    press is the confirmation, so it can only cover matches that don't need
    judgement).

    Suggestions are recomputed here rather than accepted from the request body:
    the client sends nothing, so it can't nominate a link the matcher wouldn't
    have made itself.
    """
    _Repository = SqlAlchemyRepository()
    if nutrition_mode(get_or_create_app_setting(_Repository)) != NUTRITION_MODE_COMPLEX:
        return bad_request("Nutrition isn't in complex mode on this install.")

    _Strong = [
        item for item in unmatched_items(_Repository)
        if item.suggestion is not None and item.suggestion.is_strong
    ]
    if not _Strong:
        return ok({"linked_count": 0})

    _ItemsById = {
        item.id: item for item in _Repository.get(StockItem).where(
            EntityField(StockItem, StockItem.Fields.ID).in_(
                [item.stock_item_id for item in _Strong]
            )
        ).all()
    }
    _Linked = 0
    for match in _Strong:
        _StockItem = _ItemsById.get(match.stock_item_id)
        if _StockItem is None:
            continue
        _StockItem.nutrition_food_id = match.suggestion.nutrition_food_id
        _Linked += 1
    _Repository.save_changes()

    _LOGGER.info("Accepted %d confident nutrition suggestions in bulk.", _Linked)
    return ok({"linked_count": _Linked})


@NUTRITION_ROUTER.route("/datasets/import", methods=["POST"])
@has_request_body(StartDatasetImportRequest)
def start_dataset_import():
    _, _Error = require_admin()
    if _Error is not None:
        return _Error

    _Body: StartDatasetImportRequest = get_request_body()
    _Source = _Body.source.strip()
    if _Source not in NUTRITION_DATASET_SOURCES:
        return bad_request(f"Unknown nutrition dataset '{_Source}'.")
    _Url = (_Body.url or "").strip() or None

    _LOGGER.info("Starting nutrition dataset import: %s", dataset_label(_Source))
    start_import(_Source, _Url)
    return ok(_source_payload())
