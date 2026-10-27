"""11-R43 — the factory builds a client per request, so availability is
remembered per endpoint rather than on the instance: two clients for the same
server probe it once."""
from unittest.mock import MagicMock, patch

from dora_api.infrastructure.llm import llm_client
from dora_api.infrastructure.llm.ollama_client import OllamaClient


def test__availability__second_client_for_the_same_endpoint_reuses_the_probe():
    llm_client._availability.clear()
    response = MagicMock(status=200)
    response.__enter__.return_value = response
    with patch("dora_api.infrastructure.llm.ollama_client.urlopen", return_value=response) as probe:
        assert OllamaClient("http://ollama.test", "m", 5, True).is_available()
        assert OllamaClient("http://ollama.test", "m", 5, True).is_available()
        assert probe.call_count == 1
        OllamaClient("http://other.test", "m", 5, True).is_available()
        assert probe.call_count == 2
    llm_client._availability.clear()
