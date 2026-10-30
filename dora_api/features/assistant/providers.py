"""Per-user LLM-provider configuration.

  GET   /api/assistant/providers            — this user's config for every
                                              provider (stored rows merged with
                                              the four known providers, so the
                                              UI always sees all of them)
  PATCH /api/assistant/providers/<provider> — upsert one provider's details
                                              { base_url?, model?, api_key?,
                                                clear_api_key? }

Each provider's details live in their own `UserLlmProvider` row (source of
truth); `User.llm_provider` just points at the active one. Editing any field
resets `verified` to False — the row is only re-marked verified by a
successful live probe (`probe_assistant.py`), so a provider isn't offered as
a selectable Mode until it has actually answered.
"""
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from dora_api.domain.entities.user import ALLOWED_LLM_PROVIDERS
from dora_api.domain.entities.user_llm_provider import UserLlmProvider
from dora_api.features.routers import ASSISTANT_ROUTER
from dora_api.infrastructure.api_response import (bad_request,
                                                  business_rule_violation, ok,
                                                  unauthorized)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.llm import EncryptionUnavailable, encrypt_api_key
from dora_api.infrastructure.llm.factory import (BASE_URL_SCHEME_MESSAGE,
                                                 PROVIDER_DEFAULTS,
                                                 is_http_base_url)
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository
from dora_api.infrastructure.session_user import current_user_id


@dataclass(frozen=True, slots=True)
class ProviderConfigDto:
    provider: str
    base_url: str | None
    model: str | None
    has_api_key: bool
    verified: bool
    verified_at: str | None
    # Placeholders for the settings form (11-R16): the endpoint used when the
    # base URL is left empty ("" for Ollama, which has none), and an example id.
    default_base_url: str
    example_model: str

    @classmethod
    def from_row(cls, provider: str, row: UserLlmProvider | None) -> "ProviderConfigDto":
        default_base_url, example_model = PROVIDER_DEFAULTS[provider]
        if row is None:
            return cls(
                provider=provider,
                base_url=None,
                model=None,
                has_api_key=False,
                verified=False,
                verified_at=None,
                default_base_url=default_base_url,
                example_model=example_model,
            )
        return cls(
            default_base_url=default_base_url,
            example_model=example_model,
            provider=provider,
            base_url=row.base_url,
            model=row.model,
            has_api_key=row.api_key_encrypted is not None,
            verified=bool(row.verified),
            verified_at=row.verified_at.isoformat() if row.verified_at is not None else None,
        )


@dataclass(frozen=True, slots=True)
class ProvidersDto:
    providers: list[ProviderConfigDto]


class UpdateProviderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Partial edit — omit a field to leave it untouched. `api_key` write-only
    # (encrypted, never echoed); `clear_api_key` wipes the saved key.
    base_url: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, max_length=255)
    api_key: str | None = Field(default=None, max_length=512)
    clear_api_key: bool = False

    @field_validator("base_url")
    @classmethod
    def _http_base_url(cls, value: str | None) -> str | None:
        if value is not None and value.strip() and not is_http_base_url(value):
            raise ValueError(BASE_URL_SCHEME_MESSAGE)
        return value


def get_provider_config(
    repository: Repository, user_id: UUID, provider: str
) -> UserLlmProvider | None:
    """The user's row for one provider, or None if never configured."""
    return repository.get(UserLlmProvider).one(
        EntityField(UserLlmProvider, UserLlmProvider.Fields.USER_ID).eq(user_id)
        & EntityField(UserLlmProvider, UserLlmProvider.Fields.PROVIDER).eq(provider)
    )


class ProvidersHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def list_providers(self, user_id: UUID) -> ProvidersDto:
        rows: list[UserLlmProvider] = self.repository.get(UserLlmProvider).all(
            EntityField(UserLlmProvider, UserLlmProvider.Fields.USER_ID).eq(user_id)
        )
        by_provider = {row.provider: row for row in rows}
        return ProvidersDto(providers=[
            ProviderConfigDto.from_row(provider, by_provider.get(provider))
            for provider in ALLOWED_LLM_PROVIDERS
        ])

    def update_provider(
        self, user_id: UUID, provider: str, request: UpdateProviderRequest
    ) -> tuple[ProviderConfigDto | None, str | None]:
        row = get_provider_config(self.repository, user_id, provider)
        if row is None:
            row = UserLlmProvider(user_id=user_id, provider=provider)
            self.repository.add(row)

        set_fields = request.model_fields_set
        if "base_url" in set_fields:
            row.base_url = (request.base_url or "").strip() or None
        if "model" in set_fields:
            row.model = (request.model or "").strip() or None
        if request.clear_api_key:
            row.api_key_encrypted = None
        elif "api_key" in set_fields and request.api_key is not None:
            plaintext = request.api_key.strip()
            if plaintext:
                try:
                    row.api_key_encrypted = encrypt_api_key(plaintext)
                except EncryptionUnavailable as exc:
                    return None, str(exc)

        # Any change to the config invalidates the prior probe result — the
        # row must be re-probed before it can be selected as the active Mode.
        row.verified = False
        row.verified_at = None

        self.repository.save_changes()
        return ProviderConfigDto.from_row(provider, row), None


@ASSISTANT_ROUTER.route("/providers", methods=["GET"])
def get_providers():
    user_id = current_user_id()
    if user_id is None:
        return unauthorized()
    return ok(ProvidersHandler(SqlAlchemyRepository()).list_providers(user_id))


@ASSISTANT_ROUTER.route("/providers/<provider>", methods=["PATCH"])
@has_request_body(UpdateProviderRequest)
def update_provider(provider: str):
    user_id = current_user_id()
    if user_id is None:
        return unauthorized()
    if provider not in ALLOWED_LLM_PROVIDERS:
        return bad_request(f"Unknown provider '{provider}'.")

    request: UpdateProviderRequest = get_request_body()
    dto, error = ProvidersHandler(SqlAlchemyRepository()).update_provider(
        user_id, provider, request,
    )
    if error is not None:
        return business_rule_violation(error)
    return ok(dto)
