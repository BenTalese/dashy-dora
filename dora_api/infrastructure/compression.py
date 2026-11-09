"""Gzip for the API's JSON and text responses (FU-992).

The self-host serves the API straight from gunicorn (or the dev server), and
only the SPA's static files pass through nginx's gzip. Uncompressed, the
cookbook's recipe list ran to ~5KB a recipe and the stock list to ~0.8KB an
item; gzip takes both down by more than ten times.

A WSGI wrapper rather than a Flask `after_request` hook: it runs after every
hook has finished with the body (some read it as JSON), and it never sees a
response it shouldn't touch, such as a file download, because it only buffers
the types listed below.
"""

import gzip
from collections.abc import Callable, Iterable

_COMPRESSIBLE_TYPES = (
    "application/json",
    "application/problem+json",
    "text/",
    "application/javascript",
    "image/svg+xml",
)
_MIN_SIZE = 1024
_LEVEL = 5


def _header(headers: list[tuple[str, str]], name: str) -> str | None:
    lower = name.lower()
    for key, value in headers:
        if key.lower() == lower:
            return value
    return None


def _compressible(status: str, headers: list[tuple[str, str]]) -> bool:
    code = int(status.split(" ", 1)[0])
    if code < 200 or code in (204, 206, 304):
        return False
    if _header(headers, "Content-Encoding") is not None:
        return False
    content_type = (_header(headers, "Content-Type") or "").lower()
    return content_type.startswith(_COMPRESSIBLE_TYPES)


class GzipMiddleware:
    def __init__(self, app: Callable) -> None:
        self.app = app

    def __call__(self, environ: dict, start_response: Callable) -> Iterable[bytes]:
        if "gzip" not in environ.get("HTTP_ACCEPT_ENCODING", "").lower():
            return self.app(environ, start_response)

        captured: dict = {}

        def capture(status, headers, exc_info=None):
            captured["status"], captured["headers"], captured["exc_info"] = status, headers, exc_info
            # Flask never uses the legacy `write` callable this returns.
            return lambda _data: None

        body_iter = self.app(environ, capture)
        status, headers = captured["status"], captured["headers"]

        if not _compressible(status, headers):
            start_response(status, headers, captured["exc_info"])
            return body_iter

        try:
            body = b"".join(body_iter)
        finally:
            close = getattr(body_iter, "close", None)
            if close is not None:
                close()

        vary = _header(headers, "Vary")
        headers = [(k, v) for k, v in headers if k.lower() not in ("content-length", "vary")]
        headers.append(("Vary", f"{vary}, Accept-Encoding" if vary else "Accept-Encoding"))
        if len(body) >= _MIN_SIZE:
            body = gzip.compress(body, compresslevel=_LEVEL)
            headers.append(("Content-Encoding", "gzip"))
        headers.append(("Content-Length", str(len(body))))
        start_response(status, headers, captured["exc_info"])
        return [body]
