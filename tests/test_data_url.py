"""The one stored-image decoder (`infrastructure/data_url.py`). It serves only
raster image types: echoing an uploaded `text/html` mimetype back from an
image route ran script on the app's origin (QA2-01 / SEC-1)."""
import base64

import pytest

from dora_api.infrastructure.data_url import decode_data_url


def _blob(mime: str, payload: bytes = b"\x89PNG\r\n") -> bytes:
    return f"data:{mime};base64,{base64.b64encode(payload).decode()}".encode()


@pytest.mark.parametrize("mime", ["image/png", "image/jpeg", "image/webp", "image/gif", "IMAGE/PNG"])
def test__decode__serves_raster_images(mime):
    decoded = decode_data_url(_blob(mime))
    assert decoded == (mime.lower(), b"\x89PNG\r\n")


@pytest.mark.parametrize("mime", ["text/html", "image/svg+xml", "application/javascript", "text/xml"])
def test__decode__refuses_anything_that_is_not_a_raster_image(mime):
    assert decode_data_url(_blob(mime, b"<script>alert(1)</script>")) is None


@pytest.mark.parametrize("blob", [None, b"", b"not a data url", b"data:image/png;base64"])
def test__decode__empty_or_malformed_is_no_image(blob):
    assert decode_data_url(blob) is None
