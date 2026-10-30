"""Per-user LLM client factory.

FU-153 §7.4 — ``ask_assistant`` calls ``build_assistant_client(user)``
and gets back a configured ``LlmClient`` for whatever provider the user
picked. The factory keeps the assistant handler oblivious to the
provider matrix: it talks to one ABC.

Behaviour summary, by which knobs the user has set:

  * ``user.llm_enabled`` is False → unavailable. The user has opted out.
  * ``user.llm_provider`` is unset → unavailable. The user enabled AI
    mode but never finished the setup. Fall back without crashing.
  * Provider needs an API key and the install hasn't configured
    ``DORA_SECRET_ENCRYPTION_KEY`` → unavailable. The saved key can't
    be decrypted.
  * Provider needs an API key and the saved blob can't be decrypted
    (key rotated, blob corrupt) → unavailable.

In every "unavailable" branch the factory returns a sentinel
``_UnavailableClient`` whose ``is_available()`` returns False and whose
``chat()`` raises ``LlmUnavailable``. The existing per-request safety
net in ``AssistantHandler`` already handles that — the user sees the
rule-based fallback (and, once §7.2 lands, a banner explaining why).
"""
import logging
from urllib.parse import urlparse

from dora_api.domain.entities.user import (
    LLM_PROVIDER_ANTHROPIC,
    LLM_PROVIDER_GEMINI,
    LLM_PROVIDER_OLLAMA,
    LLM_PROVIDER_OPENAI,
    LLM_PROVIDERS_REQUIRING_API_KEY,
    User,
)
from dora_api.domain.entities.user_llm_provider import UserLlmProvider
from dora_api.infrastructure.llm import anthropic_client, gemini_client, openai_client
from dora_api.infrastructure.llm.anthropic_client import AnthropicClient
from dora_api.infrastructure.llm.gemini_client import GeminiClient
from dora_api.infrastructure.security.secret_encryption import (
    EncryptionFailed,
    EncryptionUnavailable,
    decrypt,
)
from dora_api.infrastructure.llm.llm_client import LlmClient, LlmUnavailable
from dora_api.infrastructure.llm.ollama_client import OllamaClient
from dora_api.infrastructure.llm.openai_client import OpenAiClient


_LOGGER = logging.getLogger(__name__)

# Outbound network timeout for an LLM request. Long enough for a slow
# self-hosted Ollama, short enough that a downed paid API doesn't lock
# the chat turn forever.
_REQUEST_TIMEOUT_SECONDS = 60


# What the settings page shows as placeholders: the endpoint a client falls
# back to when the base URL is left empty, and an example model id. Served by
# `/assistant/providers` so the SPA doesn't keep its own copy (11-R16).
PROVIDER_DEFAULTS: dict[str, tuple[str, str]] = {
    LLM_PROVIDER_OLLAMA: ("", "qwen2.5:7b"),
    LLM_PROVIDER_OPENAI: (openai_client.DEFAULT_BASE_URL, "gpt-4o-mini"),
    LLM_PROVIDER_ANTHROPIC: (anthropic_client.DEFAULT_BASE_URL, "claude-3-5-sonnet-20241022"),
    LLM_PROVIDER_GEMINI: (gemini_client.DEFAULT_BASE_URL, "gemini-2.0-flash"),
}


_BASE_URL_SCHEMES = ("http", "https")
BASE_URL_SCHEME_MESSAGE = "The base URL must be an http:// or https:// address."


def is_http_base_url(base_url: str) -> bool:
    """Provider endpoints are only ever reached over HTTP(S). `urlopen` also
    honours `file://` (and a `#` fragment swallows the appended API path), so
    an unchecked base URL turned the probe into a server-side file-existence
    oracle."""
    try:
        parsed = urlparse(base_url.strip())
    except ValueError:
        return False
    return parsed.scheme.lower() in _BASE_URL_SCHEMES and bool(parsed.netloc)


def unavailable_client(reason: str) -> LlmClient:
    """The sentinel for callers outside the factory (the assistant's own
    sign-in checks; finalisation 11-R32)."""
    return _UnavailableClient(reason)


class _UnavailableClient(LlmClient):
    """Sentinel returned when the factory can't build a real client.

    Reads as 'available=False' so the assistant handler routes to its
    rule-based fallback; ``chat()`` raises ``LlmUnavailable`` as a
    belt-and-braces (the handler shouldn't be calling it after seeing
    is_available()=False, but if it does, we degrade cleanly).

    FU-330 — the human-readable ``reason`` is surfaced via
    ``/api/assistant/status`` so the chat banner can explain why AI
    mode degraded ("LLM at <host> didn't respond" beats silence)."""

    def __init__(self, reason: str):
        self._reason = reason

    @property
    def reason(self) -> str:
        return self._reason

    def is_available(self) -> bool:
        return False

    def list_models(self) -> list[str]:
        raise LlmUnavailable(self._reason)

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        raise LlmUnavailable(self._reason)


def build_assistant_client(user: User, config: UserLlmProvider | None) -> LlmClient:
    """Construct an LlmClient for the given user + active-provider config.

    AI mode is gated solely by the user's own ``llm_enabled`` opt-in — there
    is no install-wide master switch (removed 2026-08-12). ``config`` is the
    user's ``UserLlmProvider`` row for ``user.llm_provider`` (the active
    provider); the caller loads it. None means the active provider has no
    saved config.
    """
    if not user.llm_enabled:
        return _UnavailableClient("AI mode is off for this user.")
    if not user.llm_provider:
        return _UnavailableClient("AI mode is on but no provider is configured.")
    if config is None:
        return _UnavailableClient("AI mode is on but the provider isn't configured yet.")

    provider = user.llm_provider

    if provider in LLM_PROVIDERS_REQUIRING_API_KEY:
        if not config.api_key_encrypted:
            return _UnavailableClient(
                f"AI mode is on but the {provider} API key is missing."
            )
        try:
            api_key = decrypt(config.api_key_encrypted)
        except (EncryptionUnavailable, EncryptionFailed) as exc:
            _LOGGER.warning("API-key decryption failed for user %s: %s", user.id, exc)
            return _UnavailableClient(str(exc))
    else:
        api_key = ""

    return build_assistant_client_from_provider(
        provider=provider,
        model=config.model or "",
        base_url=config.base_url or None,
        api_key=api_key,
    )


def build_assistant_client_from_provider(
    *,
    provider: str,
    model: str,
    base_url: str | None,
    api_key: str,
) -> LlmClient:
    """Direct constructor without a User. Used by the per-user probe
    (`assistant/probe_assistant.py`) and by tests so they can build a client
    without hydrating a full row."""
    if base_url and not is_http_base_url(base_url):
        return _UnavailableClient(BASE_URL_SCHEME_MESSAGE)
    if provider == LLM_PROVIDER_OLLAMA:
        if not base_url or not model:
            return _UnavailableClient("Ollama needs a base URL and a model.")
        return OllamaClient(
            base_url=base_url,
            model=model,
            timeout_seconds=_REQUEST_TIMEOUT_SECONDS,
            enabled=True,
        )
    if provider == LLM_PROVIDER_OPENAI:
        if not api_key or not model:
            return _UnavailableClient("OpenAI needs an API key and a model.")
        return OpenAiClient(
            api_key=api_key,
            model=model,
            timeout_seconds=_REQUEST_TIMEOUT_SECONDS,
            enabled=True,
            base_url=base_url,
        )
    if provider == LLM_PROVIDER_ANTHROPIC:
        if not api_key or not model:
            return _UnavailableClient("Anthropic needs an API key and a model.")
        return AnthropicClient(
            api_key=api_key,
            model=model,
            timeout_seconds=_REQUEST_TIMEOUT_SECONDS,
            enabled=True,
            base_url=base_url,
        )
    if provider == LLM_PROVIDER_GEMINI:
        if not api_key or not model:
            return _UnavailableClient("Gemini needs an API key and a model.")
        return GeminiClient(
            api_key=api_key,
            model=model,
            timeout_seconds=_REQUEST_TIMEOUT_SECONDS,
            enabled=True,
            base_url=base_url,
        )
    return _UnavailableClient(f"Unknown LLM provider '{provider}'.")
