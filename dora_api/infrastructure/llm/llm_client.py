from abc import ABC, abstractmethod
from time import time

# A client is built per request, so an availability probe cached on the
# instance never got reused and every `/ask` paid a network round trip (up to
# 3 s) before the chat (finalisation 11-R43). Shared per endpoint instead.
_AVAILABILITY_TTL_SECONDS = 60
_availability: dict[tuple, tuple[float, bool]] = {}


def remembered_availability(key: tuple) -> bool | None:
    """The last probe result for this endpoint, or None when stale or unknown."""
    entry = _availability.get(key)
    if entry is None or time() - entry[0] >= _AVAILABILITY_TTL_SECONDS:
        return None
    return entry[1]


def remember_availability(key: tuple, available: bool) -> None:
    _availability[key] = (time(), available)


class LlmUnavailable(Exception):
    """Raised when the model can't be reached or returns nothing usable. Callers
    catch this to fall back to the rule-based assistant rather than erroring."""


class LlmClient(ABC):
    """Narrow interface every model backend must satisfy: a reachability probe
    and a tool-aware chat turn. `chat` raises `LlmUnavailable` on transport
    failure so the assistant can degrade to its rule-based fallback cleanly.
    """

    @abstractmethod
    def is_available(self) -> bool:
        """Cheap reachability probe. Must not raise."""

    @abstractmethod
    def list_models(self) -> list[str]:
        """Names of models the endpoint has available. Raises `LlmUnavailable`
        if the endpoint can't be reached. Used by the admin Settings page to
        confirm a connection and offer a model picker."""

    @abstractmethod
    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """Run one chat turn and return the assistant message dict.

        `messages` is the running conversation (role/content, plus tool results).
        When `tools` is provided the model may respond with `tool_calls` instead
        of `content` — the caller runs those tools and feeds results back. The
        returned dict mirrors the provider's message: at least `content`, and
        `tool_calls` when the model chose to call a function.
        """
        ...
