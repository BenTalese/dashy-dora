"""End-to-end coverage for the A1 auth surface.

Each test gets a fresh requests.Session so test order doesn't matter
and the authenticated `dora` cookie from conftest doesn't leak in
when the test means to be anonymous.
"""
import uuid
from datetime import timedelta

import requests

from dora_api.app import app
from dora_api.domain.entities.auth_token import (
    PURPOSE_RESET_PASSWORD, PURPOSE_VERIFY_EMAIL,
)
from dora_api.infrastructure.auth_helpers import (
    RESET_PASSWORD_TTL, VERIFY_EMAIL_TTL, issue_token,
)


BASE = "http://localhost:5170/api/auth"


def _fresh_session() -> requests.Session:
    return requests.Session()


def _register(s: requests.Session, username: str, password: str, email: str | None = None):
    return s.post(f"{BASE}/register", json={
        "username": username, "password": password,
        **({"email": email} if email else {}),
    })


def test__register__rejects_weak_password(api):
    s = _fresh_session()
    response = _register(s, f"weak-{uuid.uuid4().hex[:6]}", "shortpw", "x@example.com")
    assert response.status_code == 422
    body = response.json()
    assert "password" in (body.get("errors") or {})


def test__register__rejects_bad_email_format(api):
    s = _fresh_session()
    response = _register(s, f"bademail-{uuid.uuid4().hex[:6]}", "Abcdefghij1", "not-an-email")
    assert response.status_code == 422


def test__register__happy_path(api):
    s = _fresh_session()
    username = f"happy-{uuid.uuid4().hex[:8]}"
    response = _register(s, username, "Abcdefghij1", f"{username}@example.com")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["username"] == username
    assert body["email_verified"] is False
    # Auto-login should have set the session cookie.
    me = s.get(f"{BASE}/me")
    assert me.status_code == 200


def test__register__rejects_duplicate_email_case_insensitive(api):
    s = _fresh_session()
    email = f"dup-{uuid.uuid4().hex[:8]}@example.com"
    first = _register(s, f"dup1-{uuid.uuid4().hex[:6]}", "Abcdefghij1", email)
    assert first.status_code == 200, first.text
    s2 = _fresh_session()
    second = _register(s2, f"dup2-{uuid.uuid4().hex[:6]}", "Abcdefghij1", email.upper())
    assert second.status_code == 422


def test__register__never_grants_admin(api):
    """FU-200 — /register no longer self-grants admin. Self-serve accounts
    are always created with `is_admin=False`; the first-admin path is
    /bootstrap-admin (single-use, separately tested)."""
    s = _fresh_session()
    username = f"noadmin-{uuid.uuid4().hex[:8]}"
    response = _register(s, username, "Abcdefghij1", f"{username}@example.com")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_admin"] is False
    assert body["email_verified"] is False


def test__capabilities__unauthenticated_and_reports_email_state(api):
    """The capabilities probe is reachable pre-auth (no session cookie)
    and reports whether outbound email is live. The test suite runs with
    no SMTP config, so it should report false. FU-392 added `demo_mode`,
    which is off unless DORA_DEMO_MODE is set (never in the test env)."""
    s = _fresh_session()
    response = s.get(f"{BASE}/capabilities")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {"email_sender_configured": False, "demo_mode": False}


def test__bootstrap_required__false_when_users_exist(api):
    """FU-200 — the bootstrap-required probe returns `false` once any user
    exists. The seeded `dora` test account guarantees that's the case here.
    Never leaks the actual user count."""
    s = _fresh_session()
    response = s.get(f"{BASE}/bootstrap-required")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {"required": False}


def test__bootstrap_admin__rejects_when_users_exist(api):
    """FU-200 — POST /bootstrap-admin is a one-shot endpoint. Once any
    user exists every subsequent call must 410, regardless of credentials,
    so the race ("first registrant becomes admin") is closed."""
    s = _fresh_session()
    response = s.post(f"{BASE}/bootstrap-admin", json={
        "username": f"intruder-{uuid.uuid4().hex[:6]}",
        "password": "Abcdefghij1",
        "email": f"intruder-{uuid.uuid4().hex[:6]}@example.com",
    })
    assert response.status_code == 410, response.text
    # Session must NOT have been established by a failed bootstrap.
    me = s.get(f"{BASE}/me")
    assert me.status_code == 401


def test__bootstrap_admin__rejects_weak_password(api):
    """Validation runs before the 410 — but only because the request
    *passes* the cheap fast-reject branch on an empty DB. Here it 410s
    first (existing users); a fresh-DB browser-verify covers the 422 path."""
    s = _fresh_session()
    response = s.post(f"{BASE}/bootstrap-admin", json={
        "username": f"weak-{uuid.uuid4().hex[:6]}",
        "password": "short",
        "email": f"weak-{uuid.uuid4().hex[:6]}@example.com",
    })
    # Either 410 (already bootstrapped) or 422 (weak password) is correct
    # — both refuse the request. The DB-has-users branch wins in CI.
    assert response.status_code in (410, 422), response.text


def test__forgot_password__anti_enumeration(api):
    s = _fresh_session()
    # Returns 204 regardless of whether the email exists.
    response = s.post(f"{BASE}/forgot-password", json={
        "email": f"nobody-{uuid.uuid4().hex}@example.com",
    })
    assert response.status_code == 204


def test__verify_email__invalid_token__is_400(api):
    s = _fresh_session()
    response = s.post(f"{BASE}/verify-email", json={"token": "definitely-not-real"})
    assert response.status_code == 400


def test__reset_password__invalid_token__is_400(api):
    s = _fresh_session()
    response = s.post(f"{BASE}/reset-password", json={
        "token": "bogus", "new_password": "Abcdefghij1",
    })
    assert response.status_code == 400


def test__reset_password__weak_password__is_422(api):
    s = _fresh_session()
    response = s.post(f"{BASE}/reset-password", json={
        "token": "bogus", "new_password": "short",
    })
    assert response.status_code == 422


# ── FU-197 — email on `/auth/me` + CSRF defence ────────────────────────
#
# These reuse the session-scoped `api` (the bootstrapped `dora`/`dora`
# user) rather than registering fresh accounts so we don't burn through
# the `auth.register` per-IP rate limit (10/min) — that bucket is shared
# across every test in the file. (The verified change-email confirmation
# flow this block once described was retired — FU-620; a PATCH of `email`
# now applies directly and simply un-verifies the address.)


def test__update_me__email__round_trips_and_validates(api):
    """The verified change-email flow was retired as overengineered — PATCH
    /auth/me now accepts `email` directly: it validates the format, updates
    in place, and reads back on /me."""
    import requests
    original = requests.get(f"{BASE}/me").json().get("email")
    try:
        # Invalid format is rejected (handler business-rule → 422).
        bad = requests.patch(f"{BASE}/me", json={"email": "not-an-email"})
        assert bad.status_code == 422, bad.text

        # A valid address saves, reflects in the DTO, and persists.
        new_email = f"dora-updated-{uuid.uuid4().hex[:6]}@example.com"
        patched = requests.patch(f"{BASE}/me", json={"email": new_email})
        assert patched.status_code == 200, patched.text
        assert patched.json()["email"] == new_email, patched.text
        assert requests.get(f"{BASE}/me").json()["email"] == new_email
    finally:
        # Restore so the shared bootstrap user doesn't leak state.
        requests.patch(f"{BASE}/me", json={"email": original or ""})


def test__update_me__show_assistant_round_trips(api):
    """FU-360.6 — the per-user 'show the Dora helper' toggle persists via
    PATCH /auth/me and reads back on /me. Default is True."""
    import requests
    # Default on a fresh session.
    before = requests.get(f"{BASE}/me").json()
    assert before["show_assistant"] is True, before

    # Turn it off; the DTO reflects the change and /me confirms it persisted.
    patched = requests.patch(f"{BASE}/me", json={"show_assistant": False})
    assert patched.status_code == 200, patched.text
    assert patched.json()["show_assistant"] is False, patched.text
    assert requests.get(f"{BASE}/me").json()["show_assistant"] is False

    # Restore so the shared bootstrap user doesn't leak state into other tests.
    restore = requests.patch(f"{BASE}/me", json={"show_assistant": True})
    assert restore.status_code == 200, restore.text
    assert requests.get(f"{BASE}/me").json()["show_assistant"] is True


def test__csrf__mutation_without_header_is_403(api):
    """FU-197 — the double-submit defence rejects an authenticated
    mutating request that's missing the `X-CSRF-Token` header (the
    cookie may still be set; the *match* is what gates the call)."""
    import requests
    # Bypass the conftest's auto-attach by passing an empty header
    # explicitly; the wrapper sets it via `setdefault`, so a present-
    # but-empty value wins and the server sees no valid token. PATCH
    # the username back to its existing value so a future state-leak
    # would be a no-op anyway — but expect the call to never reach the
    # handler because the CSRF gate fires first.
    response = requests.patch(
        f"{BASE}/me",
        json={"username": "dora"},
        headers={"X-CSRF-Token": ""},
    )
    assert response.status_code == 403, response.text


# Settings rebuild Phase 4 — profile picture round-trip.
_PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYPhfDwAChwGA"
    "60e6kgAAAABJRU5ErkJggg=="
)


def test__profile_picture__set_fetch_and_clear(api):
    """A user can set a profile picture (data-URL), it round-trips on the
    `has_image` flag + the bytes endpoint, and clearing removes it again."""
    s = _fresh_session()
    username = f"pic-{uuid.uuid4().hex[:8]}"
    reg = _register(s, username, "Abcdefghij1", f"{username}@example.com")
    assert reg.status_code == 200, reg.text
    user_id = reg.json()["user_id"]
    assert reg.json()["has_image"] is False

    # No picture yet → bytes endpoint 404s.
    img = s.get(f"http://localhost:5170/api/users/{user_id}/image")
    assert img.status_code == 404

    # Set one via PATCH /auth/me.
    patched = s.patch(f"{BASE}/me", json={"image": _PNG_DATA_URL})
    assert patched.status_code == 200, patched.text
    assert patched.json()["has_image"] is True

    # Bytes now served with the declared mime.
    img = s.get(f"http://localhost:5170/api/users/{user_id}/image")
    assert img.status_code == 200, img.text
    assert img.headers["Content-Type"].startswith("image/png")
    assert len(img.content) > 0

    # Clear it → flag flips back, bytes 404 again.
    cleared = s.patch(f"{BASE}/me", json={"clear_image": True})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["has_image"] is False
    img = s.get(f"http://localhost:5170/api/users/{user_id}/image")
    assert img.status_code == 404


def test__profile_picture__rejects_oversize_data_url(api):
    """The ~4.5 MB base64 cap (max_length=6_000_000) rejects a huge payload
    rather than letting a 50 MB selfie through. The middleware emits 400 on
    pydantic ValidationError (codebase convention; see
    infrastructure/middleware.deserialise_web_request)."""
    s = _fresh_session()
    username = f"big-{uuid.uuid4().hex[:8]}"
    assert _register(s, username, "Abcdefghij1", f"{username}@example.com").status_code == 200
    oversize = "data:image/png;base64," + ("A" * 6_000_001)
    resp = s.patch(f"{BASE}/me", json={"image": oversize})
    assert resp.status_code == 400, resp.status_code


def test__dashboard_layout__set_and_clear(api):
    """A user's dashboard layout JSON round-trips on /auth/me and clears with
    an explicit null (Dashboard rebuild Phase 2)."""
    s = _fresh_session()
    username = f"dash-{uuid.uuid4().hex[:8]}"
    reg = _register(s, username, "Abcdefghij1", f"{username}@example.com")
    assert reg.status_code == 200, reg.text
    assert reg.json()["dashboard_layout"] is None

    layout = '{"order":["budget","attention"],"hidden":["meal_plan"]}'
    patched = s.patch(f"{BASE}/me", json={"dashboard_layout": layout})
    assert patched.status_code == 200, patched.text
    assert patched.json()["dashboard_layout"] == layout

    # Explicit null clears it back to the default layout.
    cleared = s.patch(f"{BASE}/me", json={"dashboard_layout": None})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["dashboard_layout"] is None


def test__login__rate_limit_returns_429_eventually(api):
    s = _fresh_session()
    # The endpoint allows 5/min per IP. Spam past the limit.
    for _ in range(6):
        s.post(f"{BASE}/login", json={
            "username": "rate-probe", "password": "wrong",
        })
    response = s.post(f"{BASE}/login", json={
        "username": "rate-probe", "password": "wrong",
    })
    assert response.status_code in (401, 429)
    if response.status_code == 429:
        assert "Retry-After" in response.headers


# ── FU-547 / FU-537 / FU-522 — token lifecycle security pins ──────────
#
# The invalid-token 400s above prove a *garbage* string is refused. These
# prove the three properties that make a real token safe once minted:
#   (a) single-use — a consumed token can't be replayed;
#   (b) expiry — an in-date filter actually rejects a stale token;
#   (c) cross-purpose isolation — a token minted for purpose A is inert on
#       purpose B's route (the FU-522 concern, generalised).
#
# Tokens only ever reach a real user by email, which the test suite doesn't
# send. The e2e suite runs the app in-process (conftest dispatches through
# Flask's test client against the same `app`/`db` + SQLite file), so we mint
# real tokens directly through `issue_token` in an app context and then drive
# the public consuming routes over HTTP. The per-test snapshot rollback wipes
# the minted rows (and dora's flipped email_verified / password) afterwards.


def _dora_user_id() -> uuid.UUID:
    # `requests` is rebound to the authenticated `dora` test client by the
    # `api` fixture, so /me identifies the bootstrap user.
    return uuid.UUID(requests.get(f"{BASE}/me").json()["user_id"])


def _mint(purpose: str, ttl: timedelta, payload: str | None = None) -> str:
    with app.app_context():
        return issue_token(_dora_user_id(), purpose, ttl, payload=payload)


def _reset_rate_buckets() -> None:
    # verify-email (10/min) + reset-password (5/min) share process-lifetime
    # IP buckets across the whole file; several consuming calls per test would
    # otherwise accumulate toward the limit and flake. Clear before each pin so
    # a token 400 is a *token* 400, never a 429. Safe globally — the one test
    # that relies on accumulation (login rate-limit) builds its own burst.
    from dora_api.infrastructure import auth_helpers
    with auth_helpers._buckets_lock:
        auth_helpers._buckets.clear()


_GOOD_PW = "Abcdefghij1"


def test__verify_email__token_is_single_use(api):
    _reset_rate_buckets()
    token = _mint(PURPOSE_VERIFY_EMAIL, VERIFY_EMAIL_TTL)
    s = _fresh_session()
    first = s.post(f"{BASE}/verify-email", json={"token": token})
    assert first.status_code == 200, first.text
    assert first.json() == {"email_verified": True}
    # Replay of the now-consumed token must fail.
    second = s.post(f"{BASE}/verify-email", json={"token": token})
    assert second.status_code == 400, second.text


def test__reset_password__token_is_single_use(api):
    _reset_rate_buckets()
    token = _mint(PURPOSE_RESET_PASSWORD, RESET_PASSWORD_TTL)
    s = _fresh_session()
    first = s.post(f"{BASE}/reset-password", json={"token": token, "new_password": _GOOD_PW})
    assert first.status_code == 200, first.text
    second = s.post(f"{BASE}/reset-password", json={"token": token, "new_password": _GOOD_PW})
    assert second.status_code == 400, second.text


def test__reset_password__consuming_one_token_revokes_sibling_reset_tokens(api):
    """A successful reset revokes every other live reset token for that user
    (`revoke_tokens_for_user`), so an attacker holding a second, never-used
    reset link is locked out the moment the real user resets."""
    _reset_rate_buckets()
    used = _mint(PURPOSE_RESET_PASSWORD, RESET_PASSWORD_TTL)
    sibling = _mint(PURPOSE_RESET_PASSWORD, RESET_PASSWORD_TTL)
    s = _fresh_session()
    assert s.post(
        f"{BASE}/reset-password", json={"token": used, "new_password": _GOOD_PW}
    ).status_code == 200
    revoked = s.post(f"{BASE}/reset-password", json={"token": sibling, "new_password": _GOOD_PW})
    assert revoked.status_code == 400, revoked.text


def test__verify_email__expired_token_is_rejected(api):
    _reset_rate_buckets()
    token = _mint(PURPOSE_VERIFY_EMAIL, timedelta(seconds=-1))
    resp = _fresh_session().post(f"{BASE}/verify-email", json={"token": token})
    assert resp.status_code == 400, resp.text


def test__reset_password__expired_token_is_rejected(api):
    _reset_rate_buckets()
    token = _mint(PURPOSE_RESET_PASSWORD, timedelta(seconds=-1))
    resp = _fresh_session().post(
        f"{BASE}/reset-password", json={"token": token, "new_password": _GOOD_PW}
    )
    assert resp.status_code == 400, resp.text


def test__verify_email__rejects_reset_password_token(api):
    """Purpose is part of the token lookup — a reset token can't verify email."""
    _reset_rate_buckets()
    token = _mint(PURPOSE_RESET_PASSWORD, RESET_PASSWORD_TTL)
    resp = _fresh_session().post(f"{BASE}/verify-email", json={"token": token})
    assert resp.status_code == 400, resp.text


def test__reset_password__rejects_verify_email_token(api):
    _reset_rate_buckets()
    token = _mint(PURPOSE_VERIFY_EMAIL, VERIFY_EMAIL_TTL)
    resp = _fresh_session().post(
        f"{BASE}/reset-password", json={"token": token, "new_password": _GOOD_PW}
    )
    assert resp.status_code == 400, resp.text


def test__verify_email__rejects_foreign_purpose_token(api):
    """A token minted for a different purpose (here reset-password) must not
    be honoured on the verify-email route — purpose-matching is enforced."""
    _reset_rate_buckets()
    token = _mint(PURPOSE_RESET_PASSWORD, RESET_PASSWORD_TTL)
    resp = _fresh_session().post(f"{BASE}/verify-email", json={"token": token})
    assert resp.status_code == 400, resp.text


def test__bootstrap_admin__creates_first_admin_on_empty_install(api):
    """QA 2026-10-29 — the success path. The `fb49f00a` import tidy dropped
    `hash_password` / `audit_emit` from this module, so every fresh install
    500'd on /setup; the existing tests only covered the reject branches.
    Wipe the seeded users (the per-test snapshot restores them) and walk the
    one-shot path end to end: 200, admin flag, session established."""
    from sqlalchemy import delete as sa_delete
    from dora_api.app import db
    with app.app_context():
        db.session.execute(sa_delete(db.metadata.tables["User"]))
        db.session.commit()

    s = _fresh_session()
    assert s.get(f"{BASE}/bootstrap-required").json() == {"required": True}
    response = s.post(f"{BASE}/bootstrap-admin", json={
        "username": "first-admin",
        "password": "Abcdefghij1",
        "email": "first-admin@example.com",
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["username"] == "first-admin"
    assert body["is_admin"] is True
    me = s.get(f"{BASE}/me")
    assert me.status_code == 200, me.text
    assert me.json()["is_admin"] is True
    # One-shot: a second call is refused.
    again = s.post(f"{BASE}/bootstrap-admin", json={
        "username": "second", "password": "Abcdefghij1",
    })
    assert again.status_code == 410


# ── Security review: per-username login limit, timing, change-password ──

def test__login__IpRotatesButUsernameRepeats__Returns429(api, monkeypatch):
    """The IP bucket is trivially defeated by a forged / misproxied
    `X-Forwarded-For`. Simulate a fresh IP per request: the per-username
    bucket (10 / 15 min) must still cut guessing off with a 429."""
    import itertools
    import types
    from dora_api.infrastructure import auth_helpers
    _reset_rate_buckets()
    counter = itertools.count()

    class _RotatingRequest:
        @property
        def remote_addr(self):
            return f"10.9.{next(counter)}.1"

    monkeypatch.setattr(auth_helpers, "request", _RotatingRequest())
    s = _fresh_session()
    victim = f"victim-{uuid.uuid4().hex[:6]}"
    for _ in range(10):
        r = s.post(f"{BASE}/login", json={"username": victim, "password": "wrong-pw"})
        assert r.status_code == 401, r.text
    blocked = s.post(f"{BASE}/login", json={"username": victim.upper(), "password": "x"})
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 60
    # A different account is unaffected.
    other = s.post(f"{BASE}/login", json={"username": f"o-{victim}", "password": "x"})
    assert other.status_code == 401
    _reset_rate_buckets()


def test__login__UsernameBudgetExhausted__CorrectPasswordStillSignsIn(api, monkeypatch):
    """The per-username bucket counts guesses, it is not a lockout: an
    attacker spraying `dora`'s username must not lock the real owner out —
    only wrong passwords are refused once the budget is spent."""
    import itertools
    from dora_api.infrastructure import auth_helpers
    _reset_rate_buckets()
    counter = itertools.count()

    class _RotatingRequest:
        @property
        def remote_addr(self):
            return f"10.8.{next(counter)}.1"

    monkeypatch.setattr(auth_helpers, "request", _RotatingRequest())
    attacker = _fresh_session()
    for _ in range(10):
        assert attacker.post(f"{BASE}/login", json={"username": "dora", "password": "wrong-pw"}).status_code == 401
    assert attacker.post(f"{BASE}/login", json={"username": "dora", "password": "wrong-pw"}).status_code == 429
    owner = _fresh_session()
    assert owner.post(f"{BASE}/login", json={"username": "dora", "password": "dora"}).status_code == 200
    _reset_rate_buckets()


def test__login__UnknownUsername__StillRunsDummyHashVerify(api, monkeypatch):
    """Anti-enumeration: an unknown username must cost the same scrypt verify
    as a wrong password, so response timing can't reveal which users exist."""
    from dora_api.features.auth import login as login_mod
    _reset_rate_buckets()
    seen: list[str] = []
    real = login_mod.check_password_hash

    def _spy(pwhash, password):
        seen.append(pwhash)
        return real(pwhash, password)

    monkeypatch.setattr(login_mod, "check_password_hash", _spy)
    r = _fresh_session().post(f"{BASE}/login", json={
        "username": f"nobody-{uuid.uuid4().hex[:8]}", "password": "whatever-pw",
    })
    assert r.status_code == 401
    assert seen == [login_mod._DUMMY_PASSWORD_HASH]
    _reset_rate_buckets()


def test__change_password__OverPerUserLimit__Returns429(api):
    from dora_api.features.auth import change_password as cp
    from dora_api.infrastructure.auth_helpers import rate_limit
    _reset_rate_buckets()
    user_id = str(_dora_user_id())
    for _ in range(cp._CHANGE_PASSWORD_MAX):
        assert rate_limit(
            cp._CHANGE_PASSWORD_SCOPE, cp._CHANGE_PASSWORD_MAX, subject=user_id,
            window_seconds=cp._CHANGE_PASSWORD_WINDOW_SECONDS,
        )
    r = requests.post(f"{BASE}/me/password", json={
        "current_password": "wrong-current", "new_password": "Zyxwvutsrq987",
    })
    assert r.status_code == 429
    assert "Retry-After" in r.headers
    _reset_rate_buckets()
