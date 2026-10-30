import json
import logging
from urllib.error import URLError
from urllib.request import Request, urlopen

from dora_api.infrastructure.llm.llm_client import (LlmClient, LlmUnavailable,
                                                 is_provider_down,
                                                 remember_availability,
                                                 remembered_availability)

_LOGGER = logging.getLogger(__name__)


class OllamaClient(LlmClient):
    """Talks to a local Ollama server over its HTTP API.

    Uses /api/chat with streaming disabled. When `tools` are passed, Ollama
    returns `message.tool_calls` for tool-capable models (qwen2.5, llama3.1,
    etc.) — so the model itself decides whether to call a function or reply
    directly. Low temperature keeps that decision stable.
    """

    def __init__(self, base_url: str, model: str, timeout_seconds: int, enabled: bool):
        self._base_url = base_url
        self._model = model
        self._timeout = timeout_seconds
        self._enabled = enabled
        # Reachability is remembered per endpoint (`llm_client`), so a chat
        # turn doesn't probe every request and a downed server doesn't stall
        # each one with a fresh timeout.
        self._availability_key = (type(self).__name__, self._base_url, self._model)

    def is_available(self) -> bool:
        if not self._enabled:
            return False
        remembered = remembered_availability(self._availability_key)
        if remembered is not None:
            return remembered
        available = False
        try:
            req = Request(f"{self._base_url}/api/tags", method="GET")
            with urlopen(req, timeout=3) as resp:
                available = resp.status == 200
        except (URLError, OSError, ValueError) as exc:
            _LOGGER.debug("Ollama not reachable: %s", exc)
        remember_availability(self._availability_key, available)
        return available

    def list_models(self) -> list[str]:
        # Not gated on `_enabled`: this is a connectivity/discovery probe the
        # admin Settings page uses before saving (and before enabling).
        data = self._get("/api/tags")
        models = data.get("models") or []
        names = [m["name"] for m in models if isinstance(m, dict) and m.get("name")]
        return sorted(names)

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        if not self._enabled:
            raise LlmUnavailable("LLM is disabled in configuration.")

        payload: dict = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.2},
        }
        if tools:
            payload["tools"] = tools

        data = self._post("/api/chat", payload)
        message = data.get("message")
        if not isinstance(message, dict):
            raise LlmUnavailable("Ollama returned no message.")
        return message

    def _post(self, path: str, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        req = Request(
            f"{self._base_url}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return self._send(req)

    def _get(self, path: str) -> dict:
        return self._send(Request(f"{self._base_url}{path}", method="GET"))

    def _send(self, req: Request) -> dict:
        try:
            with urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (URLError, OSError, ValueError) as exc:
            if is_provider_down(exc):
                remember_availability(self._availability_key, False)
            raise LlmUnavailable(f"Ollama request failed: {exc}") from exc
