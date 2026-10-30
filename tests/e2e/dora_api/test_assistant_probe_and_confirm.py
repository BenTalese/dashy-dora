"""Assistant settings probe + confirm endpoint hardening.

- A probe run with DRAFT values used to write `verified` onto the SAVED
  provider row: a passing draft vouched for different saved settings, and a
  failing draft un-verified a good saved config. `verified` now moves only
  when the probe exercised exactly the saved (base_url, model, api_key).
- Provider base URLs are http(s) only — `urlopen` honours `file://`, and a
  `#` fragment swallows the appended API path, so an unchecked base URL made
  the probe a server-side file-existence oracle.
- A malformed / stale `/assistant/confirm` payload raised KeyError/ValueError
  → 500; it now answers `{"ok": false, …}` in the usual shape.
"""
from unittest.mock import patch

import requests

from tests.support import assert_problem
from dora_api.features.assistant.probe_assistant import (
    ProbeAssistantHandler, ProbeAssistantResponse)

BASE = "http://localhost:5170/api/assistant"
SAVED_URL = "http://saved-ollama.test:11434"
SAVED_MODEL = "saved-model"


def _ollama_row() -> dict:
    providers = requests.get(f"{BASE}/providers").json()["providers"]
    return next(p for p in providers if p["provider"] == "ollama")


def _save_ollama() -> None:
    resp = requests.patch(f"{BASE}/providers/ollama",
                          json={"base_url": SAVED_URL, "model": SAVED_MODEL})
    assert resp.status_code == 200, resp.text
    assert _ollama_row()["verified"] is False


def _probe(available: bool, **body) -> dict:
    result = ProbeAssistantResponse(available=available,
                                    reason=None if available else "nope")
    with patch.object(ProbeAssistantHandler, "_probe", return_value=result):
        resp = requests.post(f"{BASE}/probe", json={"provider": "ollama", **body})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test__probe__only_the_saved_config_moves_the_verified_flag(api):
    _save_ollama()

    # A draft that passes must not vouch for the (different) saved settings.
    assert _probe(True, model="draft-model")["available"] is True
    assert _ollama_row()["verified"] is False

    # Probing the saved values verifies the row…
    assert _probe(True)["available"] is True
    assert _ollama_row()["verified"] is True

    # …and a failing draft doesn't un-verify it.
    assert _probe(False, base_url="http://draft.test:11434")["available"] is False
    assert _ollama_row()["verified"] is True

    # The saved values failing does clear it.
    _probe(False, base_url=SAVED_URL, model=SAVED_MODEL)
    assert _ollama_row()["verified"] is False


def test__provider_base_url__must_be_http_or_https(api):
    for bad in ("file:///etc/passwd#", "ftp://example.test", "javascript:alert(1)"):
        patched = requests.patch(f"{BASE}/providers/ollama", json={"base_url": bad})
        assert_problem(patched, 400, field="base_url")

        probed = requests.post(f"{BASE}/probe", json={
            "provider": "ollama", "base_url": bad, "model": "m",
        })
        assert_problem(probed, 400, field="base_url")

    ok = requests.patch(f"{BASE}/providers/ollama", json={"base_url": "http://localhost:11434"})
    assert ok.status_code == 200, ok.text


def test__confirm__a_malformed_payload_answers_not_ok_instead_of_500(api):
    for payload in ({}, {"stock_item_id": "not-a-uuid", "new_level_id": "nope"}):
        resp = requests.post(f"{BASE}/confirm",
                             json={"type": "update_stock_level", "payload": payload})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["ok"] is False
        assert body["answer"]
