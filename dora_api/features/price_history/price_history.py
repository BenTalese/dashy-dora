"""N8 — Price History Explorer backend.

  GET    /api/price-history?product_ids=<csv>&range=30d|90d|1y|all
  POST   /api/price-history/alerts          — body {product_id, threshold_unit_price}
  GET    /api/price-history/alerts          — list current user's alerts
  DELETE /api/price-history/alerts/<id>     — remove

Price points are pulled from `ProductHistoricOffer` (the append-only
log fed by `POST /api/ingest`). The current point comes from the live
`ProductOffer` row. All-time low is computed across the historic rows.

Alerts are per-user; the trigger-side logic (firing a notification on
the next push that beats the threshold) is owned by whatever ingestion
producer the install runs — this round just creates / lists / removes
the subscription rows.
"""
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from flask import request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from dora_api.app import db
from dora_api.domain.entities.price_alert import PriceAlert
from dora_api.domain.entities.product import Product
from dora_api.domain.product_offer import discount_percent
from dora_api.features._ranges import RANGE_DAYS, range_start
from dora_api.features.routers import PRICE_HISTORY_ROUTER
from dora_api.features.stock_items.your_prices import (
    build_product_observation_series, build_your_prices_for_product)
from dora_api.infrastructure.api_response import (bad_request, no_content,
                                                  not_found, ok, unauthorized)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.session_user import current_user_id

_LOGGER = logging.getLogger(__name__)


def _as_utc(value: datetime) -> datetime:
    """SQLite hands back naive datetimes, which are stored as UTC."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _parse_product_ids(raw: str | None) -> list[UUID]:
    if not raw:
        return []
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


# ── GET /api/price-history ────────────────────────────────────────────

@PRICE_HISTORY_ROUTER.route("", methods=["GET"])
def get_price_history():
    ids = _parse_product_ids(request.args.get("product_ids"))
    if not ids:
        return bad_request("Provide one or more product_ids (comma-separated UUIDs).")
    if len(ids) > 5:
        return bad_request("At most 5 products at a time.")

    # An absent or unknown token (and "all") means all time.
    repo = SqlAlchemyRepository()
    cutoff = range_start(RANGE_DAYS.get(request.args.get("range") or ""), repo)

    # R-005 carve-out: a four-table aggregate (product, store, live offer,
    # history) read once per request; core SQL is portable both ways.
    product_table = db.metadata.tables["Product"]
    store_table = db.metadata.tables["Store"]
    offer_table = db.metadata.tables["ProductOffer"]
    historic_table = db.metadata.tables["ProductHistoricOffer"]

    products = db.session.execute(
        select(
            product_table.c.id, product_table.c.name,
            product_table.c.size_value, product_table.c.size_unit,
            store_table.c.name.label("store_name"),
        ).select_from(
            product_table.join(store_table, product_table.c.store_id == store_table.c.id)
        ).where(product_table.c.id.in_(ids))
    ).mappings().all()
    products_by_id = {row["id"]: dict(row) for row in products}

    # Every historic point once: the all-time low reads them all, the series
    # only those inside the range.
    all_history = db.session.execute(
        select(historic_table).where(historic_table.c.product_id.in_(ids)).order_by(
            historic_table.c.product_id, historic_table.c.offered_on,
        )
    ).mappings().all()
    historic_rows = [
        row for row in all_history
        if cutoff is None or (row["offered_on"] is not None and _as_utc(row["offered_on"]) >= cutoff)
    ]

    # Live offers (current).
    current_rows = db.session.execute(
        select(offer_table).where(offer_table.c.product_id.in_(ids))
    ).mappings().all()
    current_by_product = {row["product_id"]: dict(row) for row in current_rows}

    atl_by_product: dict[Any, dict[str, Any]] = {}
    for row in all_history:
        pid = row["product_id"]
        price = row["price_now"]
        if price is None:
            continue
        prev = atl_by_product.get(pid)
        if prev is None or price < prev["unit_price"]:
            atl_by_product[pid] = {
                "unit_price": float(price),
                "date": (row["offered_on"].isoformat() if row["offered_on"] else None),
            }

    series: list[dict[str, Any]] = []
    points_by_product: dict[Any, list[dict[str, Any]]] = {pid: [] for pid in ids}
    for row in historic_rows:
        pid = row["product_id"]
        if pid not in points_by_product:
            continue
        points_by_product[pid].append({
            "date": row["offered_on"].isoformat() if row["offered_on"] else None,
            "unit_price": float(row["price_now"]) if row["price_now"] is not None else None,
            "list_price": float(row["price_was"]) if row["price_was"] is not None else None,
            "on_deal": (
                row["price_now"] is not None
                and row["price_was"] is not None
                and row["price_now"] < row["price_was"]
            ),
        })

    # the user's own observation overlay + the
    # baseline reference line. Observations are normalised per-unit and the
    # baseline rides the chunk-4 chokepoint (R-003). The SPA renders the
    # observation series only when a product has no offers (the H2 fallback)
    # so the per-unit observation scale never clashes with the raw offer scale
    # on a product that has offers (decision: H2-fallback-only).
    for pid in ids:
        product = products_by_id.get(pid)
        if product is None:
            # The caller asked for a product that doesn't exist —
            # surface a placeholder so the SPA can render "no data".
            series.append({
                "product_id": str(pid), "name": "(unknown)", "store": "",
                "points": [], "current": None, "all_time_low": None,
                "your_prices": None, "observation_points": [],
            })
            continue
        current = current_by_product.get(pid)
        deal_pct = discount_percent(current["price_now"], current["price_was"]) if current else None

        _Yp = build_your_prices_for_product(repo, pid)
        _ObsUnit, _ObsPoints = build_product_observation_series(repo, pid)

        series.append({
            "product_id": str(pid),
            "name": product["name"],
            "store": product["store_name"] or "",
            "points": points_by_product.get(pid, []),
            "current": (
                {
                    "unit_price": float(current["price_now"]) if current and current.get("price_now") is not None else None,
                    "list_price": float(current["price_was"]) if current and current.get("price_was") is not None else None,
                    "deal_pct": deal_pct,
                }
                if current else None
            ),
            "all_time_low": atl_by_product.get(pid),
            # F-3 — baseline + above-usual signal for this product's own prices.
            "your_prices": {
                "baseline": _Yp.baseline,
                "baseline_unit": _Yp.baseline_unit,
                "current": _Yp.current,
                "above_baseline": _Yp.above_baseline,
                "sample_count": _Yp.sample_count,
            },
            # H2 — per-unit observation series ("date" matches the offer
            # points' key so the chart treats them uniformly).
            "observation_points": [
                {
                    "date": p.observed_at.isoformat() if p.observed_at else None,
                    "unit_price": p.unit_price,
                    "store_name": p.store_name,
                }
                for p in _ObsPoints
            ],
        })

    _LOGGER.debug(
        "price_history requested ids=%s range=%s", ids, request.args.get("range"),
    )
    return ok({"series": series})


# ── Alerts ────────────────────────────────────────────────────────────

class CreatePriceAlertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: UUID
    threshold_unit_price: float = Field(gt=0)


@PRICE_HISTORY_ROUTER.route("/alerts", methods=["POST"])
@has_request_body(CreatePriceAlertRequest)
def create_price_alert():
    user_id = current_user_id()
    if user_id is None:
        return unauthorized()
    body: CreatePriceAlertRequest = get_request_body()

    repo = SqlAlchemyRepository()
    if repo.get(Product).by_id(body.product_id) is None:
        return not_found("Product", body.product_id)

    # One watch per product per user (owner 2026-10-15): setting a new price
    # replaces the old one rather than stacking a second row the user has no
    # way to tell apart from the first.
    row: PriceAlert | None = repo.get(PriceAlert).one(
        EntityField(PriceAlert, PriceAlert.Fields.USER_ID).eq(user_id)
        & EntityField(PriceAlert, PriceAlert.Fields.PRODUCT_ID).eq(body.product_id)
    )
    if row is None:
        row = PriceAlert(
            user_id=user_id,
            product_id=body.product_id,
            threshold_unit_price=float(body.threshold_unit_price),
            created_at=datetime.now(timezone.utc),
        )
        repo.add(row)
    else:
        row.threshold_unit_price = float(body.threshold_unit_price)
    repo.save_changes()
    return ok({
        "price_alert_id": str(row.id),
        "product_id": str(body.product_id),
        "threshold_unit_price": float(body.threshold_unit_price),
        "created_at": row.created_at.isoformat(),
    })


@PRICE_HISTORY_ROUTER.route("/alerts", methods=["GET"])
def list_price_alerts():
    user_id = current_user_id()
    if user_id is None:
        return unauthorized()
    # R-005 carve-out: a three-table projection (watch + product + store) for
    # one list; core SQL is portable to Postgres and SQLite alike.
    alert_table = db.metadata.tables["PriceAlert"]
    product_table = db.metadata.tables["Product"]
    store_table = db.metadata.tables["Store"]
    rows = db.session.execute(
        select(
            alert_table.c.id, alert_table.c.product_id,
            alert_table.c.threshold_unit_price, alert_table.c.created_at,
            product_table.c.name.label("product_name"),
            store_table.c.name.label("store_name"),
        )
        .select_from(
            alert_table.join(product_table, alert_table.c.product_id == product_table.c.id)
            .join(store_table, product_table.c.store_id == store_table.c.id)
        )
        .where(alert_table.c.user_id == user_id)
        .order_by(alert_table.c.created_at.desc())
    ).mappings().all()
    return ok({
        "items": [
            {
                "price_alert_id": str(r["id"]),
                "product_id": str(r["product_id"]),
                "product_name": r["product_name"],
                "store_name": r["store_name"],
                "threshold_unit_price": float(r["threshold_unit_price"]),
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ],
    })


@PRICE_HISTORY_ROUTER.route("/alerts/<uuid:alert_id>", methods=["DELETE"])
def delete_price_alert(alert_id: UUID):
    # R-033: uuid converter parses the id at the routing edge (FU-544).
    user_id = current_user_id()
    if user_id is None:
        return unauthorized()
    repo = SqlAlchemyRepository()
    # Scope by user so one account can't delete another's alerts.
    alert = repo.get(PriceAlert).one(
        EntityField(PriceAlert, "id").eq(alert_id)
        & EntityField(PriceAlert, PriceAlert.Fields.USER_ID).eq(user_id)
    )
    if alert is None:
        return not_found("PriceAlert", alert_id)
    repo.remove(alert)
    repo.save_changes()
    return no_content()
