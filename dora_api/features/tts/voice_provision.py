"""Download Piper voice models on demand into the runtime voices dir.

Voice models aren't shipped in the repo (~60 MB each). When a user picks a
voice in onboarding / Settings → Voice, the SPA calls
`POST /api/tts/voices/<id>/download`, which kicks off a background download
here: fetch the `.onnx` + `.onnx.json` from the catalog's pinned HuggingFace
URLs into `<voices dir>`, verify the `.onnx` against the catalog SHA-256, and
atomically move it into place. `GET /api/tts/voices` reports each voice's
state so the UI can show Download / Downloading… / Ready / Retry.

State is process-local (an in-memory set + last-error map). That's fine: the
*file on disk* is the source of truth for "ready" (any worker sees it), and the
download status is only a transient UI hint while a fetch is in flight. A
second download request for an already-in-flight voice is a no-op. A worker
reload mid-download loses the in-flight bit but leaves the `.part` file behind;
the atomic rename means a partial file never reads as "ready", so the next
request just kicks off a fresh download (the `.part` is overwritten in place).

Two resolution paths:
- `<data dir>/voices/<filename>` — where downloads land (read-write). The
  user's choice, survives across upgrades.
- `<bundle dir>/voices/<filename>` — the build-time-bundled default voice in
  shipped artifacts (Docker image + desktop installer). Read-only. Populated
  by `packaging/fetch_default_voice.py`, never present in git. Checked as a
  fallback so a fresh install can speak Dora's neural voice immediately
  without the user clicking Download first.
"""
import hashlib
import logging
import os
import sys
import threading
from pathlib import Path

import requests

from dora_api.features.tts.voice_catalog import VoiceDef, get_voice
from dora_api.infrastructure.configuration_manager import DORA_CONFIG

_LOGGER = logging.getLogger(__name__)

# Per-voice download state, guarded by _LOCK. `_IN_FLIGHT` holds ids currently
# downloading; `_ERRORS` holds the last error message per id (cleared on a
# fresh attempt / success / when the file appears manually).
_LOCK = threading.Lock()
_IN_FLIGHT: set[str] = set()
_ERRORS: dict[str, str] = {}
# `_PROGRESS` holds (bytes_done, bytes_total) for the voice model currently
# downloading. A Piper voice is 60–110MB, which on a slow line is long enough
# that a bare "downloading" spinner is indistinguishable from a stall — the
# same complaint the nutrition dataset import answered. `bytes_total` is 0
# when the origin sent no Content-Length; callers must treat that as unknown
# rather than as a denominator. Cleared when the download settles, because
# this is a live-progress hint and not a record of what happened.
_PROGRESS: dict[str, tuple[int, int]] = {}

# Hard ceiling so a bad URL / redirect to something huge can't fill the disk.
# Larger than any current catalog voice with headroom for future "high" tier
# (~120 MB) models without bumping the ceiling.
_MAX_BYTES = 200 * 1024 * 1024
_CHUNK = 1024 * 256
# Bytes between progress updates. The settings page polls on a timer, so
# publishing more often than it reads is just lock traffic; 1MB is a visible
# step on a 60–110MB voice.
_PROGRESS_TICK = 1024 * 1024
# (connect, read) — separate so a stuck stream times out instead of hanging
# the worker thread forever. Connect stays generous for slow networks.
_TIMEOUT = (60, 30)


def voices_dir() -> Path:
    """The writable per-install voices dir. Downloads land here."""
    return DORA_CONFIG.get_voices_dir()


def bundled_voices_dir() -> Path | None:
    """The read-only build-time bundle dir, when present.

    Populated by `packaging/fetch_default_voice.py` and copied into shipped
    artifacts by `dora.spec` (desktop) / Dockerfile (Docker). Lets a fresh
    install speak Dora's neural voice immediately without the user having to
    click Download — the voice is already there.

    Resolution order (highest priority first):
      1. `AppSetting.piper_bundled_voice_dir` (FU-333 Bucket B) — admin-editable
         operator override; desktop bundles seed this at boot from the
         detected `<_MEIPASS>/voices/` location.
      2. `<_MEIPASS>/voices/` — PyInstaller one-folder / one-file desktop build.
      3. `<repo_root>/packaging/voices/` — dev checkout + the Docker image's
         working copy (the image runs the prefetch into `packaging/voices/`
         during build).

    Returns None when no bundle is present (source install with no prefetch).
    """
    try:
        from dora_api.features.app_settings.operational_config import \
            resolved_operational_config
        explicit = resolved_operational_config().piper_bundled_voice_dir
    except Exception:
        explicit = ""
    if explicit:
        path = Path(explicit)
        return path if path.is_dir() else None
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        path = Path(meipass) / "voices"
        if path.is_dir():
            return path
    # `<repo_root>/packaging/voices/` — this file is at
    # dora_api/features/tts/voice_provision.py, three parents up is the repo
    # root.
    repo_root = Path(__file__).resolve().parents[3]
    path = repo_root / "packaging" / "voices"
    return path if path.is_dir() else None


def model_path(voice: VoiceDef) -> Path:
    """Resolve a voice's `.onnx` to its on-disk location, preferring the
    writable data dir over the read-only bundle. Used by `tts_synthesize` to
    point Piper at the right file; callers should pair this with
    `is_downloaded` since it returns the data-dir path even when nothing's
    there yet (so a fresh download lands in the right place)."""
    data = voices_dir() / voice.filename
    if data.exists():
        return data
    bundle = bundled_voices_dir()
    if bundle is not None:
        bundled = bundle / voice.filename
        if bundled.exists():
            return bundled
    return data  # not present anywhere — callers check is_downloaded first


def is_downloaded(voice: VoiceDef) -> bool:
    if (voices_dir() / voice.filename).exists():
        return True
    bundle = bundled_voices_dir()
    return bundle is not None and (bundle / voice.filename).exists()


def status_for(voice: VoiceDef) -> str:
    """One of: ready | downloading | error | downloadable."""
    if is_downloaded(voice):
        # Manual drop (operator copied the file in, or the bundle is now
        # visible) clears a stale error so the picker shows Ready.
        with _LOCK:
            _ERRORS.pop(voice.id, None)
        return "ready"
    with _LOCK:
        if voice.id in _IN_FLIGHT:
            return "downloading"
        if voice.id in _ERRORS:
            return "error"
    return "downloadable"


def error_for(voice_id: str) -> str | None:
    with _LOCK:
        return _ERRORS.get(voice_id)


def progress_for(voice_id: str) -> tuple[int, int]:
    """(bytes_done, bytes_total) for an in-flight download; (0, 0) otherwise.
    A `bytes_total` of 0 means the origin didn't declare a size."""
    with _LOCK:
        return _PROGRESS.get(voice_id, (0, 0))


def start_download(voice: VoiceDef) -> str:
    """Begin (or no-op) a background download. Returns the resulting status:
    `ready` (already present), `downloading` (started or already running)."""
    if is_downloaded(voice):
        return "ready"
    with _LOCK:
        if voice.id in _IN_FLIGHT:
            return "downloading"
        _IN_FLIGHT.add(voice.id)
        _ERRORS.pop(voice.id, None)
    thread = threading.Thread(
        target=_run_download, args=(voice,), name=f"tts-download-{voice.id}", daemon=True,
    )
    thread.start()
    return "downloading"


def _run_download(voice: VoiceDef) -> None:
    try:
        _download_voice(voice)
        _LOGGER.info("Downloaded Piper voice '%s' (%s)", voice.id, voice.filename)
        with _LOCK:
            _ERRORS.pop(voice.id, None)
    except Exception as exc:  # noqa: BLE001 — surface any failure as UI state
        _LOGGER.exception("Failed to download Piper voice '%s'", voice.id)
        with _LOCK:
            _ERRORS[voice.id] = str(exc) or exc.__class__.__name__
    finally:
        with _LOCK:
            _IN_FLIGHT.discard(voice.id)
            _PROGRESS.pop(voice.id, None)


def _download_voice(voice: VoiceDef) -> None:
    dest_dir = voices_dir()
    onnx = dest_dir / voice.filename
    onnx_tmp = dest_dir / f"{voice.filename}.part"
    json_final = dest_dir / f"{voice.filename}.json"
    json_tmp = dest_dir / f"{voice.filename}.json.part"

    # The model first (big, integrity-checked), then the small config sidecar.
    # Only the model reports progress — the sidecar is a few KB, and letting it
    # write to `_PROGRESS` would snap a nearly-full bar back to ~0% at the very
    # end of the download.
    _fetch(
        voice.onnx_url, onnx_tmp, expected_sha256=voice.sha256,
        on_progress = lambda done, total: _record_progress(voice.id, done, total),
    )
    _fetch(voice.json_url, json_tmp, expected_sha256=None)

    # Atomic-ish swap: rename both only once both fetched + verified, so a
    # partial download never looks "ready". A worker reload between the
    # fetches leaves the .part files; the next download attempt overwrites
    # them in place (no orphan accumulation).
    onnx_tmp.replace(onnx)
    json_tmp.replace(json_final)


def _record_progress(voice_id: str, done: int, total: int) -> None:
    with _LOCK:
        _PROGRESS[voice_id] = (done, total)


def _fetch(url: str, tmp_path: Path, expected_sha256: str | None, on_progress=None) -> None:  # noqa: ANN001
    hasher = hashlib.sha256()
    total = 0
    try:
        with requests.get(url, stream=True, timeout=_TIMEOUT) as resp:
            resp.raise_for_status()
            # Cheap pre-flight: a redirect-to-something-huge fails fast
            # without opening the file at all.
            declared = resp.headers.get("Content-Length")
            declared_bytes = 0
            if declared is not None:
                try:
                    declared_bytes = int(declared)
                except ValueError:
                    declared_bytes = -1
                if declared_bytes > _MAX_BYTES:
                    raise ValueError(
                        f"server declared {declared_bytes} bytes, ceiling is {_MAX_BYTES}"
                    )
            # A malformed header parsed to -1 above; that sentinel drives the
            # ceiling check only and must not reach the UI as a denominator.
            size_hint = declared_bytes if declared_bytes > 0 else 0
            if on_progress is not None:
                on_progress(0, size_hint)
            last_reported = 0
            with open(tmp_path, "wb") as handle:
                for chunk in resp.iter_content(chunk_size=_CHUNK):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > _MAX_BYTES:
                        raise ValueError(f"download exceeded {_MAX_BYTES} bytes")
                    hasher.update(chunk)
                    handle.write(chunk)
                    if on_progress is not None and total - last_reported >= _PROGRESS_TICK:
                        on_progress(total, size_hint)
                        last_reported = total
            if on_progress is not None:
                # Exact final figure, so a finished fetch never rests short of
                # 100% because the last chunk didn't reach the tick.
                on_progress(total, size_hint or total)
        if total == 0:
            raise ValueError("empty download")
        if expected_sha256 and hasher.hexdigest() != expected_sha256:
            raise ValueError("Checksum mismatch, download discarded")
    except BaseException:
        # Any failure — network blip, ceiling exceeded, checksum mismatch,
        # caller cancellation — drops the orphan so the next attempt isn't
        # confused by a stale `.part` of the wrong length. The atomic rename
        # later won't have happened yet, so the final filename is untouched.
        tmp_path.unlink(missing_ok=True)
        raise


def ensure_voice(voice_id: str) -> bool:
    """Synchronous download for build/CLI use (e.g. packaging prefetch).
    Returns True if the voice is present afterwards. Used by
    `python -m dora_api.features.tts.voice_provision <id...>`."""
    voice = get_voice(voice_id)
    if voice is None:
        raise ValueError(f"unknown voice '{voice_id}'")
    if is_downloaded(voice):
        return True
    _download_voice(voice)
    return is_downloaded(voice)


if __name__ == "__main__":
    from dora_api.features.tts.voice_catalog import DEFAULT_VOICE_ID

    logging.basicConfig(level=logging.INFO)
    ids = sys.argv[1:] or [DEFAULT_VOICE_ID]
    for vid in ids:
        ok = ensure_voice(vid)
        print(f"{vid}: {'ready' if ok else 'FAILED'}")
