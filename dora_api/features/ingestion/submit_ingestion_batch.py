"""`POST /api/ingest` — the producer-facing batch endpoint (C-10.2).

Auth: `Authorization: Bearer <key>` matched against `IngestionSource`.
The session-cookie middleware exempts this endpoint
(`middleware.PUBLIC_ENDPOINTS` carries `submit_ingestion_batch`); auth
lives here entirely.

Contract (PROPOSAL_INGESTION_API §2.2-§2.4):

- `Idempotency-Key` header: re-sending the same key under the same
  source is a no-op (last result is NOT cached — we just refuse to
  re-process to avoid double-writes).
- Payload: `{ products[], offers[] }`. Each record carries a `source`
  provenance string (defaults to the IngestionSource id if absent).
  **FU-227 chunk 7 (J1):** observations are in-app user input only;
  `price_observations[]` is no longer accepted (`extra="forbid"` rejects
  the field with a 400 — see PROPOSAL_PRODUCTS_AS_OVERLAY §2.5 "Idea A").
- Products dedupe on (store_id + stockcode) when stockcode is present,
  else (store_id + name) — same product across sources collapses into
  one row (shared catalogue, proposal §1/§5).
- Offers are append-only, deduped on
  (product_id, observed_at, price_now).
- FU-190: the producer's `store` string is resolved through
  `IngestionStoreMapping`. Unknown names quarantine (record skipped
  with `store_not_mapped`); admin maps later via the API access page.
  Stores are **never auto-created**.
- 2026-10-15: a producer that already knows Dora's stores (the companion reads
  them from `GET /api/ingest/stores` and keeps its own provider → store map)
  sends `store_id` instead of `store`. That skips the name mapping entirely; an
  id that names no store is skipped with `store_unknown`.

Per-record results follow the seed-style DTO: a bad record never fails
the batch — `{ accepted: [...], skipped: [...], failed: [...] }`.
"""
from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from flask import request
from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.idempotency_key import IdempotencyKey
from dora_api.domain.entities.ingestion_source import IngestionSource
from dora_api.domain.entities.ingestion_store_mapping import \
    IngestionStoreMapping
from dora_api.domain.entities.store import Store
from dora_api.domain.entities.product import Product
from dora_api.domain.entities.product_offer import ProductOffer
from dora_api.features.products.offer_mapping import (OfferOutcome,
                                                       apply_offer_to_product)
from dora_api.features.ingestion.product_identity import (StoreRef, find_ingested_product,
                                                          find_store_mapping)
from dora_api.features.routers import INGEST_ROUTER
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.ingestion_auth import (
    authenticate_ingestion_request, stamp_used)
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository
from dora_api.infrastructure.data_url import image_field


_LOGGER = logging.getLogger(__name__)

# Keys expire so the table stays bounded; long enough that an honest
# producer retrying a flaky network call still gets the no-op.
_IDEMPOTENCY_TTL = timedelta(days=7)


# ── Payload schema ─────────────────────────────────────────────────────

class _ProductIn(StoreRef):
    model_config = ConfigDict(extra="forbid")

    ref: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    # Exactly one of these. `store` is the store's external name, resolved
    # through the per-source mapping (was `merchant` pre-Phase-E); `store_id`
    # is a Dora store id, for a producer that maps stores on its own side.
    brand: str | None = Field(default=None, max_length=255)
    size: str | None = Field(default=None, max_length=255)
    size_unit: str | None = Field(default=None, max_length=255)
    size_value: float | None = Field(default=None, gt=0)
    # Multipack metadata (FU-232). `size_value` remains the TOTAL across
    # the bundle (e.g. 4×125g yoghurt → size_value=500); `pack_count` is
    # what recipe costing divides by to price a bare "3 eggs" (ADR-073). The
    # companion reads it off the listing ("12 Pack"). NULL = single-pack.
    pack_count: int | None = Field(default=None, gt=0)
    # `merchant_stockcode` carve-out: the producer's SKU code, kept
    # verbatim across the rename per the runbook.
    merchant_stockcode: str | None = Field(default=None, max_length=255)
    web_url: str | None = Field(default=None, max_length=500)
    source: str | None = Field(default=None, max_length=64)
    # The product picture as a `data:image/...;base64,...` URL, the form every
    # product image is stored in and `GET /products/<id>/image` decodes (same
    # cap as create_product). An ingested product's image comes only from
    # here: the producer supplies it, and a later push with one replaces it.
    # Absent leaves the stored image alone (owner 2026-10-17: images saved
    # from the companion never reached My products, because this field didn't
    # exist and the companion never sent one).
    image: str | None = image_field()


class _OfferIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_ref: str = Field(min_length=1, max_length=255)
    price_now: float = Field(gt=0)
    price_was: float | None = Field(default=None, gt=0)
    observed_at: datetime
    source: str | None = Field(default=None, max_length=64)


_IMAGE_DATA_URL_RE = re.compile(r"^data:image/[\w.+-]+;base64,")


def _ingested_image(value: str | None) -> bytes | None:
    """The stored form of a pushed image, or None to leave the image alone.

    Not a field validator: a bad record never fails the batch, so an image
    that isn't a data URL (which the image route could only 404) is dropped
    and the product itself still lands."""
    if not value or not _IMAGE_DATA_URL_RE.match(value):
        return None
    return value.encode("utf-8")


# `_PriceObservationIn` removed. Observations are an
# in-app user-input substrate only (PROPOSAL_PRODUCTS_AS_OVERLAY §2.5, Idea A):
# the producer never writes them. A request carrying `price_observations[]`
# is now rejected by `extra="forbid"` below; producers that wanted to push
# "I paid $X for product Y" should publish a one-point historic offer via
# the `offers[]` array instead — that's the offer/observation union point.


class IngestBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    products: list[_ProductIn] = Field(default_factory=list)
    offers: list[_OfferIn] = Field(default_factory=list)


# ── Result DTOs ────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class _AcceptedRecord:
    kind: Literal["product", "offer"]
    ref: str
    id: str
    note: str | None = None  # e.g. "created" / "duplicate"


@dataclass(frozen=True, slots=True)
class _SkippedRecord:
    kind: Literal["product", "offer"]
    ref: str
    reason: str  # short stable code: duplicate, store_not_mapped, product_unknown, ...


@dataclass(frozen=True, slots=True)
class _FailedRecord:
    kind: Literal["product", "offer"]
    ref: str
    reason: str


@dataclass(slots=True)
class IngestBatchResult:
    accepted: list[_AcceptedRecord] = field(default_factory=list)
    skipped: list[_SkippedRecord] = field(default_factory=list)
    failed: list[_FailedRecord] = field(default_factory=list)
    idempotent_replay: bool = False


# ── Handler ────────────────────────────────────────────────────────────

class _IngestionContext:
    """Per-batch scratchpad: caches Store lookups, the products
    touched this batch (by ref), and the running result. Keeps the
    handler body tidy without piling on parameters."""

    def __init__(self, source: IngestionSource, repository: SqlAlchemyRepository) -> None:
        self.source = source
        self.repository = repository
        self.result = IngestBatchResult()
        # ref → Product, populated as products are upserted; offers in
        # the same batch can target newly-created products.
        self.products_by_ref: dict[str, Product] = {}
        # external store name → mapping row (resolved Store or None)
        self.store_cache: dict[str, IngestionStoreMapping] = {}


class SubmitIngestionBatchHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    # — entrypoints —

    def handle(
        self,
        source: IngestionSource,
        idempotency_key: str | None,
        payload: IngestBatchRequest,
    ) -> IngestBatchResult:
        idempotency_row: IdempotencyKey | None = None
        if idempotency_key:
            idempotency_row = self._find_idempotency_row(source.id, idempotency_key)
            if idempotency_row is not None and self._is_live(idempotency_row):
                return IngestBatchResult(idempotent_replay=True)

        ctx = _IngestionContext(source, self.repository)

        for raw in payload.products:
            self._apply_product(ctx, raw)
        for raw in payload.offers:
            self._apply_offer(ctx, raw)
        # observations are in-app input only; the producer
        # path was removed (J1). Offer pushes still flow through above.

        # Counters land on the source row (consumed by C-10.3's
        # observability surface) — additive, so a re-send of a key
        # never double-counts.
        source.accepted_count += len(ctx.result.accepted)
        source.skipped_count += len(ctx.result.skipped)
        source.failed_count += len(ctx.result.failed)
        stamp_used(source)

        if idempotency_key:
            self._stamp_idempotency(source.id, idempotency_key, idempotency_row)

        self.repository.save_changes()
        return ctx.result

    # — idempotency —

    def _find_idempotency_row(self, source_id: UUID, key: str) -> IdempotencyKey | None:
        field_key = EntityField(IdempotencyKey, IdempotencyKey.Fields.KEY)
        field_src = EntityField(IdempotencyKey, IdempotencyKey.Fields.SOURCE_ID)
        return self.repository.get(IdempotencyKey).one(
            field_key.eq(key) & field_src.eq(str(source_id))
        )

    @staticmethod
    def _is_live(row: IdempotencyKey) -> bool:
        # SQLite drops the tzinfo on roundtrip even when the column is
        # `DateTime(timezone=True)`; coerce a naive read to UTC so the
        # comparison is well-defined.
        expires = row.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return expires > datetime.now(timezone.utc)

    def _stamp_idempotency(
        self, source_id: UUID, key: str, existing: IdempotencyKey | None,
    ) -> None:
        """Record `key` as consumed for `source_id`, and keep the table bounded.

        `(source_id, key)` is unique (`ix_idempotency_key_source_key`). An
        **expired** row for the same key is refreshed in place — the old code
        added a second row, which the index rejected at commit, so a producer
        that reused a stable key a week later got a 500 *after* the batch had
        been applied in the session, and lost it to the rollback (finalisation
        16-R2). Rows past their TTL are swept here too: nothing else ever
        deleted them, so the table grew by one row per push forever
        (16-R3). The sweep is bounded by the TTL and runs only on a keyed
        push, which is the one path that writes the table.
        """
        now = datetime.now(timezone.utc)
        field_expires = EntityField(IdempotencyKey, IdempotencyKey.Fields.EXPIRES_AT)
        for stale in self.repository.get(IdempotencyKey).all(field_expires.lt(now)):
            if existing is not None and stale.id == existing.id:
                continue  # refreshed below, not dropped
            self.repository.remove(stale)

        if existing is not None:
            existing.expires_at = now + _IDEMPOTENCY_TTL
            existing.created_at = now
            return
        self.repository.add(IdempotencyKey(
            key=key,
            source_id=str(source_id),
            expires_at=now + _IDEMPOTENCY_TTL,
            created_at=now,
        ))

    # — store mapping (FU-190) —

    def _resolve_store(
        self, ctx: _IngestionContext, external_name: str
    ) -> tuple[Store | None, IngestionStoreMapping]:
        """Look up (or create-as-quarantined) the per-source store
        mapping; return the Dora Store if mapped, else None."""
        cached = ctx.store_cache.get(external_name)
        if cached is not None:
            mapping = cached
        else:
            mapping = find_store_mapping(self.repository, ctx.source.id, external_name)
            if mapping is None:
                # First sighting — create the quarantined row so the
                # admin sees a pending mapping to resolve. Stores are
                # never auto-created.
                mapping = IngestionStoreMapping(
                    source_id=ctx.source.id,
                    external_name=external_name,
                    store_id=None,
                    created_at=datetime.now(timezone.utc),
                    last_seen_at=datetime.now(timezone.utc),
                )
                self.repository.add(mapping)
            ctx.store_cache[external_name] = mapping

        mapping.last_seen_at = datetime.now(timezone.utc)
        if mapping.store_id is None:
            return None, mapping
        store = self.repository.get(Store).by_id(mapping.store_id)
        return store, mapping

    # — record applicators —

    def _apply_product(self, ctx: _IngestionContext, raw: _ProductIn) -> None:
        if raw.store_id is not None:
            store = self.repository.get(Store).by_id(raw.store_id)
            if store is None:
                ctx.result.skipped.append(_SkippedRecord(
                    kind="product", ref=raw.ref, reason="store_unknown",
                ))
                return
        else:
            assert raw.store is not None  # guaranteed by `_one_store`
            store, _mapping = self._resolve_store(ctx, raw.store)
            if store is None:
                ctx.result.skipped.append(_SkippedRecord(
                    kind="product", ref=raw.ref, reason="store_not_mapped",
                ))
                return

        # Dedupe: stockcode-first, name fallback, never a custom product
        # (OD-2). Source is provenance only, NOT identity — the same product
        # pushed by two sources collapses into one Product row (shared
        # catalogue). The rule itself lives in `product_identity` so the
        # read side (`/api/ingest/link-status`) can never disagree with it.
        existing = find_ingested_product(
            self.repository, store.id, raw.merchant_stockcode, raw.name,
            includes=(Product.Fields.STORE, Product.Fields.CURRENT_OFFER),
        )

        if existing is not None:
            # Refresh mutable attributes; provenance recorded via the
            # next offer push, not the product row itself.
            existing.brand = raw.brand or existing.brand
            existing.size = raw.size or existing.size
            existing.size_unit = raw.size_unit or existing.size_unit
            existing.size_value = raw.size_value or existing.size_value
            existing.pack_count = raw.pack_count or existing.pack_count
            existing.web_url = raw.web_url or existing.web_url
            # Never a custom product here (`not_custom` above), so the
            # producer's picture is the product's picture.
            image = _ingested_image(raw.image)
            if image is not None:
                existing.image = image
            existing.is_active = True
            ctx.products_by_ref[raw.ref] = existing
            ctx.result.accepted.append(_AcceptedRecord(
                kind="product", ref=raw.ref, id=str(existing.id), note="updated",
            ))
            return

        # Create — initial offer mirrors the not-yet-known price; the
        # next /ingest offer for this product moves it. v1 producers
        # always push an offer for the same product so this is fine.
        initial_offer = ProductOffer(
            offered_on=datetime.now(timezone.utc),
            price_now=0.0,
            price_was=0.0,
        )
        product = Product(
            brand=raw.brand,
            current_offer=initial_offer,
            historic_offers=[],
            image=_ingested_image(raw.image),
            is_active=True,
            is_available=True,
            store=store,
            merchant_stockcode=raw.merchant_stockcode,
            name=raw.name,
            size=raw.size or "",
            size_unit=raw.size_unit or "",
            size_value=raw.size_value or 0.0,
            pack_count=raw.pack_count,
            web_url=raw.web_url,
        )
        self.repository.add(initial_offer)
        self.repository.add(product)
        ctx.products_by_ref[raw.ref] = product
        # Provenance is recorded on the offer rows (`ProductHistoricOffer.
        # source`), never smuggled into the product's result note.
        ctx.result.accepted.append(_AcceptedRecord(
            kind="product", ref=raw.ref, id=str(product.id), note="created",
        ))

    def _apply_offer(self, ctx: _IngestionContext, raw: _OfferIn) -> None:
        product = ctx.products_by_ref.get(raw.product_ref)
        if product is None:
            ctx.result.failed.append(_FailedRecord(
                kind="offer", ref=raw.product_ref, reason="product_unknown",
            ))
            return

        record_source = raw.source or str(ctx.source.id)
        outcome = apply_offer_to_product(
            self.repository,
            product,
            price_now=raw.price_now,
            price_was=raw.price_was,
            observed_at=raw.observed_at,
            source=record_source,
        )
        if outcome.outcome == OfferOutcome.DUPLICATE:
            ctx.result.skipped.append(_SkippedRecord(
                kind="offer", ref=raw.product_ref, reason="duplicate",
            ))
            return
        ctx.result.accepted.append(_AcceptedRecord(
            kind="offer", ref=raw.product_ref,
            id=outcome.historic_offer_id or "",
            note="appended",
        ))

# `_apply_observation` removed. The producer no longer
# writes observations; users do, via the in-app PriceEntry widget. The
# product-anchored half of the old method (push a single-point historic offer
# from a "$X for product Y" payload) was always a misuse of the observation
# substrate — that intent is properly expressed by a row in `offers[]` with
# the same `observed_at` + `price_now`, which the `_apply_offer` path above
# already covers.


# ── Route ──────────────────────────────────────────────────────────────


@INGEST_ROUTER.route("", methods=["POST"], endpoint="submit_ingestion_batch")
@has_request_body(IngestBatchRequest)
def submit_ingestion_batch():
    # FU-866 — one shared check: authenticate, then honour the
    # install-wide ingestion switch. Both live in `ingestion_auth` so a
    # new ingest route cannot quietly skip the gate.
    source, auth_error = authenticate_ingestion_request()
    if auth_error is not None:
        return auth_error

    # The body is validated by the request middleware (`has_request_body`),
    # which answers a malformed payload with the structured per-field 400
    # every other route uses — not `str(ValidationError)` (finalisation
    # 16-R9 / 16-R34; the owner saw that text ×5 in the companion).
    payload: IngestBatchRequest = get_request_body()

    idempotency_key = (request.headers.get("Idempotency-Key") or "").strip() or None

    handler = SubmitIngestionBatchHandler(SqlAlchemyRepository())
    result = handler.handle(source, idempotency_key, payload)

    _LOGGER.info(
        "Ingest batch from source %s: %d accepted, %d skipped, %d failed%s",
        source.id, len(result.accepted), len(result.skipped),
        len(result.failed), " (replay)" if result.idempotent_replay else "",
    )
    return {
        "accepted": [asdict(r) for r in result.accepted],
        "skipped": [asdict(r) for r in result.skipped],
        "failed": [asdict(r) for r in result.failed],
        "idempotent_replay": result.idempotent_replay,
    }
