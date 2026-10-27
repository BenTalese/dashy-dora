"""POST /api/app-settings/probe — test an LLM endpoint and list its models.

Admin-only. Runs server-side because the base URL (e.g. localhost:11434) is
relative to the Dora host, not the admin's browser — and Ollama sends no CORS
headers. Lets the Settings page confirm a connection and populate a model
picker before saving. Does not change any settings.
"""
import logging
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from dora_api.features.routers import APP_SETTINGS_ROUTER
from dora_api.features.auth.admin_gate import require_admin
from dora_api.infrastructure.api_response import ok
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.llm import LlmUnavailable, OllamaClient
from dora_api.infrastructure.utils import get_request_body

_LOGGER = logging.getLogger(__name__)

# Short timeout — the admin is often typing a URL before the server is up, and
# a snappy "couldn't reach it" beats a long hang.
_PROBE_TIMEOUT_SECONDS = 5


class ProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_url: str = Field(min_length=1, max_length=500)


@dataclass(frozen=True, slots=True)
class ProbeResultDto:
    reachable: bool
    models: list[str]
    error: str | None = None


@APP_SETTINGS_ROUTER.route("/probe", methods=["POST"])
@has_request_body(ProbeRequest)
def probe_llm():
    _, err = require_admin()
    if err is not None:
        return err

    _Request: ProbeRequest = get_request_body()
    client = OllamaClient(
        base_url=_Request.base_url.strip(),
        model="",
        timeout_seconds=_PROBE_TIMEOUT_SECONDS,
        enabled=True,
    )
    try:
        models = client.list_models()
        _LOGGER.info("LLM probe of %s ok (%d models)", _Request.base_url, len(models))
        return ok(ProbeResultDto(reachable=True, models=models))
    except LlmUnavailable as exc:
        _LOGGER.info("LLM probe of %s failed: %s", _Request.base_url, exc)
        return ok(ProbeResultDto(reachable=False, models=[], error=str(exc)))
