"""Admin CRUD over `IngestionSource` (C-10.1).

The "API access" Settings page consumes these endpoints. They are
**always admin-accessible** — not gated by `features.products`
(PROPOSAL_PRODUCTS_AS_OVERLAY §4.3): an admin needs to mint a key
*before* any product data exists, so the producer can push the first
batch that lights the product surfaces up.

Routes:
- `GET    /api/ingestion-sources`        — list (no key material).
- `POST   /api/ingestion-sources`        — create; returns the raw key
                                            **once**, never again.
- `PATCH  /api/ingestion-sources/<id>`   — relabel / enable / disable.
- `DELETE /api/ingestion-sources/<id>`   — revoke (hard delete; the key
                                            is then useless).

The invisibility rule (PROPOSAL §header) is honoured: nothing in the
DTOs, copy, or errors references a scraper / companion / producer.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.ingestion_source import (ALLOWED_TRUSTS,
                                                       TRUST_HIGH,
                                                       IngestionSource)
from dora_api.features.auth.admin_gate import require_admin
from dora_api.features.routers import INGESTION_SOURCE_ROUTER
from dora_api.infrastructure.api_response import (bad_request, no_content,
                                                  not_found)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.ingestion_auth import (hash_ingestion_key,
                                                    mint_ingestion_key)
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


# ── DTOs ───────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class IngestionSourceDto:
    """Public shape — the `key_hash` never leaves the server."""
    id: UUID
    label: str
    enabled: bool
    trust: str
    created_at: datetime
    last_used_at: datetime | None
    accepted_count: int
    skipped_count: int
    failed_count: int

    @classmethod
    def from_entity(cls, src: IngestionSource) -> "IngestionSourceDto":
        return cls(
            id=src.id,
            label=src.label,
            enabled=src.enabled,
            trust=src.trust,
            created_at=src.created_at,
            last_used_at=src.last_used_at,
            accepted_count=src.accepted_count,
            skipped_count=src.skipped_count,
            failed_count=src.failed_count,
        )


@dataclass(frozen=True, slots=True)
class CreateIngestionSourceResponse:
    """The raw `key` field is the **only** time the admin sees it; the
    client must surface it immediately and warn that it won't be shown
    again."""
    source: IngestionSourceDto
    key: str


# ── Requests ───────────────────────────────────────────────────────────

class CreateIngestionSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=255)
    trust: str = Field(default=TRUST_HIGH)


class UpdateIngestionSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = Field(default=None, min_length=1, max_length=255)
    enabled: bool | None = None


# ── Handlers ───────────────────────────────────────────────────────────

class ListIngestionSourcesHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self) -> list[IngestionSourceDto]:
        rows: list[IngestionSource] = (
            self.repository.get(IngestionSource).all()
        )
        rows.sort(key=lambda r: r.created_at)
        return [IngestionSourceDto.from_entity(r) for r in rows]


class CreateIngestionSourceHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, req: CreateIngestionSourceRequest) -> CreateIngestionSourceResponse:
        raw = mint_ingestion_key()
        entity = IngestionSource(
            id=uuid4(),
            label=req.label.strip(),
            key_hash=hash_ingestion_key(raw),
            enabled=True,
            trust=req.trust,
            created_at=datetime.now(timezone.utc),
        )
        self.repository.add(entity)
        self.repository.save_changes()
        return CreateIngestionSourceResponse(
            source=IngestionSourceDto.from_entity(entity),
            key=raw,
        )


class UpdateIngestionSourceHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, source_id: UUID, req: UpdateIngestionSourceRequest) -> IngestionSourceDto | None:
        target: IngestionSource | None = (
            self.repository.get(IngestionSource).by_id(source_id)
        )
        if target is None:
            return None
        set_fields = req.model_dump(exclude_unset=True)
        if "label" in set_fields and req.label is not None:
            target.label = req.label.strip()
        if "enabled" in set_fields and req.enabled is not None:
            target.enabled = req.enabled
        self.repository.save_changes()
        return IngestionSourceDto.from_entity(target)


class DeleteIngestionSourceHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, source_id: UUID) -> bool:
        target: IngestionSource | None = (
            self.repository.get(IngestionSource).by_id(source_id)
        )
        if target is None:
            return False
        self.repository.remove(target)
        self.repository.save_changes()
        return True


# ── Routes ─────────────────────────────────────────────────────────────

@INGESTION_SOURCE_ROUTER.route("", methods=["GET"])
def list_ingestion_sources():
    _, err = require_admin()
    if err is not None:
        return err
    items = ListIngestionSourcesHandler(SqlAlchemyRepository()).handle()
    return {"items": [asdict(it) for it in items]}


@INGESTION_SOURCE_ROUTER.route("", methods=["POST"])
@has_request_body(CreateIngestionSourceRequest)
def create_ingestion_source():
    _, err = require_admin()
    if err is not None:
        return err
    req: CreateIngestionSourceRequest = get_request_body()
    if req.trust not in ALLOWED_TRUSTS:
        return bad_request(f"trust must be one of {ALLOWED_TRUSTS}.")
    result = CreateIngestionSourceHandler(SqlAlchemyRepository()).handle(req)
    _LOGGER.info(
        "Minted IngestionSource %s (label=%s, trust=%s)",
        result.source.id, result.source.label, result.source.trust,
    )
    return {"source": asdict(result.source), "key": result.key}, 201


@INGESTION_SOURCE_ROUTER.route("<uuid:source_id>", methods=["PATCH"])
@has_request_body(UpdateIngestionSourceRequest)
def update_ingestion_source(source_id: UUID):
    _, err = require_admin()
    if err is not None:
        return err
    req: UpdateIngestionSourceRequest = get_request_body()
    updated = UpdateIngestionSourceHandler(SqlAlchemyRepository()).handle(source_id, req)
    if updated is None:
        return not_found("IngestionSource", source_id)
    return asdict(updated)


@INGESTION_SOURCE_ROUTER.route("<uuid:source_id>", methods=["DELETE"])
def delete_ingestion_source(source_id: UUID):
    _, err = require_admin()
    if err is not None:
        return err
    deleted = DeleteIngestionSourceHandler(SqlAlchemyRepository()).handle(source_id)
    if not deleted:
        return not_found("IngestionSource", source_id)
    _LOGGER.info("Revoked IngestionSource %s", source_id)
    return no_content()
