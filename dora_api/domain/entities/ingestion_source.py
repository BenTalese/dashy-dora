from dataclasses import dataclass
from datetime import datetime

from dora_api.domain.entities.base_entity import BaseEntity


TRUST_HIGH = "high"
TRUST_LOW = "low"
ALLOWED_TRUSTS = (TRUST_HIGH, TRUST_LOW)


@dataclass
class IngestionSource(BaseEntity):
    """An admin-minted bearer credential used by an external producer to push
    products and offers into Dora via `POST /api/ingest` (observations left
    the producer path at J1). The raw
    key is shown once at creation; only its SHA-256 lives at rest. `trust`
    is captured now (high = admin's own data, low = future crowd sources);
    enforcement is deferred per PROPOSAL_INGESTION_API §2.6.
    """
    label: str
    key_hash: str
    enabled: bool
    trust: str
    created_at: datetime
    last_used_at: datetime | None = None
    accepted_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0

    class Fields(BaseEntity.Fields):
        LABEL = "label"
        KEY_HASH = "key_hash"
        ENABLED = "enabled"
        TRUST = "trust"
        CREATED_AT = "created_at"
        LAST_USED_AT = "last_used_at"
        ACCEPTED_COUNT = "accepted_count"
        SKIPPED_COUNT = "skipped_count"
        FAILED_COUNT = "failed_count"
