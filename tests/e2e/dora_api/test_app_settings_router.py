"""FU-519 tail — e2e for the /api/app-settings router.

GET + PATCH of the install-wide settings row, plus POST /probe (the LLM
connection tester). Sibling suites already own the deep field-specific
behaviour (locale/currency: test_locale_currency; timezone boundaries:
test_household_tz_boundaries; secrets: test_bucket_c_secrets;
product_search_url: test_product_search_url_setting; full GET key
snapshot: test_dto_contracts). This file pins what none of them do:

  - the admin gate on both verbs (anonymous → 401, non-admin → 403),
  - secret ciphertext never rides the GET DTO (only `_configured` bools),
  - a plain PATCH round-trip (bool + bounded int) with partial-update
    semantics (untouched fields stay put),
  - the handler-level enum/format validations → 400 "Invalid settings.",
  - request-model validation (unknown field, bounds, bad types) → 400,
  - /probe degrades to `reachable: false` on an unreachable URL (no 5xx).
"""
from uuid import uuid4

import requests

from tests.support import assert_problem, open_registration

BASE = "http://localhost:5170/api"
APP_SETTINGS = f"{BASE}/app-settings"


def _get_settings() -> dict:
    resp = requests.get(APP_SETTINGS)
    assert resp.status_code == 200, resp.text
    return resp.json()


#region ---------------- auth posture ----------------


def test__app_settings__Anonymous__401OnBothVerbs(api):
    anon = requests.Session()
    assert_problem(anon.get(APP_SETTINGS), 401)
    assert_problem(anon.patch(APP_SETTINGS, json={"scanning_enabled": True}), 401)


def test__app_settings__NonAdmin__403OnBothVerbs(api):
    # Mint a plain user: /register (opened for this test — SEC-3) grants
    # is_admin=False, and login doesn't require email verification.
    # NB: register from a *fresh* session — /register logs the new user in
    # on whatever cookie jar carried the request, which would hijack the
    # shared admin client's session for every later test.
    username = f"peon-{uuid4().hex[:8]}"
    password = f"hunter-{uuid4().hex[:8]}"
    peon = requests.Session()
    open_registration()
    registered = peon.post(f"{BASE}/auth/register", json={
        "username": username, "password": password,
    })
    assert registered.status_code == 200, registered.text

    login = peon.post(f"{BASE}/auth/login", json={
        "username": username, "password": password,
    })
    assert login.status_code == 200, login.text

    assert_problem(peon.get(APP_SETTINGS), 403, detail="Admin role required.")
    assert_problem(
        peon.patch(APP_SETTINGS, json={"scanning_enabled": True}),
        403, detail="Admin role required.",
    )


#endregion auth posture

#region ---------------- GET shape ----------------


def test__get_app_settings__SecretsNeverRideTheDto__OnlyConfiguredFlags(api):
    body = _get_settings()

    # Plaintext / ciphertext secret fields must not exist on the wire.
    assert "smtp_password" not in body
    assert "smtp_password_encrypted" not in body
    assert "vapid_private_key" not in body
    assert "vapid_private_key_encrypted" not in body
    # ... the admin UI gets Set/Change/Clear affordances via bools instead.
    assert isinstance(body["smtp_password_configured"], bool)
    assert isinstance(body["vapid_private_key_configured"], bool)


def test__get_app_settings__CoreFields__PresentAndTyped(api):
    body = _get_settings()

    for flag in ("scanning_enabled", "money_enabled",
                 "nutrition_off_lookup_enabled",
                 "auto_drain_past_meals"):
        assert isinstance(body[flag], bool), flag
    # Nutrition is a three-state install-wide mode, not a bool (2026-08-14 —
    # the old `nutrition_enabled` flag + per-user mode collapsed into this).
    assert body["nutrition_mode"] in {"off", "simple", "complex"}
    assert isinstance(body["expiring_soon_window_days"], int)
    assert body["auto_add_mode"] in {"off", "essential_only", "all"}
    assert body["stocktake_default_cadence_band"] in {"weekly", "fortnightly", "monthly"}
    assert len(body["currency"]) == 3 and body["currency"].isupper()


#endregion GET shape


def test__patch__invalid_nutrition_mode__is_400_not_500(api):
    """Finalisation 13-R1 — the handler returned a bare `(None, "reason")`
    tuple for an unknown mode; the route then read `.invalid_reason` off it
    and 500'd. Every other invalid field answers 400 with the reason."""
    resp = requests.patch(APP_SETTINGS, json={"nutrition_mode": "bogus"})
    assert resp.status_code == 400, resp.text
    assert "Invalid nutrition mode" in resp.text
    # And the stored mode is untouched.
    assert _get_settings()["nutrition_mode"] in {"off", "simple", "complex"}

#region ---------------- PATCH round-trip ----------------


def test__patch_app_settings__BoolAndBoundedInt__RoundTripsAndLeavesRestAlone(api):
    before = _get_settings()
    flipped = not before["scanning_enabled"]

    resp = requests.patch(APP_SETTINGS, json={
        "scanning_enabled": flipped,
        "expiring_soon_window_days": 14,
    })

    assert resp.status_code == 200, resp.text
    echoed = resp.json()
    assert echoed["scanning_enabled"] is flipped
    assert echoed["expiring_soon_window_days"] == 14

    after = _get_settings()
    assert after["scanning_enabled"] is flipped
    assert after["expiring_soon_window_days"] == 14
    # Partial-update semantics: everything we didn't send is untouched.
    assert after["money_enabled"] == before["money_enabled"]
    assert after["timezone"] == before["timezone"]
    assert after["auto_add_mode"] == before["auto_add_mode"]


def test__patch_app_settings__EmptyBody__200NoOp(api):
    before = _get_settings()
    resp = requests.patch(APP_SETTINGS, json={})
    assert resp.status_code == 200, resp.text
    assert _get_settings() == before


#endregion PATCH round-trip

#region ---------------- PATCH validation ----------------


def test__patch_app_settings__UnknownField__400(api):
    resp = requests.patch(APP_SETTINGS, json={"llm_enabled": True})
    assert_problem(resp, 400, field="llm_enabled")


def test__patch_app_settings__OutOfBoundsWindow__400(api):
    assert_problem(
        requests.patch(APP_SETTINGS, json={"expiring_soon_window_days": 0}),
        400, field="expiring_soon_window_days",
    )
    assert_problem(
        requests.patch(APP_SETTINGS, json={"expiring_soon_window_days": 366}),
        400, field="expiring_soon_window_days",
    )


def test__patch_app_settings__WrongType__400(api):
    resp = requests.patch(APP_SETTINGS, json={"expiring_soon_window_days": "fortnight"})
    assert_problem(resp, 400, field="expiring_soon_window_days")


def test__patch_app_settings__BogusTimezone__400InvalidSettings(api):
    resp = requests.patch(APP_SETTINGS, json={"timezone": "Mars/Olympus_Mons"})
    assert_problem(resp, 400, title="Invalid settings.",
                   detail="not a recognised IANA timezone")


def test__patch_app_settings__BogusCadenceBand__400InvalidSettings(api):
    resp = requests.patch(
        APP_SETTINGS, json={"stocktake_default_cadence_band": "sometimes"},
    )
    assert_problem(resp, 400, title="Invalid settings.",
                   detail="not a valid cadence band")


def test__patch_app_settings__BogusAutoAddMode__400InvalidSettings(api):
    resp = requests.patch(APP_SETTINGS, json={"auto_add_mode": "everything"})
    assert_problem(resp, 400, title="Invalid settings.",
                   detail="not a valid auto-add mode")


def test__patch_app_settings__NonAlphaCurrency__400InvalidSettings(api):
    resp = requests.patch(APP_SETTINGS, json={"currency": "A1D"})
    assert_problem(resp, 400, title="Invalid settings.", detail="ISO 4217")


def test__patch_app_settings__MalformedLocale__400InvalidSettings(api):
    resp = requests.patch(APP_SETTINGS, json={"locale": "99-XX"})
    assert_problem(resp, 400, title="Invalid settings.", detail="BCP-47")


def test__patch_app_settings__NonHttpProductSearchUrl__400InvalidSettings(api):
    resp = requests.patch(APP_SETTINGS, json={"product_search_url": "ftp://deals.example"})
    assert_problem(resp, 400, title="Invalid settings.",
                   detail="must start with http:// or https://")


#endregion PATCH validation

# The `/app-settings/probe` region went with its route (finalisation 13-R19 —
# the Assistant page probes per-user providers via `/assistant/probe`).
