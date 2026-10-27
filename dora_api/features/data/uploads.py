"""Chunked-resumable upload endpoints used by Data Management.

Workflow:
    POST /api/data/uploads/start
        Body: optional {"expected_size": <bytes>}
        Returns: {"upload_id", "chunk_size", "max_size"}
    POST /api/data/uploads/chunk    (multipart)
        Form fields:
            upload_id : the id returned by /start
            offset    : the byte offset this chunk starts at (sanity check)
        File field:
            chunk     : the raw bytes
        Returns: {"received": <total_bytes_so_far>}
    POST /api/data/uploads/finish
        Body: {"upload_id": ...}
        Returns: {"upload_id", "size"}
    DELETE /api/data/uploads/<upload_id>
        Returns: 204

The staged file lives at `data/uploads/<upload_id>.bin`. Inspect and
restore reference it via `upload_id` so the SPA never has to parse the
backup client-side.

TTL: every /start call sweeps any staged file last-modified > 1 hour ago.
A more rigorous background sweeper is future work; the lazy sweep is
fine for hobby-scale usage and avoids needing a job runner.
"""
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from flask import request
from pydantic import BaseModel, ConfigDict, Field

from dora_api.features.auth.admin_gate import require_admin
from dora_api.infrastructure.configuration_manager import DORA_CONFIG
from dora_api.features.routers import DATA_ROUTER
from dora_api.infrastructure.api_response import bad_request, no_content, not_found, ok
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body

_LOGGER = logging.getLogger(__name__)


# 2 GB total cap per upload session. 8 MB default chunk size.
MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024
DEFAULT_CHUNK_BYTES = 8 * 1024 * 1024
# Stale-upload TTL — files older than this on the next /start call get
# swept. 1 hour is generous for chunked uploads on slow connections.
STAGE_TTL_SECONDS = 60 * 60


def upload_dir() -> Path:
    """Where staged uploads live. Routes through DORA_CONFIG so the
    data dir honours DORA_DATA_DIR / container volume mounts; the
    config helper creates the dir lazily so first-upload-on-fresh-
    install still works."""
    return DORA_CONFIG.get_uploads_dir()


def staged_path(upload_id: str) -> Path:
    return upload_dir() / f"{upload_id}.bin"


def _sweep_stale_uploads() -> None:
    """Best-effort cleanup of staged files older than STAGE_TTL_SECONDS.
    Runs on every /start; cheap because the dir is normally small.
    """
    now = time.time()
    for entry in upload_dir().iterdir():
        if not entry.is_file():
            continue
        try:
            if now - entry.stat().st_mtime > STAGE_TTL_SECONDS:
                entry.unlink(missing_ok=True)
        except OSError:
            # Best-effort — one stale file we can't unlink isn't worth aborting.
            continue


def _is_valid_upload_id(upload_id: str) -> bool:
    try:
        UUID(upload_id)
        return True
    except (ValueError, TypeError):
        return False


# ── /start ─────────────────────────────────────────────────────────────

class StartUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_size: int | None = Field(default=None, ge=0, le=MAX_UPLOAD_BYTES)


@DATA_ROUTER.route("/uploads/start", methods=["POST"])
@has_request_body(StartUploadRequest)
def start_upload():
    # the entire /uploads/* chain feeds admin-only
    # workflows (backup inspect + restore, admin import). Gate on
    # /start so a non-admin can't even open a staging slot; the
    # subsequent /chunk /finish /abort endpoints repeat the gate as
    # defence-in-depth (a leaked upload_id shouldn't grant writes).
    _, err = require_admin()
    if err is not None:
        return err
    _Request: StartUploadRequest = get_request_body()
    if _Request.expected_size is not None and _Request.expected_size > MAX_UPLOAD_BYTES:
        return bad_request(
            f"Expected size exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB cap."
        )
    _sweep_stale_uploads()
    upload_id = str(uuid4())
    # Touch the empty file so subsequent /chunk calls have something to
    # append to. O_CREAT|O_EXCL stops the (vanishingly unlikely) UUID
    # collision from clobbering an in-flight upload.
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    fd = os.open(staged_path(upload_id), flags, 0o600)
    os.close(fd)
    _LOGGER.info("Started upload session %s", upload_id)
    return ok({
        "upload_id": upload_id,
        "chunk_size": DEFAULT_CHUNK_BYTES,
        "max_size": MAX_UPLOAD_BYTES,
    })


# ── /chunk ─────────────────────────────────────────────────────────────

@DATA_ROUTER.route("/uploads/chunk", methods=["POST"])
def append_chunk():
    _, err = require_admin()
    if err is not None:
        return err
    upload_id = request.form.get("upload_id", "")
    offset_raw = request.form.get("offset", "")

    if not _is_valid_upload_id(upload_id):
        return bad_request("Missing or malformed upload_id.")
    try:
        offset = int(offset_raw)
    except ValueError:
        return bad_request("offset must be an integer.")

    chunk = request.files.get("chunk")
    if chunk is None:
        return bad_request("No 'chunk' file in upload.")

    path = staged_path(upload_id)
    if not path.exists():
        return not_found("Upload", upload_id)

    current_size = path.stat().st_size
    if offset != current_size:
        # Client is out of sync — surface what we have so it can resume from
        # the right offset on the next try.
        return bad_request(
            f"Chunk offset {offset} does not match staged size {current_size}.",
            errors={"received": [str(current_size)]},
        )

    # Stream the chunk to disk in inner reads so a single oversize chunk
    # can't blow the cap silently.
    written = 0
    with open(path, "ab") as out:
        while True:
            data = chunk.stream.read(1024 * 1024)
            if not data:
                break
            written += len(data)
            if current_size + written > MAX_UPLOAD_BYTES:
                # Truncate back to the pre-write size so the session can
                # still be resumed below the cap if the client retries.
                out.flush()
                os.truncate(path, current_size)
                return bad_request(
                    f"Upload would exceed the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB cap."
                )
            out.write(data)

    _LOGGER.debug(
        "Appended %d bytes to %s (total=%d)", written, upload_id, current_size + written
    )
    return ok({"received": current_size + written})


# ── /finish ────────────────────────────────────────────────────────────

class FinishUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    upload_id: str


@dataclass(slots=True)
class FinishUploadResponse:
    upload_id: str
    size: int


@DATA_ROUTER.route("/uploads/finish", methods=["POST"])
@has_request_body(FinishUploadRequest)
def finish_upload():
    _, err = require_admin()
    if err is not None:
        return err
    _Request: FinishUploadRequest = get_request_body()
    if not _is_valid_upload_id(_Request.upload_id):
        return bad_request("Malformed upload_id.")
    path = staged_path(_Request.upload_id)
    if not path.exists():
        return not_found("Upload", _Request.upload_id)
    size = path.stat().st_size
    if size == 0:
        return bad_request("Upload is empty.")
    _LOGGER.info("Finished upload session %s (%d bytes)", _Request.upload_id, size)
    return ok({"upload_id": _Request.upload_id, "size": size})


# ── /abort (DELETE) ────────────────────────────────────────────────────

@DATA_ROUTER.route("/uploads/<uuid:upload_id>", methods=["DELETE"])
def abort_upload(upload_id: UUID):
    # R-033: the uuid converter validates + parses the id at the routing edge
    # (a malformed value 404s), which also removes the path-traversal concern
    # on the staged-file name (FU-544). The `/start|/chunk|/finish` routes take
    # upload_id in the BODY as a str, so `_is_valid_upload_id` stays for them.
    _, err = require_admin()
    if err is not None:
        return err
    path = staged_path(upload_id)
    if path.exists():
        try:
            path.unlink()
        except OSError as exc:
            _LOGGER.warning("Failed to unlink staged upload %s: %s", upload_id, exc)
    return no_content()
