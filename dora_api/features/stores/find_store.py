"""Store lookup by name: trimmed and case-insensitive, the one rule create,
rename and the manual product-add all use (R-003)."""
from dora_api.domain.entities.store import Store
from dora_api.infrastructure.ports import Repository


def find_store_by_name(repository: Repository, name: str) -> Store | None:
    normalised = name.strip().lower()
    return next(
        (s for s in repository.get(Store).all() if s.name.strip().lower() == normalised),
        None,
    )
