"""Speech-to-text on the server, for browsers with no Web Speech API (FU-788).

Firefox has never shipped `SpeechRecognition`, so a Firefox user couldn't talk
to Dora. The browser records a clip instead and posts it here; Whisper
(`faster-whisper`, CPU, int8) turns it into text. The input-side mirror of
Piper, with the same shape (R-018 / ADR-013): the engine is optional and is
installed by the Docker image, not `requirements.txt`, and the model is
downloaded on demand into the data dir from Settings → Voice. When either is
missing the SPA keeps its "this browser can't listen" note.

Model download state is process-local, like `tts/voice_provision`: the files
on disk are the truth for "ready"; the in-flight flag and last error are only a
UI hint while a download runs.
"""
import importlib.util
import logging
import tempfile
import threading
from pathlib import Path

from dora_api.infrastructure.configuration_manager import DORA_CONFIG

_LOGGER = logging.getLogger(__name__)

# Multilingual so a non-English household is heard in its own language; `base`
# is the smallest that copes with kitchen words (~145 MB, about a second per
# short clip on a modest CPU).
MODEL_NAME = "base"
MODEL_SIZE_BYTES = 148_000_000

_LOCK = threading.Lock()
_DOWNLOADING = False
_ERROR: str | None = None
_MODEL = None  # the loaded WhisperModel, kept for the life of the worker


def engine_installed() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


def model_dir() -> Path:
    return DORA_CONFIG.get_stt_models_dir() / MODEL_NAME


def is_downloaded() -> bool:
    # `model.bin` is written last by the download, so its presence means the
    # whole model is there.
    return (model_dir() / "model.bin").exists()


def status() -> str:
    """One of: unavailable | ready | downloading | error | downloadable."""
    global _ERROR
    if not engine_installed():
        return "unavailable"
    if is_downloaded():
        with _LOCK:
            _ERROR = None
        return "ready"
    with _LOCK:
        if _DOWNLOADING:
            return "downloading"
        if _ERROR:
            return "error"
    return "downloadable"


def last_error() -> str | None:
    with _LOCK:
        return _ERROR


def start_download() -> str:
    """Begin (or no-op) the background model download; returns the status."""
    global _DOWNLOADING, _ERROR
    current = status()
    if current in ("unavailable", "ready", "downloading"):
        return current
    with _LOCK:
        _DOWNLOADING = True
        _ERROR = None
    threading.Thread(target=_run_download, name="stt-download", daemon=True).start()
    return "downloading"


def _run_download() -> None:
    global _DOWNLOADING, _ERROR
    try:
        from faster_whisper import download_model
        download_model(MODEL_NAME, output_dir=str(model_dir()))
        _LOGGER.info("Downloaded the Whisper '%s' model", MODEL_NAME)
    except Exception as exc:  # noqa: BLE001 — surface any failure as UI state
        _LOGGER.exception("Failed to download the Whisper model")
        with _LOCK:
            _ERROR = str(exc) or exc.__class__.__name__
    finally:
        with _LOCK:
            _DOWNLOADING = False


def _model():
    global _MODEL
    with _LOCK:
        if _MODEL is None:
            from faster_whisper import WhisperModel
            _MODEL = WhisperModel(str(model_dir()), device="cpu", compute_type="int8")
        return _MODEL


def transcribe(audio: bytes, *, language: str | None) -> str:
    """The text of one recorded clip. ``language`` is a two-letter code (the
    household locale's language) or None to let Whisper detect it. Whisper
    reads the container itself (webm/ogg/mp4 via PyAV), so the browser's
    MediaRecorder output goes straight in."""
    with tempfile.NamedTemporaryFile(suffix=".audio", delete=True) as handle:
        handle.write(audio)
        handle.flush()
        segments, _info = _model().transcribe(
            handle.name, language=language, beam_size=1, vad_filter=True,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
