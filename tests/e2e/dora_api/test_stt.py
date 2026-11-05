"""FU-788: server-side speech-to-text for browsers without the Web Speech API.

The engine (faster-whisper) and its model are optional, so these pin the
contract around them with the engine stubbed: the status endpoint says why
voice input isn't available, transcribe refuses until it is, and a ready
engine turns an uploaded clip into text in the household's language.
"""
import io

import requests

from dora_api.features.stt import stt_engine

STT = "http://localhost:5170/api/stt"


def test__stt_status__NoEngine__SaysUnavailable(api, monkeypatch):
    monkeypatch.setattr(stt_engine, "engine_installed", lambda: False)
    body = requests.get(STT).json()
    assert body["status"] == "unavailable"
    assert body["model_size_bytes"] > 0


def test__stt_transcribe__NotReady__Refuses(api, monkeypatch):
    monkeypatch.setattr(stt_engine, "status", lambda: "downloadable")
    resp = requests.post(f"{STT}/transcribe", files={"audio": ("clip.webm", io.BytesIO(b"x"))})
    assert resp.status_code == 503


def test__stt_transcribe__Ready__ReturnsTheTextInTheHouseholdLanguage(api, monkeypatch):
    seen: dict = {}

    def _fake(audio: bytes, *, language):
        seen["audio"], seen["language"] = audio, language
        return "add milk to the list"

    monkeypatch.setattr(stt_engine, "status", lambda: "ready")
    monkeypatch.setattr(stt_engine, "transcribe", _fake)
    resp = requests.post(
        f"{STT}/transcribe", files={"audio": ("clip.webm", io.BytesIO(b"opus-bytes"))},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"text": "add milk to the list"}
    assert seen["audio"] == b"opus-bytes"
    assert seen["language"] == "en"


def test__stt_transcribe__NoAudio__IsABadRequest(api, monkeypatch):
    monkeypatch.setattr(stt_engine, "status", lambda: "ready")
    resp = requests.post(f"{STT}/transcribe", files={})
    assert resp.status_code == 400
