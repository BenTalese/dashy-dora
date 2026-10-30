"""Regression pins for the e-mailed SPA deep-link format.

The SPA runs in **hash-history** mode (`web_app/quasar.config` →
build.vueRouterMode: 'hash'), so every link e-mailed to a user that targets an
in-app route MUST carry the route in the URL *fragment* (`…/#/reset-password?
token=…`). A path-based link (`…/reset-password?token=…`) is served the SPA
shell but the hash router never sees the route — it resolves to `/`, and the
auth guard bounces the logged-out visitor to `#/login`. That silently
dead-ended every password-reset / verify-email link.

These pure unit tests (no server, no request context — the builders fall back
to the localhost dev origin) fix that contract in place so it can't regress.
"""
from dora_api.infrastructure.auth_helpers import (
    build_reset_url,
    build_verify_url,
    spa_deep_link,
)


def test__spa_deep_link__puts_the_route_in_the_hash_fragment():
    url = spa_deep_link("/alerts")
    # The route lives after the '#', never as a bare path.
    origin, _, fragment = url.partition("#")
    assert fragment == "/alerts", url
    assert not origin.endswith("/alerts"), url
    assert origin.endswith("/"), url  # "<origin>/#<route>"


def test__build_reset_url__is_a_hash_route_carrying_the_token():
    url = build_reset_url("abc123")
    assert "/#/reset-password?token=abc123" in url, url
    # The token must sit in the hash query (after '#'), not the page query.
    assert "token=abc123" in url.partition("#")[2], url


def test__build_verify_url__is_a_hash_route_carrying_the_token():
    url = build_verify_url("tok-xyz")
    assert "/#/verify-email?token=tok-xyz" in url, url
    assert "token=tok-xyz" in url.partition("#")[2], url


def test__deep_links__never_emit_a_bare_path_route():
    # A path-based link (the old bug) would place the route before any '#'.
    for url in (
        build_reset_url("t"),
        build_verify_url("t"),
        spa_deep_link("/alerts?token=t"),
    ):
        before_hash = url.partition("#")[0]
        assert "reset-password" not in before_hash, url
        assert "verify-email" not in before_hash, url
        assert "alerts" not in before_hash, url


# ── SEC-2: links never come from request headers ────────────────────────

def test__public_base_url__ignores_a_forged_origin_header(monkeypatch):
    """A caller's `Origin` (or `Host`) must never become the host of a link
    that carries a reset token."""
    from dora_api.app import app
    from dora_api.infrastructure import auth_helpers

    monkeypatch.setattr(auth_helpers, "configured_public_url", lambda: "")
    with app.test_request_context(
        headers={"Origin": "https://evil.example", "Host": "evil.example"},
    ):
        url = build_reset_url("tok")
    assert "evil.example" not in url, url


def test__public_base_url__uses_the_configured_url(monkeypatch):
    from dora_api.infrastructure import auth_helpers

    monkeypatch.setattr(
        auth_helpers, "configured_public_url", lambda: "https://dora.home.example",
    )
    assert build_reset_url("tok").startswith("https://dora.home.example/#/")


def test__link_mail__production_without_public_url__is_skipped(monkeypatch):
    from dora_api.infrastructure import auth_helpers, profile

    monkeypatch.setattr(auth_helpers, "configured_public_url", lambda: "")
    monkeypatch.setattr(profile, "is_production", lambda: True)
    sent: list[str] = []
    auth_helpers.try_send_link_mail(lambda **kw: sent.append(kw["to"]), to="a@b.c")
    assert sent == []

    monkeypatch.setattr(
        auth_helpers, "configured_public_url", lambda: "https://dora.home.example",
    )
    auth_helpers.try_send_link_mail(lambda **kw: sent.append(kw["to"]), to="a@b.c")
    assert sent == ["a@b.c"]
