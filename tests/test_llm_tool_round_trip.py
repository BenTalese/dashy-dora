"""Round 2 of a data-tool question on a hosted provider.

The assistant appends a tool-result message after running a data tool. It
used to carry only `role` + `content`, so Anthropic got `tool_use_id: ""`,
OpenAI a tool message without `tool_call_id`, and Gemini an empty
`functionResponse.name` — every one a 400. And because `HTTPError` is a
`URLError`, that 400 then cached the provider as unavailable for the TTL.
No network here: the converters and the error classifier are pure.
"""
from urllib.error import HTTPError, URLError
from unittest.mock import MagicMock, patch

import pytest

from dora_api.features.assistant import ask_assistant
from dora_api.features.assistant.ask_assistant import _tool_result_message
from dora_api.features.assistant.tools import _bounded_days
from dora_api.infrastructure.llm import llm_client
from dora_api.infrastructure.llm.anthropic_client import (
    AnthropicClient, _split_system_and_convert as anthropic_convert)
from dora_api.infrastructure.llm.gemini_client import \
    _split_system_and_convert as gemini_convert
from dora_api.infrastructure.llm.llm_client import LlmUnavailable, is_provider_down
from dora_api.infrastructure.llm.openai_client import _convert_messages as openai_convert


_CALL = {"id": "call_abc", "type": "function",
         "function": {"name": "whats_expiring", "arguments": {"within_days": 3}}}


def _conversation() -> list[dict]:
    return [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "what's expiring?"},
        {"role": "assistant", "content": "", "tool_calls": [_CALL]},
        _tool_result_message(_CALL, "whats_expiring", '[{"name": "Milk"}]'),
    ]


def test__tool_result_message__carries_the_call_id_and_tool_name():
    message = _tool_result_message(_CALL, "whats_expiring", "[]")
    assert message == {"role": "tool", "tool_call_id": "call_abc",
                       "name": "whats_expiring", "content": "[]"}


def test__anthropic__tool_result_block_references_the_tool_use_id():
    _system, out = anthropic_convert(_conversation())
    tool_use = out[1]["content"][0]
    tool_result = out[2]["content"][0]
    assert tool_use["type"] == "tool_use" and tool_use["id"] == "call_abc"
    assert tool_result == {"type": "tool_result", "tool_use_id": "call_abc",
                           "content": '[{"name": "Milk"}]'}


def test__openai__tool_message_has_tool_call_id_and_no_name():
    out = openai_convert(_conversation())
    assert out[3] == {"role": "tool", "tool_call_id": "call_abc",
                      "content": '[{"name": "Milk"}]'}
    assert out[2]["tool_calls"][0]["id"] == "call_abc"


def test__gemini__function_response_is_named_after_the_tool():
    _system, out = gemini_convert(_conversation())
    response = out[2]["parts"][0]["functionResponse"]
    assert response["name"] == "whats_expiring"
    assert response["response"] == {"result": [{"name": "Milk"}]}


def test__is_provider_down__4xx_is_not_an_outage_but_5xx_and_transport_are():
    assert is_provider_down(HTTPError("u", 400, "Bad Request", {}, None)) is False
    assert is_provider_down(HTTPError("u", 401, "Unauthorized", {}, None)) is False
    assert is_provider_down(HTTPError("u", 503, "Unavailable", {}, None)) is True
    assert is_provider_down(URLError("connection refused")) is True
    assert is_provider_down(TimeoutError()) is True


def test__chat__a_400_does_not_cache_the_provider_as_unavailable():
    llm_client._availability.clear()
    client = AnthropicClient(api_key="k", model="m")
    with patch("dora_api.infrastructure.llm.anthropic_client.urlopen",
               side_effect=HTTPError("u", 400, "Bad Request", {}, None)):
        with pytest.raises(LlmUnavailable):
            client.chat([{"role": "user", "content": "hi"}])
    assert llm_client.remembered_availability(client._availability_key) is None

    with patch("dora_api.infrastructure.llm.anthropic_client.urlopen",
               side_effect=URLError("down")):
        with pytest.raises(LlmUnavailable):
            client.chat([{"role": "user", "content": "hi"}])
    assert llm_client.remembered_availability(client._availability_key) is False
    llm_client._availability.clear()


def test__availability_key__includes_the_model():
    a = AnthropicClient(api_key="k", model="claude-a")
    b = AnthropicClient(api_key="k", model="claude-b")
    assert a._availability_key != b._availability_key


def test__bounded_days__clamps_untrusted_day_counts():
    assert _bounded_days(10**12, 7) == 366
    assert _bounded_days(-5, 7) == 0
    assert _bounded_days("banana", 7) == 7
    assert _bounded_days(None, 7) == 7
    assert _bounded_days(float("inf"), 7) == 7
    assert _bounded_days(30, 7) == 30


def test__answer__a_tool_that_rejects_its_args_is_fed_back_not_raised():
    """A model arg of the wrong type used to raise straight out of `/ask` as
    a 500. Now the failure goes back to the model as `{"error": …}` with the
    call id, and the model gets to answer."""
    llm = MagicMock()
    llm.chat.side_effect = [
        {"role": "assistant", "content": "", "tool_calls": [_CALL]},
        {"role": "assistant", "content": "Sorry, I couldn't check that."},
    ]
    handler = ask_assistant.AskAssistantHandler.__new__(ask_assistant.AskAssistantHandler)
    handler._llm = llm
    with patch.object(ask_assistant.tools, "run_tool", side_effect=AttributeError("int has no strip")):
        reply = handler._answer(ask_assistant.AskAssistantRequest(message="what's expiring?"))

    assert reply.answer == "Sorry, I couldn't check that."
    round_two = llm.chat.call_args_list[1].args[0]
    tool_message = round_two[-1]
    assert tool_message["role"] == "tool"
    assert tool_message["tool_call_id"] == "call_abc"
    assert tool_message["name"] == "whats_expiring"
    assert "error" in tool_message["content"]


def test__completed_at_key__sorts_aware_naive_and_missing_together():
    # Postgres hands back aware `completed_at`, SQLite naive, unfinished None;
    # the old naive `datetime.min` floor raised TypeError against aware ones.
    from datetime import datetime, timezone
    from dora_api.features.assistant.tools import _completed_at_key

    samples = [
        (1.0, None, None, None, "x", 1),
        (2.0, None, None, datetime(2026, 5, 1, tzinfo=timezone.utc), "x", 1),
        (3.0, None, None, datetime(2026, 6, 1), "x", 1),
    ]
    newest_first = sorted(samples, key=_completed_at_key, reverse=True)
    assert [s[0] for s in newest_first] == [3.0, 2.0, 1.0]
