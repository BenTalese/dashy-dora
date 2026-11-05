"""`/api/stt` — server-side speech-to-text (FU-788).

  GET  /api/stt              — {status, model_size_bytes, error}: whether a
                               browser with no Web Speech API can use voice
                               input here, and if not, why.
  POST /api/stt/download     — fetch the Whisper model (background, idempotent).
                               A shared install resource, like a Piper voice.
  POST /api/stt/transcribe   — multipart `audio` (one recorded clip) → {text}.
"""
import logging

from flask import jsonify, request

from dora_api.features.routers import STT_ROUTER
from dora_api.features.stt import stt_engine
from dora_api.features.app_settings.access import get_or_create_app_setting
from dora_api.infrastructure.api_response import (ProblemDetails, bad_request,
                                                  internal_server_error)
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

_LOGGER = logging.getLogger(__name__)

# A push-to-talk clip is seconds long; 60 s of Opus is well under this.
_MAX_AUDIO_BYTES = 5 * 1024 * 1024


@STT_ROUTER.route("", methods=["GET"])
def stt_status():
    return jsonify({
        "status": stt_engine.status(),
        "model_size_bytes": stt_engine.MODEL_SIZE_BYTES,
        "error": stt_engine.last_error(),
    })


@STT_ROUTER.route("/download", methods=["POST"])
def stt_download():
    return jsonify({"status": stt_engine.start_download()})


def _household_language() -> str | None:
    """The household locale's language ("en-AU" → "en"), so Whisper isn't
    left guessing on a three-word clip."""
    try:
        locale = get_or_create_app_setting(SqlAlchemyRepository()).locale or ""
    except Exception:  # noqa: BLE001 — detection is the fallback, not an error
        return None
    return locale.split("-")[0].lower() or None


def _not_set_up():
    response = jsonify(ProblemDetails(
        detail="Speech recognition isn't set up on this server.", errors={}, status=503,
        title="Speech recognition isn't set up on this server.",
        type="https://datatracker.ietf.org/doc/html/rfc7231#section-6.6.4"))
    response.content_type = "application/problem+json"
    response.status_code = 503
    return response


@STT_ROUTER.route("/transcribe", methods=["POST"])
def stt_transcribe():
    # The request first: a malformed one is the caller's 400 whatever the
    # server's state.
    upload = request.files.get("audio")
    if upload is None:
        return bad_request("audio is required")
    audio = upload.read(_MAX_AUDIO_BYTES + 1)
    if not audio:
        return bad_request("audio is empty")
    if len(audio) > _MAX_AUDIO_BYTES:
        return bad_request("That recording is too long.")
    if stt_engine.status() != "ready":
        return _not_set_up()
    try:
        text = stt_engine.transcribe(audio, language=_household_language())
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Whisper transcription failed")
        return internal_server_error("Couldn't make out that recording")
    return jsonify({"text": text})
