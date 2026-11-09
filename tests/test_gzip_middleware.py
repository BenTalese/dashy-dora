"""FU-992: API JSON is gzipped when the client accepts it; nothing else changes."""
import gzip

from werkzeug.test import Client
from werkzeug.wrappers import Response

from dora_api.infrastructure.compression import GzipMiddleware

_BIG_JSON = b'{"items": [' + b",".join(b'{"name": "Plain Flour"}' for _ in range(200)) + b"]}"


def _client(body: bytes, mimetype: str, status: int = 200) -> Client:
    def app(environ, start_response):
        return Response(body, status=status, mimetype=mimetype)(environ, start_response)
    return Client(GzipMiddleware(app))


def test__large_json_is_gzipped_for_a_client_that_accepts_it():
    response = _client(_BIG_JSON, "application/json").get("/", headers={"Accept-Encoding": "gzip, br"})
    assert response.headers["Content-Encoding"] == "gzip"
    assert "Accept-Encoding" in response.headers["Vary"]
    assert int(response.headers["Content-Length"]) == len(response.data)
    assert gzip.decompress(response.data) == _BIG_JSON


def test__no_accept_encoding_leaves_the_body_alone():
    response = _client(_BIG_JSON, "application/json").get("/")
    assert "Content-Encoding" not in response.headers
    assert response.data == _BIG_JSON


def test__small_bodies_and_binary_types_are_not_compressed():
    small = _client(b'{"ok": true}', "application/json").get("/", headers={"Accept-Encoding": "gzip"})
    assert "Content-Encoding" not in small.headers
    assert small.data == b'{"ok": true}'

    binary = _client(_BIG_JSON, "application/zip").get("/", headers={"Accept-Encoding": "gzip"})
    assert "Content-Encoding" not in binary.headers
    assert binary.data == _BIG_JSON


def test__not_modified_is_passed_through():
    response = _client(b"", "application/json", status=304).get("/", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 304
    assert "Content-Encoding" not in response.headers
