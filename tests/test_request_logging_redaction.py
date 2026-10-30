"""Finalisation 15-R2 / 15-R1 — request-log redaction and the proxy knob.

`middleware.audit_incoming_request` dumps request bodies at DEBUG, which is
the dev default; before this it printed `/auth/login` bodies — username *and*
password — into the rotating log file. The redaction is a pure function, so
it is pinned here without HTTP. The proxy-hop knob is a pure config read.
"""
from dora_api.infrastructure.middleware import REDACTED, _request_id, redact_sensitive


def test__redact_sensitive__masks_secret_looking_keys_at_any_depth():
    body = {
        "username": "dora",
        "password": "hunter2",
        "profile": {"display_name": "Dora", "current_password": "x", "new_password": "y"},
        "providers": [{"name": "openai", "api_key": "sk-live"}, {"name": "ollama"}],
        "smtp_password": "p",
        "vapid_private_key": "k",
        "Authorization": "Bearer abc",
        "count": 3,
    }
    out = redact_sensitive(body)

    assert out["username"] == "dora"
    assert out["password"] == REDACTED
    assert out["profile"] == {"display_name": "Dora", "current_password": REDACTED, "new_password": REDACTED}
    assert out["providers"] == [{"name": "openai", "api_key": REDACTED}, {"name": "ollama"}]
    assert out["smtp_password"] == REDACTED
    assert out["vapid_private_key"] == REDACTED
    assert out["Authorization"] == REDACTED
    assert out["count"] == 3
    # The caller's object is untouched — this is a copy for the log line.
    assert body["password"] == "hunter2"


def test__redact_sensitive__passes_non_containers_through():
    assert redact_sensitive(None) is None
    assert redact_sensitive("plain") == "plain"
    assert redact_sensitive([1, "two", {"token": "t"}]) == [1, "two", {"token": REDACTED}]


def test__trusted_proxy_hops__defaults_to_zero_and_never_goes_negative(monkeypatch):
    from dora_api.infrastructure.configuration_manager import DORA_CONFIG

    monkeypatch.delenv("DORA_TRUSTED_PROXY_HOPS", raising=False)
    assert DORA_CONFIG.get_trusted_proxy_hops() == 0
    monkeypatch.setenv("DORA_TRUSTED_PROXY_HOPS", "1")
    assert DORA_CONFIG.get_trusted_proxy_hops() == 1
    monkeypatch.setenv("DORA_TRUSTED_PROXY_HOPS", "-2")
    assert DORA_CONFIG.get_trusted_proxy_hops() == 0
    monkeypatch.setenv("DORA_TRUSTED_PROXY_HOPS", "banana")
    assert DORA_CONFIG.get_trusted_proxy_hops() == 0
    monkeypatch.setenv("DORA_TRUSTED_PROXY_HOPS", "")
    assert DORA_CONFIG.get_trusted_proxy_hops() == 0


def test__request_id__keeps_a_well_formed_caller_id():
    assert _request_id("  3f2c9a1e-77b0-4c1d-9a8e-2d6f0b1c4e55 ") == "3f2c9a1e-77b0-4c1d-9a8e-2d6f0b1c4e55"


def test__request_id__replaces_one_the_audit_column_cannot_hold():
    """`AuditEvent.request_id` is String(64): Postgres rejects a longer value
    and the audit insert fails. Odd characters would land in logs and the
    echoed response header."""
    too_long = "a" * 65
    for bad in (too_long, "id with spaces", "<script>", "", None):
        replaced = _request_id(bad)
        assert replaced != bad and len(replaced) == 32 and replaced.isalnum()
