"""Serve the built SPA from Flask.

Used ONLY by the desktop bundle (`desktop_app.py`), where pywebview's
window points at Flask and there's no nginx in front. For the Docker
and `quasar dev` paths these routes are wired but never reached
(nginx / Quasar's dev server intercept everything before Flask sees
it).

Path resolution:
    1. `DORA_SPA_DIR` env var — set explicitly (PyInstaller bundle
       passes the unpacked location via `desktop_app.py`).
    2. `<repo-root>/web_app/dist/spa` — CWD-relative fallback for
       running `python -m dora_api.startup` from a checkout that's
       already built the SPA.

vue-router uses history mode, so every URL that doesn't map to a
static file must serve `index.html` and let the client router take
over. The catch-all route is intentionally LESS SPECIFIC than the
`/api/...` blueprints, so Werkzeug's routing picks the API ones
first; the catch-all only ever fires for SPA paths.
"""
import logging
import mimetypes
import os
from pathlib import Path

from flask import abort, send_from_directory

from dora_api.features.routers import SPA_ROUTER
from dora_api.infrastructure.api_response import endpoint_not_found


_LOGGER = logging.getLogger(__name__)


# FU-540/FU-551 — `send_from_directory` derives Content-Type from the stdlib
# `mimetypes`, which on Windows reads the registry — where `.js` is often
# mapped to `text/plain`. Browsers enforce strict MIME checking for ES module
# scripts, so a `text/plain` `.js` is REJECTED and the SPA never boots (blank
# page). Force the correct types here so the backend-served SPA works on any
# host OS (R-005 portability — matters for Windows self-host + the desktop
# bundle, which is the only path that reaches these routes). Linux/containers
# are usually already correct; this is belt-and-braces.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/json", ".json")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("application/wasm", ".wasm")


def _spa_dir() -> Path | None:
    """Resolve the directory containing the built SPA's `index.html`.
    Returns None when no usable bundle is found so the routes can
    503 cleanly rather than crash with a stack trace."""
    explicit = os.environ.get("DORA_SPA_DIR")
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if (path / "index.html").is_file():
            return path
        _LOGGER.warning("DORA_SPA_DIR=%s but no index.html there", path)
        return None
    fallback = Path.cwd() / "web_app" / "dist" / "spa"
    if (fallback / "index.html").is_file():
        return fallback
    return None


def _serve_file_or_index(requested: str | None):
    """Send the requested file from the SPA dir, or fall back to
    index.html when the path doesn't match a file (history-mode
    routing)."""
    root = _spa_dir()
    if root is None:
        abort(503, "SPA bundle not found. Run `quasar build` in web_app/ "
                   "or set DORA_SPA_DIR.")
    if requested:
        candidate = (root / requested).resolve()
        # Guard against `../` path traversal — the resolved path must
        # still live under the SPA root.
        try:
            candidate.relative_to(root)
        except ValueError:
            abort(404)
        if candidate.is_file():
            return send_from_directory(root, requested)
    return send_from_directory(root, "index.html")


@SPA_ROUTER.route("/", methods=["GET"])
def serve_root():
    return _serve_file_or_index(None)


@SPA_ROUTER.route("/<path:requested>", methods=["GET"])
def serve_path(requested: str):
    # API blueprints (/api/..., /mapi/... once collapse lands) win on
    # routing precedence because they're more specific than this
    # catch-all. Anything that reaches here is an SPA path — EXCEPT an
    # unknown/retired /api/... URL, which must 404 like an API endpoint
    # rather than answer 200 with index.html (an API client reading HTML
    # as success is far worse than a clean not-found; surfaced when the
    # shopping-list CSV /export endpoint was removed in UX-v2).
    #
    # return the shared JSON problem-detail (the same body the request
    # middleware returns for no-route paths) rather than `abort(404)`, which
    # would yield the default HTML 404 — so an unmatched GET /api/<x> matches
    # POST/PATCH/DELETE on the same path.
    if requested.startswith("api/"):
        return endpoint_not_found()
    return _serve_file_or_index(requested)
