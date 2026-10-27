"""Stored images: `data:<mime>;base64,<data>` UTF-8 blobs on the entity row,
served back as raw bytes by the image routes.

One decoder for every image route (finalisation 01-R7). It serves only raster
image types: the mimetype comes from whoever uploaded the blob, and echoing it
back let a `data:text/html;…` "image" run script on the app's own origin
(QA2-01 / SEC-1). SVG is excluded for the same reason (it can carry script).
"""
from __future__ import annotations

import base64
import re
from typing import Callable

from flask import Response

SERVABLE_IMAGE_TYPES = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif", "image/avif"})

_DATA_URL_RE = re.compile(r"^data:(?P<mime>[\w/+.-]+);base64,(?P<data>.+)$", re.DOTALL)


def decode_data_url(blob: bytes | None) -> tuple[str, bytes] | None:
    """`(mime, raw_bytes)` for a stored image, or None when the blob is empty,
    malformed or not a servable image type (callers treat all as "no image")."""
    if not blob:
        return None
    match = _DATA_URL_RE.match(blob.decode("utf-8", "ignore"))
    if not match:
        return None
    mime = match.group("mime").lower()
    if mime not in SERVABLE_IMAGE_TYPES:
        return None
    try:
        return mime, base64.b64decode(match.group("data"), validate=False)
    except (ValueError, TypeError):
        return None


def data_url_response(blob: bytes | None, on_missing: Callable[[], Response]) -> Response:
    """The image as raw bytes (no caching: an upload replaces it in place), or
    `on_missing()` when there is no servable image."""
    decoded = decode_data_url(blob)
    if decoded is None:
        return on_missing()
    mime, raw = decoded
    return Response(raw, mimetype=mime, headers={"Cache-Control": "no-cache"})
