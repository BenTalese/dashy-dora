"""End-to-end coverage for the Piper TTS surface.

Covers the voice catalog endpoint, the per-user voice preference round-trip +
its closed-set validation, and the graceful-degradation contract of the
synthesis endpoint (503 when Piper isn't configured so the SPA can fall back
to the browser voice).

These use the authenticated `dora` client the `api` fixture rebinds onto the
module-level `requests.*` helpers (no fresh registrations — that endpoint is
rate-limited and would flake when the whole suite runs).
"""
import requests


API = "http://localhost:5170/api"
AUTH = f"{API}/auth"


def test__tts_voices__lists_catalog_with_download_state(api):
    resp = requests.get(f"{API}/tts/voices")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert isinstance(body["configured"], bool)
    assert isinstance(body["piper_available"], bool)
    assert body["default_voice_id"] == "amy"

    by_id = {v["id"]: v for v in body["voices"]}
    # The curated catalog is fixed; the default female + male are always listed.
    assert "amy" in by_id and "ryan" in by_id

    for voice in body["voices"]:
        assert set(voice) >= {
            "id", "label", "description", "gender", "size_bytes", "status",
            "available", "error",
        }
        assert voice["gender"] in ("female", "male", "neutral")
        assert voice["status"] in ("ready", "downloading", "error", "downloadable")
        assert isinstance(voice["size_bytes"], int) and voice["size_bytes"] > 0


def test__tts_download__unknown_voice_is_404(api):
    resp = requests.post(f"{API}/tts/voices/not-a-voice/download")
    assert resp.status_code == 404, resp.text


def test__tts_download__known_voice_reports_status(api):
    # Idempotent: returns 'ready' if the model is already present on this box,
    # else kicks off a background download ('downloading'). Either is valid;
    # we don't block the test on a 60 MB fetch.
    resp = requests.post(f"{API}/tts/voices/amy/download")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == "amy"
    assert body["status"] in ("ready", "downloading")


def test__tts_synthesize__matches_configured_state(api):
    """When Piper is configured the endpoint returns WAV; when it isn't it
    returns 503 with a setup hint (the SPA's cue to use the browser voice)."""
    configured = requests.get(f"{API}/tts/voices").json()["configured"]
    resp = requests.post(f"{API}/tts", json={"text": "Hello from Dora.", "voice": "amy"})

    if configured:
        assert resp.status_code == 200, resp.text
        assert resp.headers["Content-Type"].startswith("audio/")
        assert len(resp.content) > 0
    else:
        assert resp.status_code == 503, resp.text
        body = resp.json()
        assert "error" in body and "hint" in body


def test__tts_synthesize__empty_text_is_400(api):
    resp = requests.post(f"{API}/tts", json={"text": "   "})
    assert resp.status_code == 400, resp.text


def test__tts_synthesize__JsonArrayBody__IsProblemDetails400(api):
    """A non-object body used to reach `.get` on a list and 500. Errors are the
    ProblemDetails envelope, still carrying the `error` key the SPA's raw
    fetch reads."""
    from tests.support import assert_problem

    resp = requests.post(f"{API}/tts", json=["Hello"])

    body = assert_problem(resp, 400)
    assert body["error"]


def test__update_me__voice_prefs_round_trip(api):
    # Snapshot dora's current prefs so the test leaves no residue.
    before = requests.get(f"{AUTH}/me").json()
    try:
        patched = requests.patch(f"{AUTH}/me", json={"voice_engine": "browser", "voice_id": "ryan"})
        assert patched.status_code == 200, patched.text
        body = patched.json()
        assert body["voice_engine"] == "browser"
        assert body["voice_id"] == "ryan"

        again = requests.patch(f"{AUTH}/me", json={"voice_engine": "piper", "voice_id": "amy"})
        assert again.status_code == 200, again.text
        assert again.json()["voice_engine"] == "piper"
        assert again.json()["voice_id"] == "amy"
    finally:
        requests.patch(f"{AUTH}/me", json={
            "voice_engine": before["voice_engine"],
            "voice_id": before["voice_id"],
        })


def test__update_me__rejects_invalid_voice_engine(api):
    resp = requests.patch(f"{AUTH}/me", json={"voice_engine": "robot"})
    assert resp.status_code == 422, resp.text


def test__update_me__rejects_unknown_voice_id(api):
    resp = requests.patch(f"{AUTH}/me", json={"voice_id": "definitely-not-a-voice"})
    assert resp.status_code == 422, resp.text


def test__tts_synthesize__TextOverLimit__Is400WithErrorKey(api):
    from tests.support import assert_problem

    resp = requests.post(f"{API}/tts", json={"text": "a" * 2001})

    body = assert_problem(resp, 400, field="text")
    assert body["error"]


def test__tts_synthesize__NonFiniteOrHugeKnobs__Are400NotA500(api):
    """NaN / inf / huge knobs used to reach `2.0 ** (x / 12)` (OverflowError →
    500) or Piper's CLI. Each is refused up front, before Piper is consulted."""
    from tests.support import assert_problem

    for knob, value in (
        ("pitch_semitones", float("nan")),
        ("pitch_semitones", 1e308),
        ("length_scale", float("inf")),
        ("length_scale", 0),
        ("noise_scale", -1),
        ("noise_w", 99),
        ("sentence_silence", 1e9),
    ):
        resp = requests.post(f"{API}/tts", json={"text": "Hello.", knob: value})
        body = assert_problem(resp, 400, field=knob)
        assert body["error"], (knob, value)


def test__tts_synthesize__UnknownField__Is400(api):
    from tests.support import assert_problem

    resp = requests.post(f"{API}/tts", json={"text": "Hello.", "speed": 2})

    assert_problem(resp, 400, field="speed")
