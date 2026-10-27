"""Resolve and commit assistant-driven shopping-list additions.

The model only extracts *what* the user wants ("3 apples", "some milk"). It
never decides which tracked stock item that maps to — that's done here,
deterministically, against the database:

  - exactly one matching StockItem  -> ready to add
  - more than one match             -> ambiguous, ask the user which one
  - no match                        -> not found (round 2 doesn't create items)

`resolve_add_plan` builds the plan and never mutates. `commit_add` performs the
adds once the frontend has resolved any ambiguity, reusing AddLineHandler so the
unique-per-item / sequence rules stay in one place.
"""
import logging
from typing import Any
from uuid import UUID

from dora_api.features.assistant._name_resolution import (
    resolve_by_name, stock_item_candidate)
from dora_api.features.assistant._limits import MAX_CANDIDATES
from dora_api.domain.entities.shopping_list import ShoppingList
from dora_api.domain.entities.stock_item import StockItem
from dora_api.features.shopping_lists.manage_shopping_list_lines import (
    AddLineHandler, AddLineRequest)
from dora_api.features.shopping_lists.quick_add_target_resolver import \
    resolve_quick_add_target
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

_LOGGER = logging.getLogger(__name__)

# Don't drown the user in options for a vague term. If a fuzzy match returns
# more than this, ask them to be more specific rather than listing everything.


def _stock_query(repo: SqlAlchemyRepository):
    # A fresh builder per call: the query builder mutates its internal state on
    # .where(), so reusing one across two .all() calls would AND the conditions.
    return (
        repo.get(StockItem)
        .include(StockItem.Fields.STOCK_LEVEL)
        .include(StockItem.Fields.STOCK_LOCATION)
    )


def _match_stock_items(repo: SqlAlchemyRepository, name: str) -> list[StockItem]:
    return resolve_by_name(lambda: _stock_query(repo), StockItem, name).matches


def _normalise_items(raw_items: Any) -> list[dict[str, Any]]:
    """The model's `items` arg can arrive as a list of dicts or bare strings.
    Coerce to [{name, quantity}] and drop anything without a usable name."""
    items: list[dict[str, Any]] = []
    if not isinstance(raw_items, list):
        return items
    for entry in raw_items:
        if isinstance(entry, str):
            name, quantity = entry.strip(), None
        elif isinstance(entry, dict):
            name = str(entry.get("name") or "").strip()
            quantity = entry.get("quantity")
        else:
            continue
        if not name:
            continue
        parsed_quantity: int | None = None
        if quantity is not None:
            try:
                parsed_quantity = int(quantity)
            except (TypeError, ValueError):
                parsed_quantity = None
        items.append({"name": name, "quantity": parsed_quantity})
    return items


def _primary_list(repo: SqlAlchemyRepository) -> ShoppingList | None:
    # "Primary" is inferred, not stored (P6-01 Chunk 2): exactly one draft
    # list = the target; zero or several = no unambiguous primary, so the
    # assistant asks instead of guessing. (This previously queried the
    # dropped `is_primary` column and would AttributeError at runtime.)
    lists = repo.get(ShoppingList).all()
    outcome = resolve_quick_add_target(lists)
    if outcome.kind != "single":
        return None
    return next((l for l in lists if l.id == outcome.target_list_id), None)


def resolve_add_plan(raw_items: Any) -> dict[str, Any]:
    """Build a (non-mutating) plan for adding items to the primary list."""
    repo = SqlAlchemyRepository()
    items = _normalise_items(raw_items)
    primary = _primary_list(repo)

    resolved: list[dict[str, Any]] = []
    for item in items:
        matches = _match_stock_items(repo, item["name"])
        if len(matches) == 1:
            status = "ready"
        elif len(matches) == 0:
            status = "not_found"
        elif len(matches) > MAX_CANDIDATES:
            status = "too_many"
        else:
            status = "ambiguous"
        resolved.append({
            "query": item["name"],
            "quantity": item["quantity"],
            "status": status,
            "candidates": [stock_item_candidate(m) for m in matches[:MAX_CANDIDATES]],
        })

    return {
        "type": "add_to_shopping_list",
        "no_primary": primary is None,
        "shopping_list": (
            {"id": str(primary.id), "name": primary.display_name} if primary else None
        ),
        "items": resolved,
    }


def commit_add(shopping_list_id: UUID, resolved_items: list[dict[str, Any]]) -> dict[str, Any]:
    """Add each resolved (stock_item_id, quantity) to the list. Idempotent per
    item via AddLineHandler's existing dedupe."""
    handler = AddLineHandler(SqlAlchemyRepository())
    added = 0
    already = 0
    missing = 0
    for entry in resolved_items:
        stock_item_id = entry.get("stock_item_id")
        if not stock_item_id:
            continue
        quantity = entry.get("quantity")
        try:
            request = AddLineRequest(
                stock_item_id=UUID(str(stock_item_id)),
                quantity=quantity if quantity is not None else 1,
            )
        except (ValueError, TypeError):
            continue
        response = handler.handle(request, shopping_list_id)
        if response.item_not_found or response.list_not_found:
            missing += 1
        elif response.already_on_list:
            already += 1
        elif response.line_id is not None:
            added += 1
    _LOGGER.info(
        "Assistant committed adds to list %s: added=%s already=%s missing=%s",
        shopping_list_id, added, already, missing,
    )
    return {"added": added, "already": already, "missing": missing}
