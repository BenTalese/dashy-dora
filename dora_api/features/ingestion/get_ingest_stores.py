"""`GET /api/ingest/stores` and `GET /api/ingest/stores/<id>/image`.

Dora's stores, for a producer that maps its own sources onto them (owner
2026-10-15: *"these stores should be the source of truth for stores/merchants
in the companion app"*). The companion reads this list, matches each scraper to
one or more stores by name on first run, lets the user fix the rest, and from
then on pushes by `store_id` rather than by a name Dora has to map.

The image route serves a store's uploaded logo to the same caller, so the
companion can show the logos the household set up here.

Auth: `Authorization: Bearer <key>`, like every `/api/ingest` route; the
session cookie is not involved.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from uuid import UUID

from flask import Response
from sqlalchemy import select

from dora_api.app import db
from dora_api.domain.entities.store import Store
from dora_api.features.routers import INGEST_ROUTER
from dora_api.features.stores.manage_stores import decode_store_image
from dora_api.infrastructure.api_response import not_found, ok
from dora_api.infrastructure.ingestion_auth import authenticate_ingestion_request
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository


_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _IngestStore:
    store_id: str
    name: str
    has_image: bool


@INGEST_ROUTER.route("/stores", methods=["GET"], endpoint="ingest_list_stores")
def ingest_list_stores():
    _source, auth_error = authenticate_ingestion_request()
    if auth_error is not None:
        return auth_error

    store_table = db.metadata.tables["Store"]
    rows = db.session.execute(
        select(
            store_table.c.id,
            store_table.c.name,
            store_table.c.image.isnot(None).label("has_image"),
        ).order_by(store_table.c.name)
    ).mappings().all()
    items = [
        _IngestStore(store_id=str(r["id"]), name=r["name"], has_image=bool(r["has_image"]))
        for r in rows
    ]
    _LOGGER.debug("Ingest store list: %d store(s).", len(items))
    return ok({"items": [asdict(i) for i in items]})


@INGEST_ROUTER.route(
    "/stores/<uuid:store_id>/image", methods=["GET"], endpoint="ingest_store_image",
)
def ingest_store_image(store_id: UUID):
    _source, auth_error = authenticate_ingestion_request()
    if auth_error is not None:
        return auth_error

    store = SqlAlchemyRepository().get(Store).by_id(store_id)
    if store is None:
        return not_found(Store.__name__, store_id)
    decoded = decode_store_image(store)
    if decoded is None:
        return not_found(Store.__name__, store_id)
    mime, raw = decoded
    return Response(raw, mimetype=mime, headers={"Cache-Control": "max-age=3600"})
