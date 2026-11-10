"""`GET /api/ingest/stock-items`.

The household's stock items, id and name only, for a producer that lets the
user link a product as it saves it (owner 2026-11-10: *"should be able to link
on the spot from the companion app"*). The link itself rides on the batch
(`stock_item_id` on a product in `POST /api/ingest`).

Auth: `Authorization: Bearer <key>`, like every `/api/ingest` route; the
session cookie is not involved.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass

from sqlalchemy import func, select

from dora_api.app import db
from dora_api.features.routers import INGEST_ROUTER
from dora_api.infrastructure.api_response import ok
from dora_api.infrastructure.ingestion_auth import (authenticate_ingestion_request,
                                                    stamp_used)
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository


_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _IngestStockItem:
    stock_item_id: str
    name: str


@INGEST_ROUTER.route("/stock-items", methods=["GET"], endpoint="ingest_list_stock_items")
def ingest_list_stock_items():
    source, auth_error = authenticate_ingestion_request()
    if auth_error is not None:
        return auth_error
    stamp_used(source)
    SqlAlchemyRepository().save_changes()

    # R-005 carve-out: a two-column projection, so the picker list doesn't
    # load every stock item with its relationships just to read a name (the
    # same shape `get_ingest_stores` uses).
    stock_item_table = db.metadata.tables["StockItem"]
    rows = db.session.execute(
        select(stock_item_table.c.id, stock_item_table.c.name)
        .order_by(func.lower(stock_item_table.c.name))
    ).mappings().all()
    items = [_IngestStockItem(stock_item_id=str(r["id"]), name=r["name"]) for r in rows]
    _LOGGER.debug("Ingest stock item list: %d item(s).", len(items))
    return ok({"items": [asdict(i) for i in items]})
