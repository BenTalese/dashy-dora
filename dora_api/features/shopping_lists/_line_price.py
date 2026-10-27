"""Shopping-line price helpers (FU-227 chunk 5).

Two server-owned chokepoints, both deliberately framework-free and pure so the
``/finish`` handler, the budget/waste/assistant reports, and the dev seed can
all share one definition (R-003 — no domain rule lives in two places):

* :func:`line_paid_unit_price` — the **actual→picked ladder**. Before this
  extract it was copy-pasted in ``budget.py``, ``waste.py`` and
  ``assistant/tools.py`` (K2); the harvest path would have been the 5th copy.
* :func:`harvest_observation_fields` — the E4 rule that turns "what you paid for
  this line" into the folded ``(total_price, total_measure, unit)`` observation
  shape (A1). A sized product in a measurable dimension yields a *measure*
  observation; everything else falls back to a *count* observation in ``ea``.
* :func:`resolve_store_id` — the **store ladder** (2026-08-28), the money
  ladder's twin. Added when a fifth rung (`planned_store_id`) landed and the
  ordering was still an if/elif chain inline in the detail handler, where
  nothing could test it.
* :func:`spend_lines`: "what was bought in this window", the one read every
  spend figure (budget, Reports) is built from (finalisation 12-R10).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select

from dora_api.domain import units
from dora_api.domain.entities.shopping_list import (SHOPPING_LIST_STATUS_DONE,
                                                    ShoppingList,
                                                    ShoppingListLine)


def lifetime_spend(session) -> float:
    """Lifetime spend: the `spend_lines` rule (ticked, not deferred, priced
    `actual` then `picked_offer`, times a positive quantity) summed in SQL
    over every finished list, so About and Reports can't disagree (R-003;
    finalisation 08-R6). Lines with neither price are skipped, not counted as
    zero: a floor, which is the honest reading of "spend *tracked*".

    R-005 carve-out: a single-number aggregate over two tables is Core SQL
    (the documented reports pattern), not a repository walk of every line.
    """
    unit_price = func.coalesce(
        ShoppingListLine.actual_unit_price, ShoppingListLine.picked_offer_price,
    )
    stmt = (
        select(func.sum(unit_price * func.coalesce(ShoppingListLine.quantity, 1)))
        .select_from(ShoppingListLine)
        .join(ShoppingList, ShoppingList.id == ShoppingListLine.shopping_list_id)
        .where(
            ShoppingList.status == SHOPPING_LIST_STATUS_DONE,
            ShoppingListLine.is_ticked == True,  # noqa: E712
            ShoppingListLine.deferred_by_budget == False,  # noqa: E712
            func.coalesce(ShoppingListLine.quantity, 1) > 0,
            unit_price.isnot(None),
        )
    )
    return round(float(session.execute(stmt).scalar() or 0.0), 2)


@dataclass(frozen=True, slots=True)
class SpendLine:
    """One bought line on a finished list, as the spend reports read it."""
    shopping_list_id: UUID
    completed_at: datetime
    stock_item_id: UUID | None
    selected_product_id: UUID | None
    quantity: float
    # The actual→picked ladder; None when the line carries no price.
    unit_price: float | None
    list_price_at_pick: float | None
    purchased_store_id: UUID | None
    planned_store_id: UUID | None

    @property
    def spent(self) -> float:
        """What the line cost: nothing when unpriced or a non-positive quantity,
        never a guess."""
        if self.unit_price is None or self.quantity <= 0:
            return 0.0
        return self.unit_price * self.quantity


def spend_lines(
    session, since: datetime | None, until: datetime | None = None,
) -> list[SpendLine]:
    """Every bought line on a list finished in ``[since, until)``: ticked, not
    deferred by trim-to-budget, priced or not (a report states its unpriced
    count rather than dropping it silently, R-041). ``since=None`` is all time.

    R-003 chokepoint (finalisation 12-R10): the budget period, its history and
    every Reports spend card read this one definition, so their totals agree
    on one window. R-005 carve-out: a two-table read for aggregates is Core SQL,
    the documented reports pattern.
    """
    stmt = (
        select(
            ShoppingList.id,
            ShoppingList.completed_at,
            ShoppingListLine.stock_item_id,
            ShoppingListLine.selected_product_id,
            ShoppingListLine.quantity,
            ShoppingListLine.actual_unit_price,
            ShoppingListLine.picked_offer_price,
            ShoppingListLine.list_price_at_pick,
            ShoppingListLine.purchased_store_id,
            ShoppingListLine.planned_store_id,
        )
        .select_from(ShoppingListLine)
        .join(ShoppingList, ShoppingList.id == ShoppingListLine.shopping_list_id)
        .where(
            ShoppingList.status == SHOPPING_LIST_STATUS_DONE,
            ShoppingList.completed_at.isnot(None),
            ShoppingListLine.is_ticked == True,  # noqa: E712
            ShoppingListLine.deferred_by_budget == False,  # noqa: E712
        )
    )
    if since is not None:
        stmt = stmt.where(ShoppingList.completed_at >= since)
    if until is not None:
        stmt = stmt.where(ShoppingList.completed_at < until)
    out: list[SpendLine] = []
    for (
        list_id, completed_at, stock_item_id, product_id, quantity,
        actual, picked, rrp, purchased_store_id, planned_store_id,
    ) in session.execute(stmt).all():
        paid = actual if actual is not None else picked
        out.append(SpendLine(
            shopping_list_id=list_id,
            completed_at=completed_at,
            stock_item_id=stock_item_id,
            selected_product_id=product_id,
            quantity=float(quantity) if quantity is not None else 1.0,
            unit_price=float(paid) if paid is not None else None,
            list_price_at_pick=float(rrp) if rrp is not None else None,
            purchased_store_id=purchased_store_id,
            planned_store_id=planned_store_id,
        ))
    return out


def line_paid_unit_price(line: ShoppingListLine) -> float | None:
    """The per-unit price actually paid for a shopping line, via the standard
    ladder: the user-entered ``actual_unit_price`` wins, else the
    ``picked_offer_price`` snapshot (written on lines finished before
    2026-09-17, never since), else ``None`` (no captured price — the line
    doesn't contribute to spend).

    R-003 chokepoint (K2): the single definition of "what did this line cost".
    """
    if line.actual_unit_price is not None:
        return float(line.actual_unit_price)
    if line.picked_offer_price is not None:
        return float(line.picked_offer_price)
    return None


def harvest_observation_fields(
    *,
    unit_price: float,
    quantity: int | None,
    size_value: float | None,
    size_unit: str | None,
    product_pack_count: int | None = None,
) -> tuple[float, float, str, int | None]:
    """Fold a finished line's price into one observation's
    ``(total_price, total_measure, unit, pack_count)`` (A1 / E4 + FU-227
    multipack follow-up).

    ``unit_price`` is per *item* (one bottle, one pack); ``quantity`` is how
    many items the line bought. ``total_price`` is therefore always
    ``unit_price × quantity`` — never multiplied by the measure (a sized
    product's pack size would otherwise be double-counted).

    The measure splits two ways:

    * **Sized product** — when the selected product has a positive size in a
      price dimension (volume / mass / count), the observation is a *measure*
      observation: ``total_measure = size_value × quantity`` in the product's
      canonical unit (e.g. 2 bottles × 2 L → 4 L). ``your_prices`` then
      normalises to the dimension's canonical denominator for the median.
    * **Sizeless / unsupported unit** — a *count* observation: one ``ea`` per
      item (``total_measure = quantity``, ``unit = "ea"``). Covers the
      "$9 for 3 punnets" case and product-less lines.

    The returned ``pack_count`` carries the multipack context: when the
    product has ``pack_count`` set (e.g. ``4`` for "125g × 4 pack"), the obs
    inherits ``product_pack_count × quantity`` so a "$4.20 for 1 box of
    4-pack" obs renders as "4 × 125g" rather than "500g flat". ``None`` for
    non-multipack purchases.
    """
    qty = quantity or 1
    total_price = float(unit_price) * qty
    pack_count: int | None = None
    if product_pack_count and product_pack_count > 0:
        pack_count = int(product_pack_count) * qty
    if size_value and float(size_value) > 0 and size_unit:
        udef = units.find_unit(size_unit)
        if udef is not None and udef.dimension in units.PRICE_DIMENSIONS:
            return total_price, float(size_value) * qty, udef.canonical, pack_count
    return total_price, float(qty), "ea", pack_count


def resolve_store_id(
    *,
    purchased_store_id: UUID | None,
    planned_store_id: UUID | None,
    usual_store_id: UUID | None,
    last_purchase_store_id: UUID | None,
    chosen_offer_store_id: UUID | None,
) -> UUID | None:
    """The **store ladder**: which store a shopping line is associated with.

    Five rungs, first non-null wins::

        purchased  → where you actually bought it (a record; only after the fact)
        planned    → where you mean to buy it, *on this list*
        usual      → ``StockItem.usual_store_id``, a standing preference
        last       → the store of the most recent actual purchase
        offer      → the chosen product offer's store

    Two orderings matter and both are deliberate:

    * **Intent beats history**, which is the reverse of
      :func:`line_paid_unit_price`. That ladder answers "what did this cost",
      where what you really paid outranks an advertised price; this one answers
      "where do I *plan* to buy it", where a stated intention outranks where you
      happened to shop last time.
    * **The more specific intent wins.** ``planned`` is a choice made for this
      list; ``usual`` is a habit that applies to every list. A shop where you're
      making an exception must not be overruled by the rule.

    R-003 chokepoint, and pure so the ordering is testable without a repository
    — the ladder decides which section a line lands in under Order-by → Store,
    so getting a rung wrong silently re-groups the list. ``None`` ⇒ the
    "No store set" bucket.
    """
    return (
        purchased_store_id
        or planned_store_id
        or usual_store_id
        or last_purchase_store_id
        or chosen_offer_store_id
    )
