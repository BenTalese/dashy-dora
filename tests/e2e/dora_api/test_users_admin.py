"""Users admin — Add / Delete behaviour (FU-461).

DORA_VERIFY Settings L1047–L1061. `test_route_auth_enforcement.py` pins the
admin gate on these endpoints and `test_patch_semantics.py` covers the PATCH
guards; this closes the create-validation and delete-guard behaviour:

* create → 200 + one-time password + the user is listed;
* create with a taken username / taken email / malformed email → 422;
* delete your own account → 403 (self-delete refused);
* delete another user → 204 and they leave the list;
* delete a non-existent user → 404.

The delete-last-admin guard is symmetric with the PATCH-demotion guard already
pinned in test_patch_semantics; it's hard to reach here (self-delete precedence +
the single seeded admin), so it stays owner-walk.
"""
from uuid import uuid4

import requests

from tests.support import assert_problem

BASE = "http://localhost:5170/api"
USERS = f"{BASE}/users"


def _uniq(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _create(**body) -> requests.Response:
    return requests.post(USERS, json={"username": _uniq("admin-user"), **body})


def _me() -> dict:
    return requests.get(f"{BASE}/auth/me").json()


def _row(user_id: str) -> dict | None:
    items = requests.get(USERS, params={"filter": f"user_id:eq:{user_id}"}).json()["items"]
    return items[0] if items else None


def test__admin_create_user__returns_one_time_password_and_lists_the_user(api):
    resp = _create(email=f"{_uniq('mail')}@example.com", is_admin=True)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user_id"]
    # The one-time password travels in the body (not retrievable later).
    assert isinstance(body["new_password"], str) and len(body["new_password"]) >= 12
    row = _row(body["user_id"])
    assert row is not None
    assert row["is_admin"] is True


def test__admin_create_user__taken_username__rejected_422(api):
    first = _create()
    assert first.status_code == 200, first.text
    taken = _row(first.json()["user_id"])["username"]
    resp = requests.post(USERS, json={"username": taken})
    assert_problem(resp, 422)
    assert "already taken" in resp.text.lower()


def test__admin_create_user__taken_email__rejected_422(api):
    email = f"{_uniq('mail')}@example.com"
    first = _create(email=email)
    assert first.status_code == 200, first.text
    resp = _create(email=email)
    assert_problem(resp, 422)
    assert "already registered" in resp.text.lower()


def test__admin_create_user__malformed_email__rejected_422(api):
    resp = _create(email="nope")
    body = assert_problem(resp, 422, field="email")
    assert "valid email" in resp.text.lower()


def _user_entity(user_id: str):
    from uuid import UUID

    from dora_api.app import app
    from dora_api.domain.entities.user import User
    from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

    with app.app_context():
        return SqlAlchemyRepository().get(User).by_id(UUID(user_id))


def test__admin_update_user__email__validated_unique_and_unverifies(api):
    """Finalisation 13-R2 — the admin email edit assigned the raw string with
    no validation, no uniqueness check and no reset of `email_verified`;
    create and self-service both apply all three."""
    taken = f"{_uniq('taken')}@example.com"
    other = _create(email=taken).json()["user_id"]
    victim = _create(email=f"{_uniq('mail')}@example.com").json()["user_id"]

    malformed = requests.patch(f"{USERS}/{victim}", json={"email": "not an email"})
    assert_problem(malformed, 422)

    duplicate = requests.patch(f"{USERS}/{victim}", json={"email": taken.upper()})
    assert_problem(duplicate, 422)
    assert _user_entity(other).email == taken  # the other account is untouched

    fresh = f"  {_uniq('New')}@Example.com "
    changed = requests.patch(f"{USERS}/{victim}", json={"email": fresh})
    assert changed.status_code == 204, changed.text
    entity = _user_entity(victim)
    assert entity.email == fresh.strip().lower()
    assert entity.email_verified is False


def test__admin_guards__usable_admin_bar_counts_active_admins_only(api):
    """Finalisation 13-R3 — one bar for demote / deactivate / delete: an
    admin who has been deactivated cannot be the install's "last admin"
    insurance. Pinned on the shared helper because the DELETE route's own
    scenario is unreachable through the API (you can't delete yourself and
    a deactivated admin can't sign in to do it)."""
    from dora_api.app import app
    from dora_api.features.users.admin_guards import other_usable_admins
    from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

    me = _me()
    my_id = me.get("user_id") or me.get("id")
    active_admin = _create(email=f"{_uniq('a')}@example.com", is_admin=True).json()["user_id"]
    parked_admin = _create(email=f"{_uniq('b')}@example.com", is_admin=True).json()["user_id"]
    assert requests.patch(f"{USERS}/{parked_admin}", json={"is_active": False}).status_code == 204

    with app.app_context():
        repo = SqlAlchemyRepository()
        # From my seat: the active one counts, the parked one doesn't.
        assert other_usable_admins(repo, my_id) == 1
        # From the active admin's seat: me (active) counts, the parked one doesn't.
        assert other_usable_admins(repo, active_admin) == 1
        # From the parked admin's seat: two usable admins remain.
        assert other_usable_admins(repo, parked_admin) == 2

    # Deleting the parked admin is fine (two usable admins remain)…
    assert requests.delete(f"{USERS}/{parked_admin}").status_code == 204
    # …and so is deleting the active one (I remain).
    assert requests.delete(f"{USERS}/{active_admin}").status_code == 204


def test__admin_delete_user__self__is_forbidden_403(api):
    me = _me()
    resp = requests.delete(f"{USERS}/{me['user_id']}")
    assert resp.status_code == 403, resp.text
    assert "your own account" in resp.text.lower()
    # Still there.
    assert _row(me["user_id"]) is not None


def test__admin_delete_user__another_user__removed(api):
    created = _create()
    user_id = created.json()["user_id"]
    assert _row(user_id) is not None
    resp = requests.delete(f"{USERS}/{user_id}")
    assert resp.status_code == 204, resp.text
    assert _row(user_id) is None


def test__admin_delete_user__unknown__404(api):
    resp = requests.delete(f"{USERS}/{uuid4()}")
    assert resp.status_code == 404, resp.text


_PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYPhfDwAChwGA"
    "60e6kgAAAABJRU5ErkJggg=="
)


def test__admin_update_user__clear_image__removes_the_picture(api):
    """Finalisation 13-R15: the server's `clear_image` finally has a caller
    ("Remove picture" in the Users overflow); setting another user's picture
    was dropped from the admin request (no caller, people set their own on
    `/auth/me`)."""
    me = _me()
    set_resp = requests.patch(f"{BASE}/auth/me", json={"image": _PNG_DATA_URL})
    assert set_resp.status_code in (200, 204), set_resp.text
    assert _row(me["user_id"])["has_image"] is True

    resp = requests.patch(f"{BASE}/users/{me['user_id']}", json={"clear_image": True})

    assert resp.status_code in (200, 204), resp.text
    assert _row(me["user_id"])["has_image"] is False
    # the set half is gone: an admin can't push a picture onto someone
    rejected = requests.patch(f"{BASE}/users/{me['user_id']}", json={"image": _PNG_DATA_URL})
    assert rejected.status_code == 400, rejected.text
