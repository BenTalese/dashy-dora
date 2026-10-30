"""Stock-overview exports — install-wide CSV + a stocktake-friendly print view.

  GET  /api/stock-items/export?format=csv[&ids=a,b,…]
  POST /api/stock-items/export?format=csv     body {"ids": [...]}
  GET  /api/stock-items/print-view[?ids=a,b,…]
  POST /api/stock-items/print-view            body {"ids": [...]}

Why two doors: a filtered selection travels as ids, and ~39 bytes per uuid in
a query string runs into gunicorn's 8190-byte request-line cap (and nginx's
8 KB header buffer) at ~200 items — the user saw "Couldn't export…" or a dead
print tab. The POST door carries the same ids in a JSON body; the GET door
stays for no-filter / small-selection callers and existing links. Both call
one handler body (R-051 spirit: one implementation, two doors).

Designed for "take it to the pantry" use — print-view groups by location,
shows level + expiry, leaves a checkbox column to tick off as the user
counts.
"""
import csv
import io
import logging
from datetime import datetime, timezone

from uuid import UUID

from flask import Response, render_template_string, request
from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.stock_item import StockItem
from dora_api.features.data.export_shared import (
    PRINT_CSS, PRINT_TOOLBAR, csv_safe_row,
)
from dora_api.features.routers import STOCK_ITEM_ROUTER
from dora_api.infrastructure.api_response import bad_request
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

_LOGGER = logging.getLogger(__name__)


def _location_name(item: StockItem) -> str:
    return item.stock_location.name if item.stock_location else "(no location)"


def _group_by_location(items):
    buckets: dict[str, list[StockItem]] = {}
    for item in items:
        buckets.setdefault(_location_name(item), []).append(item)
    for v in buckets.values():
        v.sort(key=lambda i: i.name.lower())

    def _sort_key(name: str) -> tuple[int, str]:
        return (1, "") if name == "(no location)" else (0, name.lower())

    return sorted(buckets.items(), key=lambda kv: _sort_key(kv[0]))


def _build_csv(items) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "location", "name", "level", "expiry", "is_essential", "is_open", "notes",
    ])
    for location, group in _group_by_location(items):
        for item in group:
            writer.writerow(csv_safe_row([
                location,
                item.name,
                item.stock_level.name if item.stock_level else "",
                item.expiry_date.isoformat() if item.expiry_date else "",
                "true" if item.is_essential else "false",
                "true" if item.is_open else "false",
                item.notes or "",
            ]))
    return buffer.getvalue()


_PRINT_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Stock overview</title>
  {{ css | safe }}
</head>
<body>
  {{ toolbar | safe }}
  <div class="page">
    <h1>Stock overview</h1>
    <div class="meta">
      Generated {{ generated_at }} · {{ total }} item(s) across
      {{ groups | length }} location(s)
    </div>
    {% if total == 0 %}
      <p><em>No stock items yet.</em></p>
    {% else %}
      {% for location, items in groups %}
        <h2>{{ location }} <span class="meta">({{ items | length }})</span></h2>
        <table>
          <thead>
            <tr>
              <th class="box"></th>
              <th>Item</th>
              <th>Level</th>
              <th>Expiry</th>
            </tr>
          </thead>
          <tbody>
            {% for item in items %}
              <tr>
                <td class="box"><span class="checkbox"></span></td>
                <td>
                  <span class="item-name">{{ item.name }}</span>
                  {% if item.notes %}
                    <div class="item-notes">{{ item.notes }}</div>
                  {% endif %}
                </td>
                <td>{{ item.stock_level.name if item.stock_level else '–' }}</td>
                <td>{{ item.expiry_date.isoformat() if item.expiry_date else '–' }}</td>
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


def _all_items(ids: list[UUID] | None = None):
    """Load stock items (with the joins both exporters need). When `ids`
    is provided, restricts the result to that set so CSV / print mirror
    the on-screen filtered selection (C-1 Stock Overview Chunk 1 / L67).
    An empty list returns no items (the caller has filtered everything
    out, intentionally); `None` means "no filter, export everything".
    """
    repo = SqlAlchemyRepository()
    query = (
        repo.get(StockItem)
        .include("stock_level")
        .include("stock_location")
    )
    if ids is not None:
        if not ids:
            return []
        query = query.where(EntityField(StockItem, "id").in_(list(ids)))
    return query.all()


def _parse_ids(raw: str | None) -> list[UUID] | None:
    """Parse a comma-separated `ids=` param into a list of UUIDs. Returns
    `None` when absent (= export everything) and an empty list when the
    param is present but empty (= caller filtered everything out). Bad
    UUIDs are dropped silently; the export of zero items is still a
    legitimate response (matches what the on-screen filter would show)."""
    if raw is None:
        return None
    out: list[UUID] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            out.append(UUID(token))
        except (ValueError, TypeError):
            continue
    return out


# Upper bound for a POSTed selection. Generous — a whole real pantry fits many
# times over — but finite, so a runaway client can't hold a request open
# rendering an unbounded list. Shared with the QR sheet's POST door.
MAX_SELECTED_IDS = 5000


class StockItemSelectionRequest(BaseModel):
    """`{"ids": [...]}` — the POST twin of the GET routes' `ids=` param.
    Same semantics: an empty list is a legitimate "filtered to nothing"
    selection. Unlike the query-string door, a malformed uuid is a 400 here:
    the body is built by our own client, so a bad id is a bug to surface."""
    model_config = ConfigDict(extra="forbid")
    ids: list[UUID] = Field(max_length=MAX_SELECTED_IDS)


def _export_csv_response(ids: list[UUID] | None) -> Response:
    fmt = (request.args.get("format") or "csv").lower()
    if fmt not in ("csv",):
        return bad_request(
            f"Unsupported export format '{fmt}'. Supported: csv. "
            "For PDF, open the print-view and 'Save as PDF' from your browser."
        )
    items = _all_items(ids)
    body = _build_csv(items)
    today = datetime.now(timezone.utc).date().isoformat()
    filename = f"stock-overview-{today}.csv"
    _LOGGER.info(
        "Exported stock overview as %s (%d items)", fmt, len(items),
    )
    response = Response(body, mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _print_view_response(ids: list[UUID] | None) -> Response:
    items = _all_items(ids)
    generated_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    html = render_template_string(
        _PRINT_TEMPLATE,
        groups=_group_by_location(items),
        total=len(items),
        generated_at=generated_at,
        css=PRINT_CSS,
        toolbar=PRINT_TOOLBAR,
    )
    return Response(html, mimetype="text/html; charset=utf-8")


@STOCK_ITEM_ROUTER.route("/export", methods=["GET"])
def export_stock_overview():
    return _export_csv_response(_parse_ids(request.args.get("ids")))


@STOCK_ITEM_ROUTER.route("/export", methods=["POST"])
@has_request_body(StockItemSelectionRequest)
def export_stock_overview_selection():
    _Request: StockItemSelectionRequest = get_request_body()
    return _export_csv_response(_Request.ids)


@STOCK_ITEM_ROUTER.route("/print-view", methods=["GET"])
def print_view_stock_overview():
    return _print_view_response(_parse_ids(request.args.get("ids")))


@STOCK_ITEM_ROUTER.route("/print-view", methods=["POST"])
@has_request_body(StockItemSelectionRequest)
def print_view_stock_overview_selection():
    _Request: StockItemSelectionRequest = get_request_body()
    return _print_view_response(_Request.ids)
