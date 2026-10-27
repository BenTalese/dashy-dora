"""Anthropic (Claude) Messages API client.

FU-153 §7.4 — Anthropic's ``/v1/messages`` differs from OpenAI's chat-
completions in three ways the adapter handles inline:

  1. The system prompt is a *top-level* ``system`` field, not a
     ``role: 'system'`` message. Strip and lift.
  2. Tool calls arrive as ``content[].type == 'tool_use'`` blocks
     interleaved with text blocks, not on a sibling ``tool_calls`` field.
     The adapter flattens text and converts ``tool_use`` blocks to the
     OpenAI shape ``tool_calls = [{id, type: 'function', function:
     {name, arguments: <json string>}}]`` so ``ask_assistant`` consumes
     it like any other provider.
  3. Tool *results* (when re-sending the conversation) need to wrap a
     ``tool_result`` content block, not a ``role: 'tool'`` message.
     Helper translates round-tripped tool results back.

The model picker doesn't hit Anthropic — they don't expose a public
``/models`` endpoint, and the list shifts often enough that hard-coding
risks rotting. ``list_models`` returns a curated snapshot of the
tool-capable Claude models; users can also type a model name manually.
"""
import json
import logging
from urllib.error import URLError
from urllib.request import Request, urlopen

from dora_api.infrastructure.llm.llm_client import (LlmClient, LlmUnavailable,
                                                 remember_availability,
                                                 remembered_availability)


_LOGGER = logging.getLogger(__name__)
DEFAULT_BASE_URL = "https://api.anthropic.com"
_API_VERSION = "2023-06-01"
# Curated tool-capable models. Update on a new Claude release; the
# user can also type a model id manually in Settings.
_DEFAULT_MODELS = [
    "claude-opus-4-20250514",
    "claude-sonnet-4-20250514",
    "claude-3-5-haiku-20241022",
    "claude-3-5-sonnet-20241022",
]


class AnthropicClient(LlmClient):
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: int = 30,
        enabled: bool = True,
        base_url: str | None = None,
    ):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds
        self._enabled = enabled
        self._base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self._availability_key = (type(self).__name__, self._base_url, self._api_key)

    def is_available(self) -> bool:
        if not self._enabled or not self._api_key:
            return False
        remembered = remembered_availability(self._availability_key)
        if remembered is not None:
            return remembered
        # Anthropic doesn't have a cheap "ping" — a tiny no-op message
        # is the standard probe. Costs ~1 input token.
        available = False
        try:
            body = json.dumps({
                "model": self._model or _DEFAULT_MODELS[1],
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "ping"}],
            }).encode("utf-8")
            req = Request(
                f"{self._base_url}/v1/messages",
                data=body,
                method="POST",
                headers={**self._headers(), "Content-Type": "application/json"},
            )
            with urlopen(req, timeout=3) as resp:
                available = resp.status == 200
        except (URLError, OSError, ValueError) as exc:
            _LOGGER.debug("Anthropic not reachable: %s", exc)
        remember_availability(self._availability_key, available)
        return available

    def list_models(self) -> list[str]:
        # No usable /models endpoint — return the curated snapshot.
        # The Settings page treats this list as a hint; the user can
        # type any model id and save it.
        return list(_DEFAULT_MODELS)

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        if not self._enabled or not self._api_key:
            raise LlmUnavailable("Anthropic is disabled or missing API key.")

        system_prompt, anthropic_messages = _split_system_and_convert(messages)
        anthropic_tools = _convert_tools(tools) if tools else None

        payload: dict = {
            "model": self._model,
            "max_tokens": 1024,
            "temperature": 0.2,
            "messages": anthropic_messages,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if anthropic_tools:
            payload["tools"] = anthropic_tools

        try:
            body = json.dumps(payload).encode("utf-8")
            req = Request(
                f"{self._base_url}/v1/messages",
                data=body,
                method="POST",
                headers={**self._headers(), "Content-Type": "application/json"},
            )
            with urlopen(req, timeout=self._timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (URLError, OSError, ValueError) as exc:
            remember_availability(self._availability_key, False)
            raise LlmUnavailable(f"Anthropic request failed: {exc}") from exc

        return _to_openai_shape(data)

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": _API_VERSION,
        }


def _split_system_and_convert(messages: list[dict]) -> tuple[str, list[dict]]:
    """Split out the system prompt (Anthropic wants it top-level) and
    convert any tool-result messages back to Anthropic's content-block
    shape. Plain user / assistant messages pass through unchanged."""
    system_parts: list[str] = []
    out: list[dict] = []
    for m in messages:
        role = m.get("role")
        if role == "system":
            content = m.get("content")
            if isinstance(content, str):
                system_parts.append(content)
            continue
        if role == "tool":
            # ask_assistant feeds tool results back as `role: 'tool'`
            # with `tool_call_id` + JSON `content`. Anthropic expects a
            # `user` message whose content is a `tool_result` block.
            out.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": m.get("tool_call_id") or "",
                    "content": str(m.get("content") or ""),
                }],
            })
            continue
        if role == "assistant" and m.get("tool_calls"):
            # Reconstruct the assistant turn that proposed the tools so
            # Anthropic can match `tool_use_id`s. Text content + each
            # tool_call as a `tool_use` block.
            content_blocks: list[dict] = []
            if isinstance(m.get("content"), str) and m["content"]:
                content_blocks.append({"type": "text", "text": m["content"]})
            for call in m["tool_calls"]:
                fn = (call or {}).get("function") or {}
                raw_args = fn.get("arguments")
                if isinstance(raw_args, str):
                    try:
                        args = json.loads(raw_args) if raw_args else {}
                    except json.JSONDecodeError:
                        args = {}
                else:
                    args = raw_args if isinstance(raw_args, dict) else {}
                content_blocks.append({
                    "type": "tool_use",
                    "id": call.get("id") or fn.get("name") or "",
                    "name": fn.get("name") or "",
                    "input": args,
                })
            out.append({"role": "assistant", "content": content_blocks})
            continue
        out.append({"role": role, "content": m.get("content")})
    return "\n\n".join(system_parts), out


def _convert_tools(tools: list[dict]) -> list[dict]:
    """OpenAI-shape tool schemas → Anthropic-shape. OpenAI's
    `{type: 'function', function: {name, description, parameters}}`
    becomes Anthropic's `{name, description, input_schema}`."""
    out: list[dict] = []
    for t in tools:
        fn = (t or {}).get("function") or {}
        out.append({
            "name": fn.get("name") or "",
            "description": fn.get("description") or "",
            "input_schema": fn.get("parameters") or {"type": "object", "properties": {}},
        })
    return out


def _to_openai_shape(response: dict) -> dict:
    """Flatten Anthropic's `content[]` into an OpenAI-style
    `{role, content, tool_calls?}` message so the rest of the
    pipeline doesn't care which provider answered."""
    blocks = response.get("content") or []
    text_parts: list[str] = []
    tool_calls: list[dict] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            t = block.get("text")
            if isinstance(t, str):
                text_parts.append(t)
        elif btype == "tool_use":
            tool_calls.append({
                "id": str(block.get("id") or ""),
                "type": "function",
                "function": {
                    "name": str(block.get("name") or ""),
                    # ask_assistant._parse_tool_call accepts either a
                    # dict or a JSON string; we send the dict.
                    "arguments": block.get("input") or {},
                },
            })
    message: dict = {
        "role": "assistant",
        "content": "\n".join(text_parts),
    }
    if tool_calls:
        message["tool_calls"] = tool_calls
    return message
