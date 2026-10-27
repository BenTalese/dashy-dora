"""Product identity for the ingestion seam — one lookup, both directions.

Both halves of `/api/ingest` answer the same question, "which `Product` row
is this `(store, merchant_stockcode | name)`?": the write side
(`submit_ingestion_batch._apply_product`) to dedupe an incoming record onto
an existing row, the read side (`get_link_status._find_product`) to tell a
producer what Dora already holds so it can decorate its own search results
and offer *unsave*.

They used to carry two copies of the lookup, and the copies disagreed on
OD-2 (hand-entered "custom" products are the user's own and are never
adopted by machinery): the write side skipped `is_custom` rows, the read
side did not. So a search for a name the user had typed in by hand came
back "already in Dora", and the companion's unsave then deleted the user's
own product through `DELETE /api/ingest/products/<id>` (finalisation
16-R8). This module is the single answer (R-003); `find_ingested_product`
is the only place the stockcode-first / name-fallback / never-custom rule
is written.
"""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from dora_api.domain.entities.ingestion_store_mapping import IngestionStoreMapping
from dora_api.domain.entities.product import Product
from dora_api.domain.entities.store import Store
from dora_api.infrastructure.ports import Repository
from dora_api.persistence.field import EntityField


class StoreRef(BaseModel):
    """The producer names a store one of two ways — the external name this
    source maps through, or a Dora store id — and exactly one. Shared by the
    batch and link-status request models (finalisation 16-R10)."""
    store: str | None = Field(default=None, min_length=1, max_length=255)
    store_id: UUID | None = None

    @model_validator(mode="after")
    def _one_store(self):
        if (self.store is None) == (self.store_id is None):
            raise ValueError("Give exactly one of `store` or `store_id`.")
        return self


def find_store_mapping(
    repository: Repository, source_id: UUID, external_name: str,
) -> IngestionStoreMapping | None:
    """The per-source row for an external store name — the one lookup the
    write side (quarantine), the read side and the admin upsert share
    (finalisation 16-R6)."""
    field_src = EntityField(IngestionStoreMapping, IngestionStoreMapping.Fields.SOURCE_ID)
    field_ext = EntityField(IngestionStoreMapping, IngestionStoreMapping.Fields.EXTERNAL_NAME)
    return repository.get(IngestionStoreMapping).one(
        field_src.eq(source_id) & field_ext.eq(external_name)
    )


def find_ingested_product(
    repository: Repository,
    store_id: UUID,
    stockcode: str | None,
    name: str | None,
    *,
    includes: tuple[str, ...] = (),
) -> Product | None:
    """The ingested (never custom) product at `store_id` matching
    `stockcode` first, then `name`.

    `includes` are relationship names to eager-load (`Product.Fields.STORE`,
    `Product.Fields.CURRENT_OFFER`) for callers that go on to mutate the row;
    a read-only caller passes none.
    """
    field_name = EntityField(Product, Product.Fields.NAME)
    field_stockcode = EntityField(Product, Product.Fields.MERCHANT_STOCKCODE)
    field_store_id = EntityField(Store, Store.Fields.ID)
    # OD-2 — a custom product is the user's to edit. A scraped record with
    # the same name at the same store creates its own row rather than
    # overwriting the user's figure, and a lookup must say "not held" so a
    # producer never learns a custom product's id.
    not_custom = EntityField(Product, Product.Fields.IS_CUSTOM).eq(False)

    def _query():
        query = repository.get(Product)
        for relationship in includes:
            query = query.include(relationship)
        return query

    if stockcode:
        existing = _query().one(
            field_stockcode.eq(stockcode) & field_store_id.eq(store_id) & not_custom
        )
        if existing is not None:
            return existing
    if name:
        return _query().one(
            field_name.eq(name) & field_store_id.eq(store_id) & not_custom
        )
    return None
