import uuid

import pytest
import requests

from tests.support import is_valid_uuid

#region ---------------- setup ----------------

# list endpoints take query options on the query string and return a
# `{items, total, page, limit}` envelope; query-option errors come back via
# `bad_request(str(exc))` (message in `title`). The seed user is now
# `dora` / `ben.talese@gmail.com` (admin), not "The Coolest Guy".

base_route = 'http://localhost:5170/api/users'

#endregion setup

#region ---------------- get_users tests ----------------


def test__get_users__GettingUsers__GetsAllExpectedAttributes(api):
    # Filter to the seeded user — other suites (auth flows) register users into
    # the shared DB, so the unfiltered first row isn't necessarily 'dora'.
    _User = requests.get(f'{base_route}?filter=username:eq:dora').json()['items'][0]

    assert _User['email'] == 'ben.talese@gmail.com'
    assert _User['send_deals_on_day'] == 6
    assert _User['username'] == 'dora'
    assert _User['is_admin'] is True
    # Deactivate-instead-of-delete: seeded rows are usable accounts.
    assert _User['is_active'] is True
    assert is_valid_uuid(_User['user_id'])
    assert _User.keys() == {
        'email',
        'send_deals_on_day',
        'username',
        'user_id',
        'is_admin',
        'is_active',
        'deals_email_enabled',
        # Settings rebuild Phase 4 — bulk-stamped via _stamp_has_image.
        'has_image',
    }


def test__get_users__GettingAllUsers__GetsAllUsers(api):
    _Response = requests.get(f'{base_route}?limit=500')

    assert _Response.status_code == 200
    assert _Response.headers['Content-Type'] == 'application/json'
    _Body = _Response.json()
    # Other suites (auth flows) register users into the shared DB, so assert
    # the envelope is well-formed and the seeded user is present, not an exact
    # count.
    assert _Body['total'] == len(_Body['items'])
    assert any(u['username'] == 'dora' for u in _Body['items'])


def test__get_users__FilteringByName__GetsSingleMatchingUser(api):
    _Response = requests.get(f'{base_route}?filter=username:ct:dor')

    assert _Response.status_code == 200
    assert _Response.headers['Content-Type'] == 'application/json'
    assert _Response.json()['items'][0]['username'] == 'dora'
    assert len(_Response.json()['items']) == 1


def test__get_users__FilteringOnNonExistentAttribute__IsBadRequest(api):
    _Response = requests.get(f'{base_route}?filter=poopus_goopus:ct:guy')

    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json() == {
        'detail': 'See errors property for more details.',
        'errors': {},
        'status': 400,
        'title': "Field 'poopus_goopus' is not filterable on 'User'.",
        'type': 'https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1',
    }


def test__get_users__FilteringForUserThatDoesNotExist__EmptyResult(api):
    _Response = requests.get(f'{base_route}?filter=user_id:eq:{uuid.uuid4()}')

    assert _Response.status_code == 200
    assert _Response.headers['Content-Type'] == 'application/json'
    assert _Response.json()['items'] == []
    assert _Response.json()['total'] == 0


def test__get_users__FilteringWithUnsupportedOperator__IsBadRequest(api):
    _Response = requests.get(f'{base_route}?filter=user_id:xx:{uuid.uuid4()}')

    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json() == {
        'detail': 'See errors property for more details.',
        'errors': {},
        'status': 400,
        'title': "Unsupported filter operator 'xx'. Supported: ct, eq, ge, gt, le, lt, ne.",
        'type': 'https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1',
    }


def test__get_users__SortingByNonExistentAttribute__IsBadRequest(api):
    _Response = requests.get(f'{base_route}?sort=dingo:desc')

    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json() == {
        'detail': 'See errors property for more details.',
        'errors': {},
        'status': 400,
        'title': "Field 'dingo' is not filterable on 'User'.",
        'type': 'https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1',
    }


# FU-169 Phase 2 — parametrized pagination-validation matrix.
@pytest.mark.parametrize(
    "query,invalid_field",
    [
        ("page=true&limit=2", "page"),
        ("page=1&limit=true", "limit"),
    ],
    ids=["page-is-not-integer", "limit-is-not-integer"],
)
def test__get_users__pagination_value_is_not_integer__IsBadRequest(api, query, invalid_field):
    _Response = requests.get(f'{base_route}?{query}')

    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json() == {
        'detail': 'See errors property for more details.',
        'errors': {},
        'status': 400,
        'title': f"'{invalid_field}' must be an integer.",
        'type': 'https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1',
    }


def test__get_users__PageWithoutLimit__DefaultsLimit(api):
    # page/limit are now independently optional (limit defaults to 50).
    _Response = requests.get(f'{base_route}?page=1')

    assert _Response.status_code == 200
    assert _Response.json()['page'] == 1
    assert _Response.json()['limit'] == 50
    assert len(_Response.json()['items']) >= 1


def test__get_users__LimitWithoutPage__DefaultsPage(api):
    _Response = requests.get(f'{base_route}?limit=1')

    assert _Response.status_code == 200
    assert _Response.json()['page'] == 1
    assert _Response.json()['limit'] == 1
    assert len(_Response.json()['items']) == 1


def test__get_users__FilteringSortingAndPagingUsers__GetsMatchingUsers(api):
    _Response = requests.get(f'{base_route}?filter=username:ct:dor&sort=username:asc&page=1&limit=1')

    assert _Response.status_code == 200
    assert _Response.headers['Content-Type'] == 'application/json'
    assert _Response.json()['items'][0]['username'] == 'dora'
    assert len(_Response.json()['items']) == 1


#endregion get_users tests

#region ---------------- admin-set passwords + deactivation ----------------

# These pin the two things the 2026-08-17 admin-users rework actually promises,
# both of which are invisible from the page itself: a password the admin typed
# is the password (and is never echoed back), and a deactivated account cannot
# get in. Chosen over UI-level checks per the lean verification stance — they're
# cheap, fast, and pin contracts that shouldn't churn.

_STRONG_PW = "Abcdefghij1"


def _reset_login_bucket() -> None:
    # `auth.login` is rate-limited 5/min per IP and the bucket is
    # process-lifetime, shared with every other suite. Clear it so a 429 can't
    # masquerade as the 401 these tests are actually asserting.
    from dora_api.infrastructure import auth_helpers
    with auth_helpers._buckets_lock:
        auth_helpers._buckets.clear()


def _create_user(**overrides) -> tuple[str, dict]:
    payload = {"username": f"probe-{uuid.uuid4().hex[:8]}", **overrides}
    response = requests.post(base_route, json=payload)
    assert response.status_code == 200, response.text
    return payload["username"], response.json()


def _login(username: str, password: str):
    _reset_login_bucket()
    return requests.Session().post(
        "http://localhost:5170/api/auth/login",
        json={"username": username, "password": password},
    )


def test__create_user__with_a_chosen_password__does_not_echo_it_back(api):
    username, body = _create_user(password=_STRONG_PW)

    # The admin already knows it — handing it back would be pure exposure.
    assert body["new_password"] is None
    assert _login(username, _STRONG_PW).status_code == 200


def test__create_user__without_a_password__generates_and_returns_one(api):
    username, body = _create_user()

    assert isinstance(body["new_password"], str) and len(body["new_password"]) == 12
    assert _login(username, body["new_password"]).status_code == 200


def test__create_user__with_a_weak_chosen_password__is_422(api):
    response = requests.post(base_route, json={
        "username": f"probe-{uuid.uuid4().hex[:8]}", "password": "short",
    })

    assert response.status_code == 422, response.text
    assert "password" in response.json()["errors"]


def test__create_user__ChosenPasswordShortOnlyOnceStripped__Is422(api):
    """Validated after the strip it's stored with: seven characters padded to
    nine used to pass the 8-character rule and be stored as seven."""
    response = requests.post(base_route, json={
        "username": f"probe-{uuid.uuid4().hex[:8]}", "password": " Abcdef1 ",
    })

    assert response.status_code == 422, response.text
    assert "password" in response.json()["errors"]


def test__login__UserNeverChangedPassword__LaterResetEndsTheSession(api):
    """Login always stamps the session's password version, and get_me compares
    it as an instant — so a reset after sign-in signs that device out."""
    from dora_api.app import app, db
    from sqlalchemy import text
    from tests.support import uuid_bind

    username, body = _create_user(password=_STRONG_PW)
    with app.app_context(), db.engine.begin() as conn:
        conn.execute(
            text('UPDATE "User" SET password_changed_at = NULL WHERE id = :id'),
            {"id": uuid_bind(body["user_id"])},
        )
    _reset_login_bucket()
    device = requests.Session()
    signed_in = device.post(
        "http://localhost:5170/api/auth/login",
        json={"username": username, "password": _STRONG_PW},
    )
    assert signed_in.status_code == 200, signed_in.text
    assert device.get("http://localhost:5170/api/auth/me").status_code == 200

    reset = requests.post(f'{base_route}/{body["user_id"]}/reset-password', json={
        "password": "Zyxwvutsrq9",
    })
    assert reset.status_code == 200, reset.text

    assert device.get("http://localhost:5170/api/auth/me").status_code == 401


def test__set_password__with_a_chosen_password__replaces_the_old_one(api):
    username, body = _create_user()
    user_id = body["user_id"]

    response = requests.post(f'{base_route}/{user_id}/reset-password', json={
        "password": _STRONG_PW,
    })

    assert response.status_code == 200, response.text
    assert response.json()["new_password"] is None
    assert _login(username, _STRONG_PW).status_code == 200
    assert _login(username, body["new_password"]).status_code == 401


def test__deactivating_a_user__stops_them_signing_in(api):
    username, body = _create_user(password=_STRONG_PW)
    assert _login(username, _STRONG_PW).status_code == 200

    patch = requests.patch(f'{base_route}/{body["user_id"]}', json={"is_active": False})
    assert patch.status_code == 204, patch.text

    refused = _login(username, _STRONG_PW)
    assert refused.status_code == 401
    # Credentials were right, so naming the reason leaks nothing and saves
    # them guessing at a password that works.
    assert "deactivated" in refused.json()["detail"].lower()

    # …and reactivating lets them straight back in — nothing was destroyed.
    assert requests.patch(
        f'{base_route}/{body["user_id"]}', json={"is_active": True},
    ).status_code == 204
    assert _login(username, _STRONG_PW).status_code == 200


def test__deactivating_yourself__is_refused(api):
    me = requests.get(f'{base_route}?filter=username:eq:dora').json()['items'][0]

    response = requests.patch(f'{base_route}/{me["user_id"]}', json={"is_active": False})

    # `business_rule_violation` is a 422 carrying the message under errors[""].
    assert response.status_code == 422, response.text
    assert "own account" in response.text.lower()
    # And the guard actually held — the caller is still usable.
    assert requests.get(base_route).status_code == 200

#endregion admin-set passwords + deactivation
