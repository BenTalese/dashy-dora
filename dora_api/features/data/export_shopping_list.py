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
from datetime import datetime, timezone
from uuid import UUID

from flask import Response, render_template_string

from dora_api.features.data.export_shared import PRINT_CSS, PRINT_TOOLBAR
from dora_api.features.routers import SHOPPING_LIST_ROUTER
from dora_api.features.shopping_lists.get_shopping_list_detail import (
    GetShoppingListDetailHandler,
    ShoppingListDetailDto,
    ShoppingListLineDto,
)
from dora_api.infrastructure.api_response import not_found
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

_LOGGER = logging.getLogger(__name__)


# ── Shared row prep ────────────────────────────────────────────────────

def _line_unit_price(line: ShoppingListLineDto) -> float | None:
    """Selected offer's `price_now` if there is one — `None` when the
    user hasn't picked an offer (we don't guess preferred/cheapest at
    export time; the CSV stays an honest snapshot of what's been chosen).
    """
    if line.selected_product_id is None:
        return None
    for offer in line.offers:
        if offer.product_id == line.selected_product_id:
            return offer.price_now
    return None


def _line_store(line: ShoppingListLineDto) -> str:
    if line.selected_product_id is None:
        return ""
    for offer in line.offers:
        if offer.product_id == line.selected_product_id:
            return offer.store_name
    return ""


def _line_location(line: ShoppingListLineDto) -> str:
    """Last crumb is the most specific level the item lives in."""
    if line.stock_location_breadcrumb:
        return line.stock_location_breadcrumb[-1]
    return "(no location)"


def _grouped_by_location(
    detail: ShoppingListDetailDto,
) -> list[tuple[str, list[ShoppingListLineDto]]]:
    """Group lines by their location, alphabetised within each group.
    The "(no location)" bucket sorts last so it doesn't dominate.
    """
    buckets: dict[str, list[ShoppingListLineDto]] = {}
    for line in detail.lines:
        buckets.setdefault(_line_location(line), []).append(line)
    for lines in buckets.values():
        lines.sort(key=lambda l: l.stock_item_name.lower())

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
      Generated {{ generated_at }} · {{ detail.lines | length }} item(s)
    </div>
    <div class="totals">
      <span><strong>{{ remaining_count }}</strong> remaining</span>
      <span><strong>{{ ticked_count }}</strong> picked up</span>
      {% if estimated_total is not none %}
        <span>Est. total <strong>${{ '%.2f' % estimated_total }}</strong></span>
      {% endif %}
    </div>
    {% if detail.lines | length == 0 %}
      <p><em>This shopping list is empty.</em></p>
    {% else %}
      {% for location, lines in groups %}
        <h2>{{ location }}</h2>
        <table>
          <tbody>
            {% for line in lines %}
              <tr>
                <td class="box"><span class="checkbox"></span></td>
                <td>
                  <span class="item-name">{{ line.stock_item_name }}</span>
                  {% if line_extras[line.line_id].store %}
                    <div class="item-store">{{ line_extras[line.line_id].store }}</div>
                  {% endif %}
                </td>
                <td class="qty">{{ line.quantity if line.quantity is not none else '' }}</td>
                <td class="price">
                  {% if line_extras[line.line_id].unit_price is not none %}
                    ${{ '%.2f' % line_extras[line.line_id].unit_price }}
                  {% endif %}
                </td>
              </tr>
            {% endfor %}
          </tbody>
        </table>
      {% endfor %}
    {% endif %}
  </div>
</body>
</html>
"""


def _render_print_view(detail: ShoppingListDetailDto) -> str:
    groups = _grouped_by_location(detail)
    ticked = sum(1 for l in detail.lines if l.is_ticked)
    remaining = len(detail.lines) - ticked

    line_extras: dict = {}
    totals: list[float] = []
    for line in detail.lines:
        unit = _line_unit_price(line)
        store = _line_store(line)
        line_extras[line.line_id] = {"unit_price": unit, "store": store}
        if unit is not None:
            totals.append(unit * (line.quantity if line.quantity is not None else 1))

    estimated_total = round(sum(totals), 2) if totals else None
    generated_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")

    return render_template_string(
        _PRINT_TEMPLATE,
        detail=detail,
        groups=groups,
        line_extras=line_extras,
        remaining_count=remaining,
        ticked_count=ticked,
        estimated_total=estimated_total,
        generated_at=generated_at,
        css=PRINT_CSS,
        toolbar=PRINT_TOOLBAR,
    )


# ── Route ──────────────────────────────────────────────────────────────

@SHOPPING_LIST_ROUTER.route("/<uuid:shopping_list_id>/print-view", methods=["GET"])
def print_view_shopping_list(shopping_list_id: UUID):
    detail = GetShoppingListDetailHandler(SqlAlchemyRepository()).handle(shopping_list_id)
    if detail is None:
        return not_found("ShoppingList", shopping_list_id)
    html = _render_print_view(detail)
    _LOGGER.info(
        "Rendered print view for shopping list %s (%d lines)",
        shopping_list_id, len(detail.lines),
    )
    return Response(html, mimetype="text/html; charset=utf-8")
