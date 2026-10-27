"""`GET /api/ingest/products` — the saved-product list an ingestion source
refreshes against (products program PF-7).

The companion pulls this on the user's chosen schedule, re-scrapes an offer for
each product, and pushes the results back through `/api/ingest`. Dora never
reaches outward (PF-6): it publishes what it holds and waits.

Three things shape the response:

* **Only active products (PF-8).** `is_active = false` means "don't scrape
  this" — it is not merely a display filter. Honouring it here is what gives
  the flag a real cost and keeps a deselected product from burning scrape
  budget forever.
* **Every row carries `store_id`** (2026-10-15), and `store` is the external
  name this source maps that store from when it has one, else Dora's own name
  for it. A producer that keeps its own provider → store map (the companion)
  decides by `store_id` which rows it can refresh; one that relies on name
  mapping reads `store` as before. Products at stores the caller can't scrape
  are its to skip: the list no longer hides them, because a store reached by
  id has no mapping row to find them through.
* **Source-agnostic body (R-005).** Nothing in the response mentions the
  caller. Two sources with the same mappings see the same list.

The shape is the identity half of what `/api/ingest` accepts — `store` +
`merchant_stockcode` + `name` — plus Dora's own `product_id`, so a caller can
push a refreshed offer back without a second lookup, and can unsave via
`DELETE /api/ingest/products/<id>`.

Auth: `Authorization: Bearer <key>`, same as the batch and link-status
endpoints; the session cookie is not involved.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from uuid import UUID

from flask import request
from sqlalchemy import select

from dora_api.app import db
from dora_api.domain.entities.ingestion_source import IngestionSource
from dora_api.domain.entities.ingestion_store_mapping import \
    IngestionStoreMapping
from dora_api.features.routers import INGEST_ROUTER
from dora_api.infrastructure.api_response import ok
from dora_api.infrastructure.ingestion_auth import (
    authenticate_ingestion_request, stamp_used)
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository


_LOGGER = logging.getLogger(__name__)

# Keeps a pull bounded on a large catalogue. The caller pages with `offset`.
_DEFAULT_LIMIT = 200
_MAX_LIMIT = 500


@dataclass(slots=True)
class _IngestableProduct:
    product_id: str
    name: str
    store: str
    store_id: str
    merchant_stockcode: str | None
    brand: str | None
    size: str | None
    size_unit: str | None
    size_value: float | None


class GetIngestableProductsHandler:
    def __init__(self, repository: SqlAlchemyRepository) -> None:
        self.repository = repository

    def handle(
        self, source: IngestionSource, *, limit: int, offset: int,
    ) -> list[_IngestableProduct]:
        external_by_store = self._external_names_for(source)
        store_table = db.metadata.tables["Store"]
        dora_name_by_store: dict[UUID, str] = {
            row["id"]: row["name"]
            for row in db.session.execute(
                select(store_table.c.id, store_table.c.name)
            ).mappings().all()
        }

        product_table = db.metadata.tables["Product"]
        rows = db.session.execute(
            select(
                product_table.c.id,
                product_table.c.name,
                product_table.c.store_id,
                product_table.c.merchant_stockcode,
                product_table.c.brand,
                product_table.c.size,
                product_table.c.size_unit,
                product_table.c.size_value,
            )
            .where(
                product_table.c.is_active.is_(True),
                # OD-2 — a custom product has no upstream to refresh from.
                # Offering it to a producer would at best waste a request and
                # at worst have it matched against something else entirely.
                product_table.c.is_custom.is_(False),
            )
            .order_by(product_table.c.name)
            .limit(limit)
            .offset(offset)
        ).mappings().all()

        return [
            _IngestableProduct(
                product_id=str(row["id"]),
                name=row["name"],
                store=(
                    external_by_store.get(row["store_id"])
                    or dora_name_by_store.get(row["store_id"], "")
                ),
                store_id=str(row["store_id"]),
                merchant_stockcode=row["merchant_stockcode"],
                brand=row["brand"],
                size=row["size"],
                size_unit=row["size_unit"],
                size_value=row["size_value"],
            )
            for row in rows
        ]

    def _external_names_for(self, source: IngestionSource) -> dict[UUID, str]:
        """Store.id → the external name *this source* knows it by.

        The inverse of `GetLinkStatusHandler._resolve_store_id`, which the
        write side also uses — read and write must agree on the mapping or a
        pulled product can't be pushed back.

        Quarantined mappings (`store_id is None`) are skipped: the admin
        hasn't said what store they are yet. A store can carry more than one
        mapping for a source (two spellings of the same shop), and any of them
        round-trips, so the alphabetically-first is chosen for a stable
        response rather than whichever row came back first.
        """
        field_src = EntityField(
            IngestionStoreMapping, IngestionStoreMapping.Fields.SOURCE_ID
        )
        mappings = self.repository.get(IngestionStoreMapping).all(
            field_src.eq(source.id)
        )

        by_store: dict[UUID, str] = {}
        for mapping in sorted(mappings, key=lambda m: m.external_name):
            if mapping.store_id is None:
                continue
            by_store.setdefault(mapping.store_id, mapping.external_name)
        return by_store


@INGEST_ROUTER.route("/products", methods=["GET"], endpoint="ingest_list_products")
def ingest_list_products():
    # FU-866 — one shared check: authenticate, then honour the
    # install-wide ingestion switch. Both live in `ingestion_auth` so a
    # new ingest route cannot quietly skip the gate.
    source, auth_error = authenticate_ingestion_request()
    if auth_error is not None:
        return auth_error

    try:
        limit = min(int(request.args.get("limit", _DEFAULT_LIMIT)), _MAX_LIMIT)
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return ({"detail": "limit and offset must be integers."}, 400)
    if limit < 1 or offset < 0:
        return ({"detail": "limit must be >= 1 and offset >= 0."}, 400)

    repository = SqlAlchemyRepository()
    items = GetIngestableProductsHandler(repository).handle(
        source, limit=limit, offset=offset,
    )
    stamp_used(source)
    repository.save_changes()

    _LOGGER.info(
        "Source %s pulled %d ingestable product(s) (limit=%d, offset=%d).",
        source.id, len(items), limit, offset,
    )
    return ok({"items": [asdict(i) for i in items]})
