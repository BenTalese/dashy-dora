"""Transactional email sender used by A1's auth flows.

Wraps stdlib smtplib so dora_api can fire one-off transactional emails
(verification, password reset, change confirmation) self-contained.

SMTP config resolves through `resolved_operational_config()` (FU-333
Buckets B + C). The admin edits everything — including the password —
in Settings → Admin → System → Email; the password is Fernet-encrypted
at rest. Empty username still puts the sender in dry-run mode (logs
the body), which is essential for dev / desktop installs that don't
need real email.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

_LOGGER = logging.getLogger(__name__)


_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "email_templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)

# The shared _layout.html header renders the brand banner (mascot + the
# "Dashy Dora" wordmark in the Cute Dino font). Web fonts don't render in
# email clients, so the wordmark is a pre-rendered PNG embedded inline via
# CID (data: URIs get stripped by Gmail/Outlook). Every transactional email
# extends that layout, so send_email attaches this image by default.
# Regenerate with email_templates/assets/generate_brand_banner.py (a
# browser-canvas render of the real font — see that script's docstring).
_BRAND_BANNER_CID = "brand-banner"
_BRAND_BANNER_PATH = _TEMPLATE_DIR / "assets" / "brand-banner.png"


@lru_cache(maxsize=1)
def _brand_banner_bytes() -> bytes | None:
    """Read the brand banner PNG once. None if it's missing so a send still
    goes out (the layout's alt text degrades gracefully)."""
    try:
        return _BRAND_BANNER_PATH.read_bytes()
    except OSError:
        _LOGGER.warning(
            "brand banner missing at %s — emails will send without it",
            _BRAND_BANNER_PATH,
        )
        return None


@dataclass(slots=True)
class _SmtpConfig:
    host: str
    port: int
    username: str
    password: str
    sender: str
    use_tls: bool
    dry_run: bool


_DRY_RUN_CONFIG = _SmtpConfig(
    host="", port=587, username="", password="", sender="", use_tls=True, dry_run=True,
)


def email_sender_configured() -> bool:
    """True when the sender has a live SMTP username to use. Dry-run
    installs (which just log the outbound body) are treated as *not*
    configured — a normal user can't read server logs, so surfaces gated
    on this (e.g. the login page's "Forgot password?" link) should hide.
    """
    return not _config().dry_run


def _config() -> _SmtpConfig:
    """Read the resolved AppSetting-backed SMTP config. If the DB isn't
    available (e.g. a unit test that imports this module without a Flask
    context), return a dry-run config so callers still function as
    dry-run loggers."""
    from dora_api.features.app_settings.operational_config import \
        resolved_operational_config
    try:
        op = resolved_operational_config()
    except Exception:
        return _DRY_RUN_CONFIG
    host = op.smtp_host or "smtp.gmail.com"
    username = op.smtp_username
    sender = op.smtp_from or username
    return _SmtpConfig(
        host=host,
        port=op.smtp_port,
        username=username,
        password=op.smtp_password,
        sender=sender,
        use_tls=op.smtp_use_tls,
        dry_run=not username,
    )


def render_template(name: str, **context: Any) -> str:
    """Render a Jinja template under dora_api/email_templates/."""
    template = _env.get_template(name)
    return template.render(**context)


def send_email(
    *,
    to: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
    include_brand_banner: bool = True,
) -> None:
    """Send a single email synchronously. Raises on SMTP failure;
    callers should wrap in `try_send` (auth_helpers) when delivery
    failure shouldn't propagate to the user.

    `include_brand_banner` embeds the shared header banner (referenced by
    the layout as `cid:brand-banner`) as an inline image. Defaults on since
    every transactional template extends _layout.html.
    """
    cfg = _config()
    if cfg.dry_run:
        _LOGGER.info(
            "DRY-RUN email | to=%s | subject=%s\n%s",
            to, subject, text_body or html_body,
        )
        return

    # The text + html alternatives always live together in a
    # multipart/alternative. When an inline image rides along, that
    # alternative is nested inside a multipart/related wrapper alongside
    # the image, so clients resolve the cid: reference to the attached PNG.
    alternative = MIMEMultipart("alternative")
    if text_body:
        alternative.attach(MIMEText(text_body, "plain", "utf-8"))
    alternative.attach(MIMEText(html_body, "html", "utf-8"))

    banner = _brand_banner_bytes() if include_brand_banner else None
    if banner is not None:
        message = MIMEMultipart("related")
        message.attach(alternative)
        image = MIMEImage(banner, _subtype="png")
        image.add_header("Content-ID", f"<{_BRAND_BANNER_CID}>")
        image.add_header(
            "Content-Disposition", "inline", filename="brand-banner.png",
        )
        message.attach(image)
    else:
        message = alternative

    message["Subject"] = subject
    message["From"] = cfg.sender
    message["To"] = to

    context = ssl.create_default_context()
    with smtplib.SMTP(cfg.host, cfg.port) as server:
        server.ehlo()
        if cfg.use_tls:
            server.starttls(context=context)
            server.ehlo()
        if cfg.username and cfg.password:
            server.login(cfg.username, cfg.password)
        server.sendmail(cfg.sender, [to], message.as_string())
    _LOGGER.info("Sent transactional email to %s (%s)", to, subject)
