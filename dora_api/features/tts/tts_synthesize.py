"""Piper text-to-speech — `POST /api/tts` + `GET /api/tts/voices`.

Runs Piper as a subprocess and streams the resulting WAV back to the client.
Piper is a small, MIT-licensed neural TTS that runs offline on CPU; we ship a
couple of voice files so the desktop build can produce a natural-sounding
voice without any cloud calls, and the catalog (`voice_catalog.py`) lists more
that an operator can drop in.

Configuration:
  DORA_PIPER_BIN        — path to the piper executable (default: `piper`
                          on PATH, which works after `pip install piper-tts`)
  DORA_PIPER_VOICE_DIR  — directory holding the `.onnx` voice models (+ the
                          matching `.onnx.json`). Default: the `voices/`
                          directory next to this file (where the bundled
                          Amy/Ryan models live).

Request JSON (POST): { "text": str, "voice"?: str,
                       "length_scale"?: float, "noise_scale"?: float,
                       "noise_w"?: float, "sentence_silence"?: float,
                       "pitch_semitones"?: float }

`voice` selects a catalog entry by id (e.g. "amy"); the voice's default tuning
is applied, and any explicit knob in the request overrides it (so chat / cook
mode send only text + voice, while the settings Preview can audition custom
knobs). When Piper isn't installed or the requested voice's model file is
missing we return 503 with a hint — the SPA treats that as "fall back to the
browser's built-in voice" so Dora is never silent.

`length_scale` is Piper's speed knob: >1 slower, <1 faster. Piper has no native
pitch knob; `pitch_semitones` is applied as a post-process through ffmpeg
(asetrate + atempo) so pitch shifts without dragging the speed. Requires ffmpeg
on PATH — if it's missing and pitch is non-zero, we return the un-pitched WAV
unchanged. (The catalog defaults leave pitch at 0 so the bundled experience
never needs ffmpeg.)
"""
import logging
import os
import shutil
import struct
import subprocess
from pathlib import Path

from flask import Response, jsonify, request

from dora_api.features.routers import TTS_ROUTER
from dora_api.features.tts import voice_provision
from dora_api.features.tts.voice_catalog import (DEFAULT_VOICE_ID,
                                                 VOICE_CATALOG, VoiceDef,
                                                 get_voice)
_LOGGER = logging.getLogger(__name__)

# Piper's per-voice numeric knobs, in the order we forward them as CLI flags.
_PIPER_PARAM_KEYS = ("length_scale", "noise_scale", "noise_w", "sentence_silence")

# Silence put in front of every clip (FU-722). A phone's audio output, and a
# Bluetooth link above all, powers down when idle and swallows the start of
# the next stream while it wakes, by a varying amount. That is the reported
# "start of the sentence is cut off, random how much", after the three
# client-side causes were fixed. With a lead-in, what gets swallowed is
# silence.
_LEAD_IN_SECONDS = 0.35


def _piper_bin() -> str | None:
    # `AppSetting.piper_bin`. Desktop bundles seed the row at
    # boot via `desktop_app._seed_desktop_paths` (post-init); server operators
    # set it in Settings → Admin → System → Voice.
    try:
        from dora_api.features.app_settings.operational_config import \
            resolved_operational_config
        explicit = resolved_operational_config().piper_bin
    except Exception:
        explicit = ""
    if explicit:
        return explicit if Path(explicit).exists() else None
    return shutil.which("piper")


def _resolve_model(voice_id: str | None) -> tuple[Path | None, VoiceDef | None]:
    """Return (model_path, voice_def) for the requested voice, or (None, None)
    when nothing usable.

    Falls through `voice_provision.is_downloaded` which checks the writable
    data dir first and the build-time bundle dir as a fallback — so a shipped
    artifact (Docker / desktop) speaks the bundled default voice immediately,
    while user downloads of additional voices still land in the data dir."""
    voice = get_voice(voice_id or DEFAULT_VOICE_ID) or get_voice(DEFAULT_VOICE_ID)
    if voice is None:
        return None, None
    if not voice_provision.is_downloaded(voice):
        return None, voice
    return voice_provision.model_path(voice), voice


@TTS_ROUTER.route("/voices", methods=["GET"])
def list_voices():
    """The catalog + each voice's download/availability state. Drives the
    Settings → Voice picker (Download / Downloading… / Ready / Retry) and the
    engine gating; the SPA falls back to the browser voice when nothing's
    usable."""
    piper_ready = _piper_bin() is not None
    voices = []
    for v in VOICE_CATALOG:
        # Live bytes while a model is coming down, so the settings page can
        # draw a real bar over a 60–110MB fetch instead of an open-ended
        # spinner. `downloaded_bytes_total` is 0 when the origin declared no
        # Content-Length — the client must read that as unknown, not as a
        # denominator. Both are 0 for any voice not currently downloading.
        done, total = voice_provision.progress_for(v.id)
        voices.append({
            "id": v.id,
            "label": v.label,
            "description": v.description,
            "gender": v.gender,
            "size_bytes": v.size_bytes,
            # ready | downloading | error | downloadable
            "status": voice_provision.status_for(v),
            # usable for synthesis right now (downloaded AND piper present)
            "available": piper_ready and voice_provision.is_downloaded(v),
            "error": voice_provision.error_for(v.id),
            "downloaded_bytes": done,
            "downloaded_bytes_total": total,
        })
    # `configured` = Piper can actually speak right now (binary present AND at
    # least one model available).
    has_model = any(v["available"] for v in voices)
    return jsonify({
        "configured": piper_ready and has_model,
        # Lets the UI distinguish "no voice downloaded yet" from "Piper engine
        # not installed on this server".
        "piper_available": piper_ready,
        "default_voice_id": DEFAULT_VOICE_ID,
        "voices": voices,
    })


@TTS_ROUTER.route("/voices/<voice_id>/download", methods=["POST"])
def download_voice(voice_id: str):
    """Download a catalog voice's model into the voices dir (background) so the
    user can pick it. Idempotent: a no-op if already present / in flight.
    Shared install resource — the model lands on the server for everyone."""
    voice = get_voice(voice_id)
    if voice is None:
        return jsonify({"error": f"Unknown voice '{voice_id}'"}), 404
    status = voice_provision.start_download(voice)
    return jsonify({"id": voice.id, "status": status})


@TTS_ROUTER.route("", methods=["POST"])
def synthesize():
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    piper = _piper_bin()
    model, voice = _resolve_model(body.get("voice"))
    if not piper or model is None:
        return jsonify({
            "error": "Piper is not configured",
            "hint": "Install Piper (`pip install piper-tts`, or the binary from "
                    "github.com/rhasspy/piper/releases with DORA_PIPER_BIN set), "
                    "then download a voice from Settings → Voice.",
        }), 503

    # Start from the voice's curated defaults, then let explicit request knobs
    # override (settings Preview). Chat / cook mode pass none, so they get the
    # tuned voice as-is.
    params: dict[str, float] = dict(voice.params) if voice else {}
    for key in (*_PIPER_PARAM_KEYS, "pitch_semitones"):
        val = body.get(key)
        if val is None:
            continue
        try:
            params[key] = float(val)
        except (TypeError, ValueError):
            return jsonify({"error": f"{key} must be a number"}), 400

    args = [piper, "--model", str(model), "--output_file", "-"]
    for key in _PIPER_PARAM_KEYS:
        if key in params:
            args.extend([f"--{key}", str(params[key])])

    pitch_semitones = float(params.get("pitch_semitones", 0.0))

    try:
        result = subprocess.run(
            args,
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=30,
            check=True,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Piper timed out"}), 504
    except subprocess.CalledProcessError as exc:
        _LOGGER.error("Piper failed: %s", exc.stderr.decode("utf-8", "replace"))
        return jsonify({"error": "Piper synthesis failed"}), 500

    wav = result.stdout
    if abs(pitch_semitones) > 0.01:
        wav = _pitch_shift(wav, pitch_semitones) or wav

    return Response(with_lead_in(wav, _LEAD_IN_SECONDS), mimetype="audio/wav")


def with_lead_in(wav: bytes, seconds: float) -> bytes:
    """``wav`` with ``seconds`` of silence before the first sample.

    Rebuilt as a plain PCM WAV (RIFF, ``fmt``, ``data``) rather than patched in
    place, because a WAV written to a pipe can carry placeholder chunk sizes:
    the ``data`` length is taken as whatever follows its header when the
    declared one overruns. Anything that isn't uncompressed PCM, or doesn't
    parse, is returned unchanged so a malformed clip still plays.
    """
    if len(wav) < 12 or wav[:4] != b"RIFF" or wav[8:12] != b"WAVE":
        return wav
    fmt: bytes | None = None
    pos = 12
    while pos + 8 <= len(wav):
        chunk_id = wav[pos:pos + 4]
        size = struct.unpack("<I", wav[pos + 4:pos + 8])[0]
        body = pos + 8
        if chunk_id == b"fmt ":
            fmt = wav[body:body + size]
        elif chunk_id == b"data":
            if fmt is None or len(fmt) < 16:
                return wav
            audio_format, channels, rate, _, block_align, _ = struct.unpack("<HHIIHH", fmt[:16])
            if audio_format != 1 or block_align == 0:
                return wav
            pcm = wav[body:body + size] if body + size <= len(wav) else wav[body:]
            pcm = pcm[:len(pcm) - len(pcm) % block_align]
            silence = b"\x00" * (int(rate * seconds) * block_align)
            data = silence + pcm
            return (b"RIFF" + struct.pack("<I", 4 + 8 + len(fmt) + 8 + len(data)) + b"WAVE"
                    + b"fmt " + struct.pack("<I", len(fmt)) + fmt
                    + b"data" + struct.pack("<I", len(data)) + data)
        pos = body + size + (size & 1)
    return wav


def _pitch_shift(wav: bytes, semitones: float) -> bytes | None:
    """Shift pitch without changing duration. Uses ffmpeg: asetrate
    multiplies the sample-rate header (pitch + speed up together),
    aresample puts it back to the original rate, then atempo undoes
    the speed change. Returns None on failure so the caller can fall
    back to the un-shifted audio."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        _LOGGER.warning("ffmpeg not on PATH — pitch_semitones ignored")
        return None
    ratio = 2.0 ** (semitones / 12.0)
    # atempo only accepts 0.5–2.0 per filter; chain when out of range.
    tempo = 1.0 / ratio
    tempo_chain: list[str] = []
    remaining = tempo
    while remaining < 0.5:
        tempo_chain.append("atempo=0.5")
        remaining /= 0.5
    while remaining > 2.0:
        tempo_chain.append("atempo=2.0")
        remaining /= 2.0
    tempo_chain.append(f"atempo={remaining:.6f}")
    # Piper WAV is 22050 Hz mono; reading the header would be safer
    # but Piper voices all use 22050 in practice.
    sr = 22050
    filt = f"asetrate={int(sr * ratio)},aresample={sr}," + ",".join(tempo_chain)
    try:
        out = subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error",
             "-f", "wav", "-i", "pipe:0",
             "-filter:a", filt,
             "-f", "wav", "pipe:1"],
            input=wav, capture_output=True, timeout=15, check=True,
        )
        return out.stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        stderr = getattr(exc, "stderr", b"") or b""
        _LOGGER.error("ffmpeg pitch shift failed: %s", stderr.decode("utf-8", "replace"))
        return None
