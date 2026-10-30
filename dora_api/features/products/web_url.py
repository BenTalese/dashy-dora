"""The one rule for a product's `web_url` (create + ingest share it, R-003).

The SPA renders it as the `:href` of an "Open on store" button, so only an
`http`/`https` address is accepted — a `javascript:` URL would run in the
user's session on click. The cap matches `Product.web_url` (`String(255)`);
Postgres enforces it, so a longer value used to 500 on save.
"""
from urllib.parse import urlparse

WEB_URL_MAX_LENGTH = 255
_SCHEMES = ("http", "https")


def check_web_url(value: str | None) -> str | None:
    """Pydantic field-validator body: the value unchanged, or ValueError
    (which the request middleware reports as a per-field error)."""
    if value is None:
        return None
    if len(value) > WEB_URL_MAX_LENGTH:
        raise ValueError(f"web_url must be at most {WEB_URL_MAX_LENGTH} characters.")
    value = value.strip()
    try:
        parsed = urlparse(value)
    except ValueError as exc:
        raise ValueError("web_url must be an http:// or https:// address.") from exc
    if parsed.scheme.lower() not in _SCHEMES or not parsed.netloc:
        raise ValueError("web_url must be an http:// or https:// address.")
    return value
