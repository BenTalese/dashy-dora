import requests

#region ---------------- setup ----------------

base_route = 'http://localhost:5170/api/health'

#endregion setup

#region ---------------- health_check tests ----------------


def test__health_check__ApiIsHealthy__GetsOkayResponse(api):
    _Response = requests.get(base_route)

    # the health endpoint now returns a status document
    # ({ok, profile, schema_version, features}) rather than a bare `True`.
    assert _Response.status_code == 200
    assert _Response.headers['Content-Type'] == 'application/json'
    assert _Response.json()['ok'] is True


def test__health_check__reports_db_schema_version_alongside_code_head(api):
    """FU-570 — the probe reports the connected DB's *actual* alembic
    revision (`schema_version_db`) next to the code-side head
    (`schema_version`), so a stale DB no longer misleads diagnosis. In the
    e2e env the DB is built via create_all and never alembic-stamped, so
    `schema_version_db` is null — the pinned contract is that the key is
    present (add-not-remove) and reports the DB's reality, not the code head."""
    body = requests.get(base_route).json()
    assert "schema_version" in body, body
    assert "schema_version_db" in body, body
    # create_all'd e2e DB carries no alembic_version row.
    assert body["schema_version_db"] is None, body


def test__health_check__publishes_the_product_search_url_for_every_user(api):
    """Members can't read `/app-settings`, so the Product Search nav entry
    never appeared for them; the URL rides `/health` (finalisation 13-R4)."""
    url = "https://companion.example/search"
    assert requests.patch(
        "http://localhost:5170/api/app-settings", json={"product_search_url": url},
    ).status_code == 200
    try:
        assert requests.get(base_route).json()["products_policy"] == {"search_url": url}
    finally:
        requests.patch("http://localhost:5170/api/app-settings", json={"product_search_url": ""})


#endregion health_check tests
