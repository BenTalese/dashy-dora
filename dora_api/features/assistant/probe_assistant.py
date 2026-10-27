"""POST /api/assistant/probe — per-user "Test connection" probe.

FU-332 — the per-user `AssistantSettings.vue` page needs a way to test
a configured provider (or test draft values the user is about to save)
without going through the full chat round-trip. Lives at
``/api/assistant/probe`` (not the existing admin-only
``/api/app-settings/probe`` — that one's gated behind admin auth as an
SSRF mitigation; the per-user version layers rate-limiting + audit
logging instead).

Threat model:

  * The probe is reachable to any authenticated session. An
    authenticated household member could call it to probe internal
    URLs from the backend's network position (SSRF).
  * Mitigations:
      - Rate limit: 10 probes/minute per user (matches the deal of
        "test, fix the URL, test again" pacing; lockout returns 429).
      - Audit log: every probe writes a row with the user id +
        target URL host, so abuse leaves a trail.
      - No allowlist enforced — household installs legitimately probe
        loopback + LAN URLs (`localhost:11434`, `192.168.1.5:11434`),
        which a generic allowlist would block. The audit log + rate
        cap are the deliberate trade-off.

Request shape:

    {
        "provider": "ollama" | "openai" | "anthropic" | "gemini",
        "base_url": "...",        // for ollama; optional for paid
        "model": "...",           // any provider
        "api_key": "..." | null   // for paid providers; null/missing
                                  //   means "use my saved key" (so the
                                  //   masked field doesn't need to be
                                  //   re-typed every probe)
    }

Response:

    {
        "available": true | false,
        "reason": null | "...",
        "models": ["..."] | null,   // populated for Ollama after a
                                    //   successful probe so the
                                    //   Settings page can populate a
                                    //   picker
    }
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from uuid import UUID

from flask import session
from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.audit_event import SEVERITY_AUDIT
from dora_api.domain.entities.user import (ALLOWED_LLM_PROVIDERS,
                                           LLM_PROVIDERS_REQUIRING_API_KEY,
                                           User)
from dora_api.features.assistant.providers import get_provider_config
from dora_api.infrastructure.session_user import SESSION_USER_ID_KEY
from dora_api.features.routers import ASSISTANT_ROUTER
from dora_api.infrastructure.api_response import (ok, too_many_requests,
                                                  unauthorized)
from dora_api.infrastructure.audit import emit as audit_emit
from dora_api.infrastructure.auth_helpers import (rate_limit,
                                                  rate_limit_remaining_seconds)
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.llm import (EncryptionFailed,
                                         EncryptionUnavailable,
                                         LlmUnavailable,
                                         build_assistant_client_from_provider,
                                         decrypt_api_key)
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository


_LOGGER = logging.getLogger(__name__)
_PROBE_TIMEOUT_SECONDS = 8
_PROBES_PER_MINUTE = 10
_RATE_SCOPE = "assistant.probe"


class ProbeAssistantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1, max_length=16)
    base_url: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, max_length=255)
    # When `api_key` is omitted/null, the handler falls back to the
    # saved encrypted blob for paid providers — lets the SPA call
    # probe() repeatedly without re-typing the masked field.
    api_key: str | None = Field(default=None, max_length=512)


@dataclass(frozen=True, slots=True)
class ProbeAssistantResponse:
    available: bool
    reason: str | None = None
    # Only populated for Ollama (which exposes /api/tags). Paid
    # providers return their curated list; the Settings page already
    # shows the picker pre-populated when the provider is selected, so
    # we don't need to round-trip that list through every probe.
    models: list[str] | None = None


class ProbeAssistantHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: ProbeAssistantRequest, user_id: UUID) -> ProbeAssistantResponse:
        user: User | None = self.repository.get(User).by_id(user_id)
        if user is None:
            return ProbeAssistantResponse(available=False, reason="User not found.")

        provider = request.provider.strip()
        if provider not in ALLOWED_LLM_PROVIDERS:
            return ProbeAssistantResponse(
                available=False,
                reason=f"Unknown provider '{provider}'.",
            )

        # The saved row is the source of truth for details + where the
        # verified flag lives; the request may carry draft overrides (the
        # user is testing before/while saving).
        row = get_provider_config(self.repository, user_id, provider)

        # API-key resolution: prefer the body's plaintext (user is
        # testing a freshly-typed value), fall back to the saved
        # encrypted blob (user is testing what they already saved).
        api_key = ""
        if provider in LLM_PROVIDERS_REQUIRING_API_KEY:
            if request.api_key is not None and request.api_key.strip():
                api_key = request.api_key.strip()
            elif row is not None and row.api_key_encrypted is not None:
                try:
                    api_key = decrypt_api_key(row.api_key_encrypted)
                except EncryptionUnavailable as exc:
                    return ProbeAssistantResponse(available=False, reason=str(exc))
                except EncryptionFailed as exc:
                    return ProbeAssistantResponse(available=False, reason=str(exc))
            if not api_key:
                return ProbeAssistantResponse(
                    available=False,
                    reason=f"{provider} needs an API key. Paste one or save it first.",
                )

        base_url = (request.base_url or "").strip() or (row.base_url if row else None)
        model = (request.model or "").strip() or (row.model if row else "") or ""
        if not model:
            return ProbeAssistantResponse(
                available=False,
                reason="A model name is required to probe.",
            )

        result = self._probe(provider, model, base_url, api_key)

        # Persist the outcome onto the saved row so the Mode picker knows
        # which providers are usable. A successful probe verifies the row;
        # a failure clears the flag (settings drifted or the server went
        # away). No row yet (pure draft test) → nothing to persist.
        if row is not None:
            row.verified = result.available
            row.verified_at = datetime.now(timezone.utc) if result.available else None
            self.repository.save_changes()

        return result

    def _probe(
        self, provider: str, model: str, base_url: str | None, api_key: str
    ) -> ProbeAssistantResponse:
        client = build_assistant_client_from_provider(
            provider=provider,
            model=model,
            base_url=base_url,
            api_key=api_key,
        )

        # _UnavailableClient (factory sentinel) carries its own reason
        # for config-shape failures — surface that verbatim before
        # paying the network round-trip.
        if hasattr(client, "reason") and not client.is_available():
            return ProbeAssistantResponse(
                available=False,
                reason=getattr(client, "reason"),
            )

        try:
            models = client.list_models() if provider == "ollama" else None
        except LlmUnavailable as exc:
            return ProbeAssistantResponse(available=False, reason=str(exc))

        # `is_available()` does its own quick probe for paid providers
        # (a /models call or a 1-token POST); a failure surfaces as
        # available=False with a friendly fallback reason.
        if not client.is_available():
            return ProbeAssistantResponse(
                available=False,
                reason="Couldn't reach the provider with these settings.",
            )

        return ProbeAssistantResponse(available=True, models=models)


@ASSISTANT_ROUTER.route("/probe", methods=["POST"])
@has_request_body(ProbeAssistantRequest)
def probe_assistant():
    user_id_raw = session.get(SESSION_USER_ID_KEY)
    if not user_id_raw:
        return unauthorized()
    try:
        user_id = UUID(user_id_raw)
    except (ValueError, TypeError):
        session.clear()
        return unauthorized()

    # Per-user rate limit (FU-458 — helper gained the `subject` override
    # so a shared household IP doesn't count multiple users against the
    # same bucket). Before this the code was per-IP despite the comment
    # claiming otherwise.
    _Subject = str(user_id)
    if not rate_limit(_RATE_SCOPE, _PROBES_PER_MINUTE, subject=_Subject):
        retry_after = rate_limit_remaining_seconds(
            _RATE_SCOPE, _PROBES_PER_MINUTE, subject=_Subject,
        )
        return too_many_requests(retry_after)

    request: ProbeAssistantRequest = get_request_body()
    response = ProbeAssistantHandler(SqlAlchemyRepository()).handle(request, user_id)

    # Audit-log every probe — abuse trail per the threat model in the
    # module docstring. Payload captures the provider + host (not the
    # API key, not the full URL with path) so the trail is useful
    # without leaking credentials.
    target_host: str | None = None
    if request.base_url:
        try:
            from urllib.parse import urlparse
            target_host = urlparse(request.base_url).hostname
        except (ValueError, TypeError):
            target_host = None
    audit_emit(
        "assistant.probe",
        severity=SEVERITY_AUDIT,
        actor_user_id=user_id,
        payload={
            "provider": request.provider,
            "target_host": target_host,
            "available": response.available,
        },
    )

    return ok(response)
