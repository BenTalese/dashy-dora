"""Google Gemini ``generateContent`` client.

FU-153 §7.4 — Gemini's schema differs further from OpenAI's:

  * The endpoint is ``/v1beta/models/<model>:generateContent`` (model in
    the URL, not the body) and auth is via ``?key=<api-key>``.
  * Messages use ``contents[]`` with ``role`` of ``'user'`` or ``'model'``
    (no system role — system prompt goes into a top-level
    ``systemInstruction`` field).
  * Tools are declared as ``tools: [{ functionDeclarations: [...] }]``.
    Each declaration uses ``parameters`` like OpenAI's JSON Schema.
  * Tool calls come back as ``candidates[0].content.parts[].functionCall
    = { name, args }`` interleaved with text parts.
  * Tool results round-trip as parts with ``functionResponse =
    { name, response: {...} }``.

The adapter flattens text + ``functionCall`` parts into the OpenAI-shape
``{role, content, tool_calls?}`` ``ask_assistant`` already consumes.
"""
import json
import logging
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from dora_api.infrastructure.llm.llm_client import (LlmClient, LlmUnavailable,
                                                 remember_availability,
                                                 remembered_availability)


_LOGGER = logging.getLogger(__name__)
DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com"
# Curated tool-capable Gemini models. Picker hint; users can also
# type a model id manually in Settings.
_DEFAULT_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.0-pro",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]


class GeminiClient(LlmClient):
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
        available = False
        try:
            # /v1beta/models is the cheapest auth-gated probe.
            url = f"{self._base_url}/v1beta/models?key={quote(self._api_key)}"
            with urlopen(Request(url, method="GET"), timeout=3) as resp:
                available = resp.status == 200
        except (URLError, OSError, ValueError) as exc:
            _LOGGER.debug("Gemini not reachable: %s", exc)
        remember_availability(self._availability_key, available)
        return available

    def list_models(self) -> list[str]:
        try:
            url = f"{self._base_url}/v1beta/models?key={quote(self._api_key)}"
            with urlopen(Request(url, method="GET"), timeout=self._timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (URLError, OSError, ValueError):
            # Gemini lists 30+ models including embedding-only entries;
            # if the live call fails, fall back to the curated snapshot.
            return list(_DEFAULT_MODELS)
        models = data.get("models") or []
        names = sorted({
            m["name"].replace("models/", "")
            for m in models
            if isinstance(m, dict) and isinstance(m.get("name"), str)
            and "gemini" in m["name"]
            # Filter to chat-capable models (most expose generateContent).
            and "generateContent" in (m.get("supportedGenerationMethods") or [])
        })
        return names or list(_DEFAULT_MODELS)

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        if not self._enabled or not self._api_key:
            raise LlmUnavailable("Gemini is disabled or missing API key.")

        system_prompt, contents = _split_system_and_convert(messages)
        gemini_tools = _convert_tools(tools) if tools else None

        payload: dict = {
            "contents": contents,
            "generationConfig": {"temperature": 0.2},
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        if gemini_tools:
            payload["tools"] = gemini_tools

        try:
            body = json.dumps(payload).encode("utf-8")
            url = (
                f"{self._base_url}/v1beta/models/"
                f"{quote(self._model)}:generateContent?key={quote(self._api_key)}"
            )
            req = Request(
                url,
                data=body,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urlopen(req, timeout=self._timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (URLError, OSError, ValueError) as exc:
            remember_availability(self._availability_key, False)
            raise LlmUnavailable(f"Gemini request failed: {exc}") from exc

        return _to_openai_shape(data)


def _split_system_and_convert(messages: list[dict]) -> tuple[str, list[dict]]:
    """OpenAI-shape messages → Gemini-shape contents. System messages
    are pulled out as a single concatenated systemInstruction; tool
    results round-trip as functionResponse parts; assistant tool_calls
    round-trip as functionCall parts."""
    system_parts: list[str] = []
    out: list[dict] = []
    for m in messages:
        role = m.get("role")
        if role == "system":
            c = m.get("content")
            if isinstance(c, str):
                system_parts.append(c)
            continue
        if role == "tool":
            content = m.get("content")
            if isinstance(content, str):
                try:
                    parsed = json.loads(content)
                    response_obj = parsed if isinstance(parsed, dict) else {"result": parsed}
                except json.JSONDecodeError:
                    response_obj = {"result": content}
            else:
                response_obj = content if isinstance(content, dict) else {"result": content}
            out.append({
                "role": "user",
                "parts": [{
                    "functionResponse": {
                        "name": str(m.get("name") or ""),
                        "response": response_obj,
                    },
                }],
            })
            continue
        if role == "assistant" and m.get("tool_calls"):
            parts: list[dict] = []
            if isinstance(m.get("content"), str) and m["content"]:
                parts.append({"text": m["content"]})
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
                parts.append({
                    "functionCall": {
                        "name": fn.get("name") or "",
                        "args": args,
                    },
                })
            out.append({"role": "model", "parts": parts})
            continue
        gemini_role = "model" if role == "assistant" else "user"
        content = m.get("content")
        text = content if isinstance(content, str) else json.dumps(content)
        out.append({"role": gemini_role, "parts": [{"text": text}]})
    return "\n\n".join(system_parts), out


def _convert_tools(tools: list[dict]) -> list[dict]:
    """OpenAI-shape tool schemas → Gemini-shape. All declarations go
    into a single ``functionDeclarations`` array under one tool entry."""
    declarations: list[dict] = []
    for t in tools:
        fn = (t or {}).get("function") or {}
        declarations.append({
            "name": fn.get("name") or "",
            "description": fn.get("description") or "",
            "parameters": fn.get("parameters") or {"type": "object", "properties": {}},
        })
    return [{"functionDeclarations": declarations}]


def _to_openai_shape(response: dict) -> dict:
    """Flatten Gemini's first candidate's parts[] into an OpenAI-style
    `{role, content, tool_calls?}` message."""
    candidates = response.get("candidates") or []
    if not candidates:
        raise LlmUnavailable("Gemini returned no candidates.")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text_parts: list[str] = []
    tool_calls: list[dict] = []
    for idx, part in enumerate(parts):
        if not isinstance(part, dict):
            continue
        if isinstance(part.get("text"), str):
            text_parts.append(part["text"])
        elif isinstance(part.get("functionCall"), dict):
            fc = part["functionCall"]
            tool_calls.append({
                # Gemini doesn't issue tool-call ids; synthesise a stable
                # one so round-tripped functionResponses (above) can be
                # matched if a caller ever needs it.
                "id": f"gemini-call-{idx}",
                "type": "function",
                "function": {
                    "name": str(fc.get("name") or ""),
                    # ask_assistant._parse_tool_call accepts a dict.
                    "arguments": fc.get("args") or {},
                },
            })
    message: dict = {
        "role": "assistant",
        "content": "\n".join(text_parts),
    }
    if tool_calls:
        message["tool_calls"] = tool_calls
    return message
