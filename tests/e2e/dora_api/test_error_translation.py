"""FU-099 end-to-end: the wire contract for validation + domain errors.

These tests pin the new ``ErrorEntry`` shape — ``{msg, code, raw}`` per
field — so a future change to the friendly-copy table or a refactor of
the middleware lift can't silently drop the structured fields the SPA
relies on. Per-feature router tests (test_product_router,
test_stock_item_router, …) assert the *content* of specific errors;
these tests assert the *contract*.
"""
import requests

from tests.e2e.dora_api._error_assertions import domain_err, validation_err


def test__validation_error__has_friendly_msg_plus_code_plus_raw(api):
    """A wrong-type field comes back with the friendly translation in
    ``msg``, the structured Pydantic code in ``code``, and the raw
    developer-facing string in ``raw``."""
    response = requests.post(
        "http://localhost:5170/api/stock-items",
        json={"name": 123, "stock_level_id": "not-a-uuid"},
    )

    assert response.status_code == 400
    body = response.json()
    name_errors = body["errors"]["name"]
    assert len(name_errors) == 1
    entry = name_errors[0]
    assert set(entry.keys()) == {"msg", "code", "raw"}
    assert entry["msg"] == "Must be text."
    assert entry["code"] == "string_type"
    assert entry["raw"] == "Input should be a valid string"


def test__validation_error__missing_required_field__uses_missing_code(api):
    response = requests.post("http://localhost:5170/api/stock-items", json={})

    assert response.status_code == 400
    body = response.json()
    assert body["errors"]["name"] == [validation_err("missing", "Field required")]
    assert body["errors"]["stock_level_id"] == [validation_err("missing", "Field required")]


def test__validation_error__extra_field__uses_extra_forbidden_code(api):
    response = requests.post(
        "http://localhost:5170/api/locations",
        json={"name": "Cellar 99", "kind": "zone", "bogus": "junk"},
    )

    assert response.status_code == 400
    assert response.json()["errors"]["bogus"] == [
        validation_err("extra_forbidden", "Extra inputs are not permitted"),
    ]


def test__validation_error__unknown_pydantic_code__falls_back_to_generic_msg(api):
    """We deliberately don't translate every Pydantic code; anything
    outside the inclusion list must hit ``FRIENDLY_FALLBACK`` so the
    client still gets *something* readable, while ``raw`` preserves the
    real text and ``code`` lets devs grep for what to add to the map."""
    from dora_api.infrastructure.error_translation import (FRIENDLY_FALLBACK,
                                                           translate_pydantic_error)
    assert translate_pydantic_error("definitely_not_a_real_code") == FRIENDLY_FALLBACK


def test__domain_error__business_rule_violation__shape_lifts_string_into_entry(api):
    """``business_rule_violation`` takes a plain string; the helper lifts
    it into ``ErrorEntry(code="domain", raw=None)`` so the wire shape is
    uniform whether the error came from Pydantic or from us."""
    # An area with no parent zone is a business-rule violation.
    response = requests.post(
        "http://localhost:5170/api/locations",
        json={"name": "Top shelf", "kind": "area"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["errors"][""] == [domain_err("An area needs a parent zone.")]


def test__domain_error__entity_existence_failure__shape_lifts_string_into_entry(api):
    """``entity_existence_failure`` similarly lifts its plain-string
    message into an ``ErrorEntry`` so the SPA's renderer doesn't need
    to know whether the bad reference came from Pydantic or from us."""
    from uuid import uuid4
    fake_id = uuid4()
    response = requests.post(
        "http://localhost:5170/api/stock-items",
        json={"name": "Just A Test", "stock_level_id": str(fake_id)},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["errors"]["stock_level_id"] == [
        domain_err(f"StockLevel with the ID '{fake_id}' was not found."),
    ]
