"""Print-view export for shopping lists.

PDF generation is deliberately not done server-side: the SPA opens the
print-view in a new tab and calls window.print(), and the user can hit
"Save as PDF" from the browser's print dialog. Avoids weasyprint's heavy
system deps and the resulting output looks identical to the on-screen
preview.

The old CSV export (`GET /<id>/export?format=csv`) was removed in the
shopping-list UX v2 pass — print covers the only real take-it-with-you use
(`PROPOSAL_SHOPPING_LIST_UX_V2.md` §12 Q1).

Hangs off the existing SHOPPING_LIST_ROUTER:
  GET /api/shopping-lists/<id>/print-view
"""
import logging
from uuid import UUID

from flask import Response, render_template_string

from dora_api.domain.entities.shopping_list import SHOPPING_LIST_STATUS_DONE
from dora_api.features.data.export_shared import (
    PRINT_CSS,
    PRINT_TOOLBAR,
    PrintFormat,
    print_format,
)
from dora_api.features.routers import SHOPPING_LIST_ROUTER
from dora_api.features.shopping_lists.get_shopping_list_detail import (
    GetShoppingListDetailHandler,
    ShoppingListDetailDto,
    ShoppingListLineDto,
)
from dora_api.infrastructure.api_response import not_found
from dora_api.infrastructure.utils import pluralize
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

_LOGGER = logging.getLogger(__name__)


# ── Shared row prep ────────────────────────────────────────────────────
# Prices and stores are NOT re-derived here (R-003). The detail handler has
# already run the money ladder onto `estimated_unit_price` and the store ladder
# onto `resolved_store_name`, and summed `totals`; the sheet prints those, so
# it can't disagree with the list page. It used to price a line from the
# selected offer's `price_now` alone, counting set-aside lines too, and printed
# a different total from the app on every seeded list.

def _line_store(line: ShoppingListLineDto) -> str:
    return line.resolved_store_name or line.purchased_store_name or ""


def _line_location(line: ShoppingListLineDto) -> str:
    """Last crumb is the most specific level the item lives in."""
    if line.stock_location_breadcrumb:
        return line.stock_location_breadcrumb[-1]
    return "(no location)"


def _grouped_by_location(
    lines: list[ShoppingListLineDto],
) -> list[tuple[str, list[ShoppingListLineDto]]]:
    """Group lines by their location, alphabetised within each group.
    The "(no location)" bucket sorts last so it doesn't dominate.
    """
    buckets: dict[str, list[ShoppingListLineDto]] = {}
    for line in lines:
        buckets.setdefault(_line_location(line), []).append(line)
    for group in buckets.values():
        group.sort(key=lambda l: l.stock_item_name.lower())

    def _sort_key(name: str) -> tuple[int, str]:
        return (1, "") if name == "(no location)" else (0, name.lower())

    return sorted(buckets.items(), key=lambda kv: _sort_key(kv[0]))


# ── Print-view HTML ────────────────────────────────────────────────────

_PRINT_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{{ detail.display_name }} · shopping list</title>
  {{ css | safe }}
</head>
<body>
  {{ toolbar | safe }}
  <div class="page">
    <h1>{{ detail.display_name }}</h1>
    <div class="meta">
      Generated {{ generated_at }} · {{ item_count_label }}
    </div>
    <div class="totals">
      <span><strong>{{ totals.unticked_count }}</strong> remaining</span>
      <span><strong>{{ totals.ticked_count }}</strong> picked up</span>
      {% if total_label %}
        <span>{{ total_caption }} <strong>{{ total_label }}</strong></span>
      {% endif %}
    </div>
    {% macro line_table(lines) %}
      <table>
        <tbody>
          {% for line in lines %}
            <tr class="{{ 'picked' if line.is_ticked else '' }}">
              <td class="box">
                <span class="checkbox">{{ '✓' if line.is_ticked else '' }}</span>
              </td>
              <td>
                <span class="item-name">{{ line.stock_item_name }}</span>
                {% if store_of(line) %}
                  <div class="item-store">{{ store_of(line) }}</div>
                {% endif %}
              </td>
              <td class="qty">{{ line.quantity if line.quantity is not none else '' }}</td>
              <td class="price">
                {% if line.estimated_unit_price is not none %}
                  {{ money(line.estimated_unit_price) }}{% if line.quantity and line.quantity > 1 %} ea{% endif %}
                {% endif %}
              </td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    {% endmacro %}
    {% if active_count == 0 and set_aside | length == 0 %}
      <p><em>This shopping list is empty.</em></p>
    {% else %}
      {% for location, lines in groups %}
        <h2>{{ location }}</h2>
        {{ line_table(lines) }}
      {% endfor %}
      {% if set_aside %}
        <h2>Set aside to fit the budget</h2>
        {{ line_table(set_aside) }}
      {% endif %}
    {% endif %}
  </div>
</body>
</html>
"""


def _render_print_view(detail: ShoppingListDetailDto, fmt: PrintFormat) -> str:
    # Lines the trim-to-budget pass set aside aren't on the active list (the
    # totals skip them too); they print in their own trailing section.
    active = [l for l in detail.lines if not l.deferred_by_budget]
    set_aside = sorted(
        (l for l in detail.lines if l.deferred_by_budget),
        key=lambda l: l.stock_item_name.lower(),
    )
    totals = detail.totals
    is_done = detail.status == SHOPPING_LIST_STATUS_DONE
    # A done list's total sums only the lines that were bought (ticked), so a
    # price on a skipped line must not open the Total row onto "$0.00".
    priced = any(
        l.estimated_unit_price is not None and (l.is_ticked or not is_done) for l in active
    )

    return render_template_string(
        _PRINT_TEMPLATE,
        detail=detail,
        groups=_grouped_by_location(active),
        set_aside=set_aside,
        active_count=len(active),
        totals=totals,
        item_count_label=f"{totals.line_count} {pluralize(totals.line_count, 'item')}",
        # A finished list's total is what was spent (ticked lines only);
        # before that it's a projection.
        total_caption="Total" if is_done else "Est. total",
        total_label=fmt.money(totals.total_price) if priced else None,
        store_of=_line_store,
        money=fmt.money,
        generated_at=fmt.generated_at(),
        css=PRINT_CSS,
        toolbar=PRINT_TOOLBAR,
    )


# ── Route ──────────────────────────────────────────────────────────────

@SHOPPING_LIST_ROUTER.route("/<uuid:shopping_list_id>/print-view", methods=["GET"])
def print_view_shopping_list(shopping_list_id: UUID):
    repository = SqlAlchemyRepository()
    detail = GetShoppingListDetailHandler(repository).handle(shopping_list_id)
    if detail is None:
        return not_found("ShoppingList", shopping_list_id)
    html = _render_print_view(detail, print_format(repository))
    _LOGGER.info(
        "Rendered print view for shopping list %s (%d lines)",
        shopping_list_id, len(detail.lines),
    )
    # `mimetype`, not a hand-written charset: Flask appends `; charset=utf-8`
    # itself, and spelling it out doubled it (same fix as barcodes.py).
    return Response(html, mimetype="text/html")
