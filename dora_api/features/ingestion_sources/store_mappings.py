"""Admin CRUD over `IngestionStoreMapping` (C-10.2 / FU-190).

The API access page lists pending (`store_id IS NULL`) and resolved
mappings per source. The admin assigns or clears the Dora `Store`
each external name resolves to. Stores are **never auto-created** here
either — the admin picks one of the existing Stores.

Endpoints (all admin-only, session-cookie):

- `GET /api/ingestion-sources/<source_id>/store-mappings`         — list
- `PUT /api/ingestion-sources/<source_id>/store-mappings`         — upsert
- `DELETE /api/ingestion-sources/<source_id>/store-mappings/<id>` — drop
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.ingestion_source import IngestionSource
from dora_api.domain.entities.ingestion_store_mapping import \
    IngestionStoreMapping
from dora_api.domain.entities.store import Store
from dora_api.features.auth.admin_gate import require_admin
from dora_api.features.ingestion.product_identity import find_store_mapping
from dora_api.features.routers import INGESTION_SOURCE_ROUTER
from dora_api.infrastructure.api_response import (bad_request, no_content,
                                                  not_found)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StoreMappingDto:
    id: UUID
    source_id: UUID
    external_name: str
    store_id: UUID | None
    store_name: str | None
    created_at: datetime
    last_seen_at: datetime | None

    @classmethod
    def from_entity(
        cls, mapping: IngestionStoreMapping, store: Store | None
    ) -> "StoreMappingDto":
        return cls(
            id=mapping.id,
            source_id=mapping.source_id,
            external_name=mapping.external_name,
            store_id=mapping.store_id,
            store_name=store.name if store else None,
            created_at=mapping.created_at,
            last_seen_at=mapping.last_seen_at,
        )


class UpsertStoreMappingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_name: str = Field(min_length=1, max_length=255)
    # `null` to quarantine (clears the link); a UUID to bind.
    store_id: UUID | None = None


class ListStoreMappingsHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, source_id: UUID) -> list[StoreMappingDto] | None:
        if self.repository.get(IngestionSource).by_id(source_id) is None:
            return None
        field_src = EntityField(
            IngestionStoreMapping, IngestionStoreMapping.Fields.SOURCE_ID
        )
        rows: list[IngestionStoreMapping] = (
            self.repository.get(IngestionStoreMapping)
            .all(field_src.eq(source_id))
        )
        rows.sort(key=lambda r: (r.store_id is not None, r.external_name))
        store_ids = {r.store_id for r in rows if r.store_id is not None}
        stores_by_id: dict[UUID, Store] = {}
        if store_ids:
            stores_by_id = {
                s.id: s for s in self.repository.get(Store).all(
                    EntityField(Store, "id").in_(list(store_ids))
                )
            }
        return [
            StoreMappingDto.from_entity(
                r, stores_by_id.get(r.store_id) if r.store_id else None
            )
            for r in rows
        ]


@dataclass(slots=True)
class UpsertStoreMappingResult:
    """Typed outcome (R-010) — the `(dto, "source_not_found" | …)` tuple this
    replaced is the shape 13-R1's 500 came from (finalisation 16-R28)."""
    mapping: StoreMappingDto | None = None
    source_not_found: bool = False
    store_not_found: bool = False


class UpsertStoreMappingHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(
        self, source_id: UUID, req: UpsertStoreMappingRequest
    ) -> UpsertStoreMappingResult:
        if self.repository.get(IngestionSource).by_id(source_id) is None:
            return UpsertStoreMappingResult(source_not_found=True)

        store: Store | None = None
        if req.store_id is not None:
            store = self.repository.get(Store).by_id(req.store_id)
            if store is None:
                return UpsertStoreMappingResult(store_not_found=True)

        existing = find_store_mapping(self.repository, source_id, req.external_name)
        if existing is None:
            mapping = IngestionStoreMapping(
                source_id=source_id,
                external_name=req.external_name,
                store_id=req.store_id,
                created_at=datetime.now(timezone.utc),
                last_seen_at=None,
            )
            self.repository.add(mapping)
        else:
            existing.store_id = req.store_id
            mapping = existing
        self.repository.save_changes()
        return UpsertStoreMappingResult(mapping=StoreMappingDto.from_entity(mapping, store))


class DeleteStoreMappingHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, source_id: UUID, mapping_id: UUID) -> bool:
        field_src = EntityField(
            IngestionStoreMapping, IngestionStoreMapping.Fields.SOURCE_ID
        )
        target: IngestionStoreMapping | None = (
            self.repository.get(IngestionStoreMapping)
            .one(EntityField(IngestionStoreMapping, "id").eq(mapping_id)
                 & field_src.eq(source_id))
        )
        if target is None:
            return False
        self.repository.remove(target)
        self.repository.save_changes()
        return True


# ── Routes ─────────────────────────────────────────────────────────────


@INGESTION_SOURCE_ROUTER.route("<uuid:source_id>/store-mappings", methods=["GET"])
def list_store_mappings(source_id: UUID):
    _, err = require_admin()
    if err is not None:
        return err
    items = ListStoreMappingsHandler(SqlAlchemyRepository()).handle(source_id)
    if items is None:
        return not_found("IngestionSource", source_id)
    return {"items": [asdict(it) for it in items]}


@INGESTION_SOURCE_ROUTER.route("<uuid:source_id>/store-mappings", methods=["PUT"])
@has_request_body(UpsertStoreMappingRequest)
def upsert_store_mapping(source_id: UUID):
    _, err = require_admin()
    if err is not None:
        return err
    req: UpsertStoreMappingRequest = get_request_body()
    outcome = UpsertStoreMappingHandler(SqlAlchemyRepository()).handle(source_id, req)
    if outcome.source_not_found:
        return not_found("IngestionSource", source_id)
    if outcome.store_not_found or outcome.mapping is None:
        return bad_request("store_id does not match any existing Store.")
    result = outcome.mapping
    _LOGGER.info(
        "Upserted store mapping %s for source %s (external=%s, store=%s)",
        result.id, source_id, result.external_name, result.store_id,
    )
    return asdict(result)


@INGESTION_SOURCE_ROUTER.route(
    "<uuid:source_id>/store-mappings/<uuid:mapping_id>", methods=["DELETE"]
)
def delete_store_mapping(source_id: UUID, mapping_id: UUID):
    _, err = require_admin()
    if err is not None:
        return err
    deleted = DeleteStoreMappingHandler(SqlAlchemyRepository()).handle(source_id, mapping_id)
    if not deleted:
        return not_found("IngestionStoreMapping", mapping_id)
    return no_content()
